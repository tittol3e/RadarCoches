"""Ejecuta y verifica ingesta real; nunca sustituye Kafka por transporte local."""
import argparse
import importlib.metadata
import json
import os
import socket
import subprocess
import sys
import time
import uuid
import traceback
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check_api_ports(ports=(8771, 8772)):
    """Comprobar disponibilidad sin conectar a una API que aún no existe.

    En Windows un rechazo TCP puede tardar más que el timeout HTTP de 2 s.
    Bind exclusivo detecta también servicios ocupados que no respondan a HTTP.
    """
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                probe.bind(('127.0.0.1', port))
            except OSError as exc:
                raise RuntimeError(f'Puerto no disponible para API DEMO: 127.0.0.1:{port}: {exc}') from exc


def wait_for_apis(urls, children, timeout=30):
    import httpx
    deadline = time.monotonic() + timeout
    last = None
    with httpx.Client(timeout=2, trust_env=False) as client:
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in children):
                raise RuntimeError('Una API DEMO ha terminado; consulte source_a.log y source_b.log')
            try:
                for source, url in urls.items():
                    response = client.get(url + '/health')
                    response.raise_for_status()
                    health = response.json()
                    if health.get('source') != source or health.get('synthetic') is not True:
                        raise RuntimeError(f'El servicio en {url}/health no es la API DEMO {source}')
                return
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last = exc
                time.sleep(.3)
    request = getattr(last, 'request', None)
    raise RuntimeError(f'API DEMO no disponible: {getattr(request, "url", "desconocida")}: {last}') from last


def wait_for_kafka(timeout=30):
    from kafka import KafkaAdminClient
    from kafka.errors import KafkaError
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        admin = None
        try:
            admin = KafkaAdminClient(bootstrap_servers='127.0.0.1:9092',
                                     request_timeout_ms=5000, api_version_auto_timeout_ms=5000)
            return admin.describe_cluster()
        except (KafkaError, OSError) as exc:
            last = exc
            time.sleep(.5)
        finally:
            if admin is not None:
                admin.close()
    raise RuntimeError(f'Kafka no disponible en 127.0.0.1:9092: {last}') from last


def verify(root, expected):
    from actividad_ingesta.pipeline.distributed import duckdb_module
    from actividad_ingesta.pipeline.storage import Storage
    store = Storage(root)
    with store.db() as db:
        source = [tuple(r) for r in db.execute('SELECT source,id,version,payload FROM source_ads ORDER BY source,id')]
        actual = [tuple(r) for r in db.execute('SELECT source,id,version,payload FROM ads ORDER BY source,id')]
        events = db.execute('SELECT COUNT(*) FROM source_changes').fetchone()[0]
        history = [tuple(r) for r in db.execute('SELECT event_id,source,id,version,old_price,new_price,payload FROM history ORDER BY event_id')]
        pending = db.execute('SELECT COUNT(*) FROM outbox WHERE kafka_sent=0').fetchone()[0]
    if len(source) != expected or source != actual or len(history) != events or pending:
        raise AssertionError('Anuncios, historial o eventos pendientes no coinciden con las fuentes')
    with duckdb_module().connect(str(root / 'analitica.duckdb'), read_only=True) as db:
        columns = 'source,id,version,payload,marca,modelo,anio,kilometros,precio_centimos'
        analytical = db.execute(f'SELECT {columns} FROM anuncios ORDER BY source,id').fetchall()
        parquet = db.execute(f'SELECT {columns} FROM read_parquet(?) ORDER BY source,id', [str(root / 'anuncios.parquet')]).fetchall()
        analytical_history = db.execute('SELECT event_id,source,id,version,old_price,new_price,payload FROM historial ORDER BY event_id').fetchall()
    enriched = []
    for row in actual:
        ad = json.loads(row[3])
        enriched.append(row + tuple(ad[key] for key in ('marca', 'modelo', 'anio', 'kilometros', 'precio_centimos')))
    if enriched != analytical or analytical != parquet or history != analytical_history:
        raise AssertionError('DuckDB, Parquet o historial difieren del estado consumido')
    return dict(passed=True, unique_ads=len(actual), events=events, parquet_read=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--volume', action='store_true')
    args = parser.parse_args(argv)
    from actividad_ingesta.pipeline.distributed import require_dependencies, dlt_extract, publish, consume
    from actividad_ingesta.pipeline.generator import BASE_TIME, generate
    from actividad_ingesta.pipeline.lab import Lab
    os.chdir(ROOT)
    run_id = uuid.uuid4().hex
    root = ROOT / 'data' / 'laboratorio_distribuido' / run_id
    evidence = ROOT / 'docs' / 'evidencias' / 'distribuido'
    evidence.mkdir(parents=True, exist_ok=True)
    report = dict(passed=False, synthetic=True, mode='distributed', root=str(root), steps=[],
                  scenario='volume' if args.volume else 'revisions')
    children, logs = [], []
    try:
        report['phase'] = 'dependencies'
        require_dependencies()
        report['versions'] = {n: importlib.metadata.version(n) for n in ('dlt', 'duckdb', 'kafka-python')}
        root.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, RADAR_LAB_DIR=str(root))
        urls = {'demo_a': 'http://127.0.0.1:8771', 'demo_b': 'http://127.0.0.1:8772'}
        report['connections'] = dict(apis=urls, kafka='127.0.0.1:9092')
        report['phase'] = 'api_port_check'
        check_api_ports()
        report['phase'] = 'kafka_readiness'
        report['kafka'] = wait_for_kafka()
        report['phase'] = 'api_startup'
        for name, port in [('source_a', 8771), ('source_b', 8772)]:
            log = (root / f'{name}.log').open('w', encoding='utf-8')
            logs.append(log)
            children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn',
                f'actividad_ingesta.pipeline.apis:{name}', '--factory', '--host', '127.0.0.1', '--port', str(port)],
                env=env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)))
        wait_for_apis(urls, children)
        lab = Lab(root)

        def cycle(label, expected, expected_events, expected_messages):
            print(f'{label}: extracción, publicación y consumo…', flush=True)
            step = dict(label=label)
            report['steps'].append(step)
            report['phase'] = label + ': dlt HTTP -> DuckDB'
            step['extraction'] = dlt_extract(root, urls)
            report['phase'] = label + ': Kafka publish 127.0.0.1:9092'
            step['published'] = publish(root)
            report['phase'] = label + ': Kafka consume 127.0.0.1:9092'
            step['consumed'] = consume(root)
            report['phase'] = label + ': verify DuckDB/Parquet'
            verified = verify(root, expected)
            if (step['published']['published'], step['consumed']['consumed']) != (expected_messages,) * 2:
                raise AssertionError('Mensajes enviados o recibidos distintos de los esperados')
            if step['extraction']['landing_events_relayed'] != expected_events or verified['events'] != expected_events:
                raise AssertionError('El total de eventos de landing o del consumidor no coincide')
            step['verification'] = verified

        if args.volume:
            for source in urls:
                for n in range(1, 501):
                    lab.store.put_source(generate(source, n, seed=73))
            cycle('1000 iniciales', 1000, 1000, 1000)
            for source in urls:
                for n in range(501, 526):
                    lab.store.put_source(generate(source, n, seed=73))
            cycle('50 altas', 1050, 1050, 50)
            for source in urls:
                for n in range(1, 11):
                    ad = generate(source, n, seed=73)
                    ad.update(precio_centimos=ad['precio_centimos'] - 25000, version_evento=2,
                              actualizado=(BASE_TIME + timedelta(days=2)).isoformat())
                    lab.store.put_source(ad)
            cycle('20 precios modificados', 1050, 1070, 20)
        else:
            for revision, (expected, events, messages) in enumerate(((10, 10, 10), (12, 12, 2), (12, 14, 2), (12, 14, 0))):
                lab.prepare_revision(revision)
                cycle(f'revisión {revision}', expected, events, messages)
        expected = 1050 if args.volume else 12
        events = 1070 if args.volume else 14
        if lab.store.summary()['counts']['price_updates'] != (20 if args.volume else 2):
            raise AssertionError('Número de cambios de precio incorrecto')
        # Simular reenvío tras pérdida de ACK, manteniendo los mismos eventos.
        with lab.store.db() as db:
            db.execute('UPDATE outbox SET kafka_sent=0')
        cycle('reenvío completo sin duplicados', expected, events, events)
        report['phase'] = 'Kafka replay 127.0.0.1:9092'
        report['replay'] = consume(root, group=f'radar-replay-{run_id}')
        if report['replay']['consumed'] != events * 2:
            raise AssertionError('El replay no recibió todos los mensajes publicados')
        report['replay_verification'] = verify(root, expected)
        report['passed'] = True
        report['phase'] = 'completed'
        return 0
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        report['traceback'] = traceback.format_exc()
        request = getattr(exc, 'request', None)
        if request is not None:
            report['failed_url'] = str(request.url)
        print(f'Integración distribuida NO superada: {report["error"]}', file=sys.stderr)
        return 1
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        for log in logs:
            log.close()
        path = evidence / f'{run_id}.json'
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Evidencia: {path}', flush=True)


if __name__ == '__main__':
    sys.exit(main())
