"""Servicio local ejecutable incluso cuando Docker/dlt/DuckDB no están disponibles."""
import importlib.util
import json
import threading
import uuid
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from .apis import create_source_app
from .extractor import extract
from .generator import BASE_TIME, generate
from .storage import Storage


class Lab:
    _lock = threading.RLock()

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.store = Storage(self.root)

    def run(self, page_size=100, stop_after=None):
        with self._lock:
            rid = self.store.begin_run()
            try:
                extracted = 0
                for source in ("demo_a", "demo_b"):
                    with TestClient(create_source_app(self.root, source)) as client:
                        extracted += extract(client, self.store, source, page_size)
                delivered = self.store.drain(stop_after=stop_after)
                self.store.end_run(rid, "success", dict(extracted=extracted, delivered=delivered, transport="sqlite_local"))
            except Exception as exc:
                self.store.end_run(rid, "interrupted" if isinstance(exc, InterruptedError) else "failed", dict(error=type(exc).__name__))
                raise
            return self.summary()

    def run_revision(self, revision):
        with self._lock:
            self.prepare_revision(revision)
            return self.run(page_size=3)

    def prepare_revision(self, revision):
        """Modifica solo las APIs simuladas; no extrae ni consume eventos locales."""
        if revision not in (0, 1, 2, 3):
            raise ValueError("Revisión permitida: 0, 1, 2 o 3")
        with self._lock:
            with self.store.db() as db:
                old = db.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()
                previous = int(old[0]) if old else -1
            if revision > previous + 1:
                raise ValueError("Ejecute primero las revisiones anteriores")
            if revision == 0 and previous < 0:
                for source in ("demo_a", "demo_b"):
                    for n in range(1, 6):
                        self.store.put_source(generate(source, n))
            elif revision == 1 and previous < 1:
                for source in ("demo_a", "demo_b"):
                    self.store.put_source(generate(source, 6))
            elif revision == 2 and previous < 2:
                for source in ("demo_a", "demo_b"):
                    ad = generate(source, 1)
                    ad.update(precio_centimos=ad["precio_centimos"] - 10000, version_evento=2,
                              actualizado=(BASE_TIME + timedelta(days=1)).isoformat())
                    self.store.put_source(ad)
            with self.store.db() as db:
                db.execute("INSERT INTO metadata VALUES ('revision',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(max(revision, previous)),))
            return dict(revision=max(revision, previous), synthetic=True,
                        source_changes=sum(self.store.highwater(s) > 0 for s in ("demo_a", "demo_b")))

    def summary(self):
        data = self.store.summary()
        with self.store.db() as db:
            row = db.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()
        data.update(label="DEMO / DATOS SINTÉTICOS", synthetic=True,
                    mode="local_sqlite", transport="Outbox SQLite local (NO es Kafka)",
                    extraction="APIs FastAPI ejecutadas en proceso con TestClient (NO es dlt)",
                    revision=int(row[0]) if row else -1,
                    dependencies={name: importlib.util.find_spec(name) is not None for name in ("dlt", "duckdb", "kafka")},
                    records=self.store.records()[:50],
                    analytics_available=importlib.util.find_spec("duckdb") is not None)
        return data

    def volume_demo(self):
        # Espacio propio para que el ejercicio 10/12 y el de volumen no se mezclen.
        volume = Lab(self.root / "volumen" / uuid.uuid4().hex)
        for source in ("demo_a", "demo_b"):
            for n in range(1, 501):
                volume.store.put_source(generate(source, n, seed=73))
        first = volume.run()["counts"]["ads"]
        for source in ("demo_a", "demo_b"):
            for n in range(501, 526):
                volume.store.put_source(generate(source, n, seed=73))
        added = volume.run()["counts"]["ads"]
        for source in ("demo_a", "demo_b"):
            for n in range(1, 11):
                ad = generate(source, n, seed=73)
                ad.update(precio_centimos=ad["precio_centimos"] - 25000,
                          version_evento=2, actualizado=(BASE_TIME + timedelta(days=2)).isoformat())
                # Repetir el ejercicio no debe retroceder versiones ni duplicar.
                volume.store.put_source(ad)
        final = volume.run()
        result = dict(label="DEMO / DATOS SINTÉTICOS", initial=first, after_add=added,
                      final=final["counts"]["ads"], price_updates=final["counts"]["price_updates"],
                      expected=dict(initial=1000, after_add=1050, final=1050, price_updates=20),
                      mode="local_sqlite", kafka_executed=False, dlt_executed=False, duckdb_executed=False)
        result["evidence_dir"] = str(volume.root)
        result["passed"] = (first, added, result["final"], result["price_updates"]) == (1000, 1050, 1050, 20)
        (self.root / "resultado_volumen.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
