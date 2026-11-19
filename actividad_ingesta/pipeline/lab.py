"""Servicio local ejecutable incluso cuando Docker/dlt/DuckDB no están disponibles."""
import importlib.util
import json
import threading
import uuid
from datetime import timedelta
from pathlib import Path

from .apis import create_source_app
from .extractor import extract
from .generator import BASE_TIME, generate
from .storage import Storage


class Lab:
    _lock = threading.RLock()

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.store = Storage(self.root)

    def run(self, page_size=100, stop_after=None, stage="revision", revision=None, verify=False):
        from fastapi.testclient import TestClient

        with self._lock:
            rid = self.store.begin_run()
            before = self.store.summary()["counts"]
            previous_ads = {(ad["source"], ad["id"]) for ad in self.store.records()} if revision == 1 else set()
            try:
                extracted = 0
                if stage != "store":
                    for source in ("demo_a", "demo_b"):
                        with TestClient(create_source_app(self.root, source)) as client:
                            extracted += extract(client, self.store, source, page_size)
                delivered = self.store.drain(stop_after=stop_after) if stage != "extract" else 0
                after = self.store.summary()["counts"]
                new_records = [ad for ad in self.store.records() if (ad["source"], ad["id"]) not in previous_ads] if revision == 1 else []
                checks = {}
                if verify:
                    expected_ads = 10 if revision == 0 else 12
                    expected_events = expected_ads + (2 if revision >= 2 else 0)
                    checks["eventos_en_cola"] = after["source_changes"] == after["outbox"] == expected_events
                    if stage == "extract":
                        checks["cola_pendiente"] = after["pending"] == expected_events and after["ads"] == 0
                    else:
                        source_ads = [ad for name in ("demo_a", "demo_b") for ad in self.store.source_ads(name)]
                        checks["inventario"] = len(source_ads) == expected_ads and self.store.records() == source_ads
                        checks["historial"] = after["consumed"] == after["history"] == expected_events
                        checks["precios"] = after["price_updates"] == (2 if revision >= 2 else 0)
                        checks["cola_vacia"] = after["pending"] == 0
                self.store.end_run(rid, "success", dict(
                    stage=stage, revision=revision, extracted=extracted, delivered=delivered,
                    generated_total=after["source_changes"], ads_before=before["ads"], ads=after["ads"],
                    new_ads=after["ads"] - before["ads"], processed=after["consumed"] - before["consumed"],
                    price_updates=after["price_updates"] - before["price_updates"], transport="sqlite_local",
                    new_records=new_records, checks=checks,
                ))
            except Exception as exc:
                self.store.end_run(rid, "interrupted" if isinstance(exc, InterruptedError) else "failed", dict(error=type(exc).__name__))
                raise
            return self.summary()

    def run_revision(self, revision):
        with self._lock:
            self.prepare_revision(revision)
            return self.run(page_size=3, revision=revision)

    def demo_stage(self, stage):
        with self._lock:
            data = self.summary()
            if stage == "read":
                self.prepare_revision(0)
                return self.summary()
            if data["revision"] != 0:
                raise ValueError("Este paso requiere la revisión inicial de la práctica")
            if stage == "store" and not self.verified_stage(data, "extract", 0):
                raise ValueError("Extrae primero los eventos de las dos APIs")
            if self.verified_stage(data, stage, 0):
                return data
            return self.run(page_size=3, stage=stage, revision=0, verify=True)

    def demo_revision(self, revision):
        with self._lock:
            data = self.summary()
            if revision < data["revision"]:
                raise ValueError("Crea otra práctica para volver a una revisión inicial")
            previous_stage = "store" if revision == 1 else "revision"
            if not self.verified_stage(data, previous_stage, revision - 1):
                raise ValueError("Completa y verifica primero el paso anterior")
            if revision != 3 and self.verified_stage(data, "revision", revision):
                return data
            self.prepare_revision(revision)
            result = self.run(page_size=3, revision=revision, verify=True)
            if revision == 3 and all(result["runs"][0]["details"]["checks"].values()):
                self.replay()
            return self.summary()

    @staticmethod
    def verified_stage(data, stage, revision):
        for run in data["runs"]:
            details = run["details"] or {}
            if details.get("stage") == stage and details.get("revision") == revision:
                checks = details.get("checks")
                return run["status"] == "success" and checks and all(checks.values())
        return False

    def replay(self):
        rid = self.store.begin_run()
        before = self.store.summary()["counts"]
        records = self.store.records()
        history = self.store.history()
        try:
            with self.store.db() as db:
                events = [json.loads(row[0]) for row in db.execute("SELECT payload FROM outbox ORDER BY rowid")]
            for event in events:
                self.store.consume(event)
            after = self.store.summary()["counts"]
            passed = all(before[key] == after[key] for key in ("ads", "consumed", "history", "price_updates"))
            passed = passed and self.store.records() == records and self.store.history() == history
            self.store.end_run(rid, "success" if passed else "failed", dict(
                stage="replay", revision=3, received=len(events), ads_before=before["ads"],
                ads=after["ads"], processed=after["consumed"] - before["consumed"], passed=passed,
            ))
        except Exception as exc:
            self.store.end_run(rid, "failed", dict(stage="replay", error=type(exc).__name__))
            raise

    def source_preview(self, source):
        from fastapi.testclient import TestClient

        with TestClient(create_source_app(self.root, source)) as client:
            responses = {}
            for path in ("/health", "/ads", "/changes"):
                response = client.get(path, params={"page_size": 6} if path != "/health" else None)
                response.raise_for_status()
                responses[path] = dict(status=response.status_code, body=response.json())
        return responses

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
                    history=self.store.history(),
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
        result["id"] = volume.root.name
        result["passed"] = (first, added, result["final"], result["price_updates"]) == (1000, 1050, 1050, 20)
        (volume.root / "resultado_volumen.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
