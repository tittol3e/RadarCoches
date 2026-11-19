"""Integración real opcional. Ninguna dependencia distribuida se importa al arrancar Radar.

dlt -> DuckDB landing durable -> outbox -> Kafka -> consumidor -> DuckDB + Parquet.
El landing intermedio evita perder eventos si dlt confirma su cursor antes del envío.
"""
import json
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .extractor import get_json
from .models import Change
from .storage import Storage

TOPIC = "radarcoches.synthetic.events.v1"
ANALYTIC_QUERIES = {
    "counts": "SELECT source,COUNT(*) AS anuncios FROM anuncios GROUP BY source ORDER BY source",
    "prices": "SELECT source,marca,modelo,COUNT(*) AS anuncios,MIN(precio_centimos)/100.0 AS minimo_eur,MAX(precio_centimos)/100.0 AS maximo_eur FROM anuncios GROUP BY source,marca,modelo ORDER BY source,marca,modelo",
    "history": "SELECT source,id,version,old_price/100.0 AS anterior_eur,new_price/100.0 AS nuevo_eur FROM historial ORDER BY source,id,version LIMIT 100",
}


def duckdb_module():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB no está instalado; instale las dependencias Big Data en .venv. Consulta no ejecutada.") from exc
    return duckdb


def consumer_group(root):
    """Un grupo durable por directorio evita compartir offsets con bases nuevas."""
    digest = hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()[:20]
    return f"radarcoches-synthetic-{digest}"


def topic_for(root):
    """Aislar ejecuciones: volumen y revisiones reutilizan IDs con datos distintos."""
    return f"{TOPIC}.{consumer_group(root).rsplit('-', 1)[-1]}"


def require_dependencies():
    try:
        import dlt
        import duckdb
        import kafka
    except ImportError as exc:
        raise RuntimeError("Instale requirements-bigdata.txt en .venv; no se ha ejecutado dlt/Kafka/DuckDB") from exc
    return dlt, duckdb, kafka


def approved_api(url):
    # Conexiones externas requieren una configuración explícita con autorización.
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("URL de API inválida")
    if parts.hostname not in ("127.0.0.1", "localhost"):
        allowed = [x.strip() for x in os.environ.get("RADAR_AUTHORIZED_API_HOSTS", "").split(",") if x.strip()]
        if parts.hostname not in allowed or parts.scheme != "https":
            raise ValueError("API externa no autorizada; configure host HTTPS explícitamente")
    return url.rstrip("/")


def dlt_extract(root, urls):
    # Mantener también la configuración de dlt en el espacio de esta ejecución.
    # Su contexto predeterminado prueba escritura en ~ incluso con pipelines_dir.
    require_dependencies()
    from dlt.common.configuration.container import Container
    from dlt.common.configuration.specs.pluggable_run_context import PluggableRunContext
    from dlt.common.configuration.specs.runtime_configuration import RuntimeConfiguration
    from dlt.common.runtime.run_context import RunContext

    class LocalRunContext(RunContext):
        @property
        def global_dir(self):
            return str(Path(root).resolve() / 'dlt_runtime')

        def initialize_runtime(self, runtime_config=None):
            if runtime_config is None:
                runtime_config = RuntimeConfiguration()
                runtime_config.dlthub_telemetry = False
            super().initialize_runtime(runtime_config)

    Path(root, 'dlt_runtime').mkdir(parents=True, exist_ok=True)
    context = PluggableRunContext(LocalRunContext(str(Path(root).resolve())))
    with Container().injectable_context(context):
        return _dlt_extract(root, urls)


def _dlt_extract(root, urls):
    dlt, duckdb, _ = require_dependencies()
    root = Path(root).resolve()
    store = Storage(root)
    landing = root / "landing.duckdb"
    total = 0
    for source, url in urls.items():
        if source not in ("demo_a", "demo_b"):
            raise ValueError("Fuente desconocida")
        base = approved_api(url)

        @dlt.resource(name="eventos", primary_key="event_id", write_disposition="merge")
        def resource(cursor=dlt.sources.incremental("seq", initial_value=0)):
            since = int(cursor.last_value or 0)
            until, page = None, 1
            with httpx.Client(base_url=base, timeout=15, follow_redirects=False, trust_env=False) as client:
                while True:
                    params = dict(since=since, page=page, page_size=100)
                    if until is not None:
                        params["until"] = until
                    data = get_json(client, "/changes", params)
                    if data.get("synthetic") is not True or data.get("source") != source:
                        raise ValueError("Fuente no identificada como DEMO")
                    until = data["highwater"] if until is None else until
                    for raw in data["items"]:
                        event = Change.model_validate(raw).validated().model_dump(mode="json")
                        if event["source"] != source or not since < event["seq"] <= until:
                            raise ValueError("Evento fuera de la fuente o del intervalo solicitado")
                        yield dict(event_id=event["event_id"], seq=event["seq"], source=source,
                                   payload=json.dumps(event, ensure_ascii=False))
                    if not data.get("next_page"):
                        break
                    page += 1

        pipe = dlt.pipeline(pipeline_name=f"radar_{source}", pipelines_dir=str(root / "dlt_state"),
                            destination=dlt.destinations.duckdb(str(landing)), dataset_name=source)
        pipe.run(resource())
        # Relay TODO el landing durable: INSERT OR IGNORE conserva idempotencia.
        with duckdb.connect(str(landing)) as db:
            tables = db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=? AND table_name='eventos'", [source]).fetchall()
            rows = db.execute(f"SELECT payload FROM {source}.eventos ORDER BY seq").fetchall() if tables else []
        events = [json.loads(r[0]) for r in rows]
        store.enqueue(events, source, max((r["seq"] for r in events), default=store.cursor(source)))
        total += len(events)
    return dict(landing_events_relayed=total, extraction="dlt", landing=str(landing))


def publish(root, bootstrap="127.0.0.1:9092"):
    _, _, kafka = require_dependencies()
    store = Storage(root)
    topic = topic_for(root)
    producer = kafka.KafkaProducer(bootstrap_servers=bootstrap, acks="all", retries=3,
                                  request_timeout_ms=15000, max_block_ms=15000,
                                  value_serializer=lambda x: json.dumps(x, ensure_ascii=False).encode())
    sent = 0
    try:
        with store.db() as db:
            rows = db.execute("SELECT event_id,payload FROM outbox WHERE kafka_sent=0 ORDER BY rowid").fetchall()
        for row in rows:
            event = Change.model_validate_json(row["payload"]).validated().model_dump(mode="json")
            producer.send(topic, key=f"{event['source']}:{event['ad']['id']}".encode(), value=event).get(timeout=20)
            # Si el proceso cae antes del UPDATE, habrá reenvío (consumo idempotente).
            with store.db() as db:
                db.execute("UPDATE outbox SET kafka_sent=1 WHERE event_id=?", (row["event_id"],))
            sent += 1
        producer.flush(timeout=20)
    finally:
        producer.close(timeout=5)
    return dict(published=sent, topic=topic, transport="Kafka")


def export_analytics(root):
    duckdb = duckdb_module()
    store = Storage(root)
    root = store.root
    with store.db() as source:
        ads = source.execute("SELECT source,id,version,payload FROM ads ORDER BY source,id").fetchall()
        history = source.execute("SELECT event_id,source,id,version,old_price,new_price,payload FROM history").fetchall()
    with duckdb.connect(str(root / "analitica.duckdb")) as db:
        db.execute("CREATE TABLE IF NOT EXISTS anuncios(source VARCHAR,id VARCHAR,version INTEGER,precio_centimos BIGINT,marca VARCHAR,modelo VARCHAR,anio INTEGER,kilometros BIGINT,payload VARCHAR,PRIMARY KEY(source,id))")
        db.execute("CREATE TABLE IF NOT EXISTS historial(event_id VARCHAR PRIMARY KEY,source VARCHAR,id VARCHAR,version INTEGER,old_price BIGINT,new_price BIGINT,payload VARCHAR)")
        db.execute("BEGIN")
        try:
            db.execute("DELETE FROM anuncios")
            if ads:
                db.executemany("INSERT INTO anuncios VALUES (?,?,?,?,?,?,?,?,?)", [
                    (r[0], r[1], r[2], (a := json.loads(r[3]))["precio_centimos"], a["marca"], a["modelo"], a["anio"], a["kilometros"], r[3]) for r in ads])
            db.execute("DELETE FROM historial")
            if history:
                db.executemany("INSERT INTO historial VALUES (?,?,?,?,?,?,?)", [tuple(r) for r in history])
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
        # Ruta solo generada por el proyecto; escapar comillas para SQL COPY.
        temp = root / "anuncios.tmp.parquet"
        escaped = str(temp).replace("'", "''")
        db.execute(f"COPY anuncios TO '{escaped}' (FORMAT PARQUET)")
        os.replace(temp, root / "anuncios.parquet")
        result = db.execute("SELECT COUNT(*),SUM(precio_centimos) FROM anuncios").fetchone()
    return dict(unique_ads=result[0], price_sum_centimos=result[1], duckdb=str(root / "analitica.duckdb"), parquet=str(root / "anuncios.parquet"))


def consume(root, bootstrap="127.0.0.1:9092", group=None, max_events=100000, export_every=100):
    if max_events < 1 or export_every < 1:
        raise ValueError("max_events y export_every deben ser positivos")
    _, _, kafka = require_dependencies()
    from kafka.structs import OffsetAndMetadata, TopicPartition
    store = Storage(root)
    consumer = kafka.KafkaConsumer(topic_for(root), bootstrap_servers=bootstrap, group_id=group or consumer_group(root),
                                   enable_auto_commit=False, auto_offset_reset="earliest",
                                   consumer_timeout_ms=5000, request_timeout_ms=15000,
                                   session_timeout_ms=10000, value_deserializer=lambda x: json.loads(x))
    seen = 0
    offsets = {}
    analytics = None

    def checkpoint():
        # SQLite ya contiene cada evento; generar la proyección antes del ACK.
        # Si falla la exportación o el commit, el replay es idempotente.
        analytics = export_analytics(root)
        if offsets:
            consumer.commit(dict(offsets))
            offsets.clear()
        return analytics

    try:
        for record in consumer:
            store.consume(record.value)
            try:
                offset = OffsetAndMetadata(record.offset + 1, "", -1)
            except TypeError:
                offset = OffsetAndMetadata(record.offset + 1, "")
            offsets[TopicPartition(record.topic, record.partition)] = offset
            seen += 1
            if seen % export_every == 0:
                analytics = checkpoint()
            if seen >= max_events:
                break
        if offsets or analytics is None:
            analytics = checkpoint()
    finally:
        consumer.close(autocommit=False)
    return dict(consumed=seen, analytics=analytics)


def query_analytics(root, query="counts"):
    if query not in ANALYTIC_QUERIES:
        raise ValueError("Consulta analítica desconocida")
    duckdb = duckdb_module()
    path = Path(root).resolve() / "analitica.duckdb"
    if not path.is_file():
        return dict(available=False, message="Todavía no existe carga DuckDB verificada")
    # No se aceptan sentencias SQL arbitrarias desde la interfaz web.
    with duckdb.connect(str(path), read_only=True) as db:
        result = db.execute(ANALYTIC_QUERIES[query])
        columns = [d[0] for d in result.description]
        return dict(available=True, synthetic=True, rows=[dict(zip(columns, r)) for r in result.fetchall()])
