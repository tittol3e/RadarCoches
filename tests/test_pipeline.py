"""Pruebas locales ejecutables con unittest y también recopilables por pytest."""
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from actividad_ingesta.pipeline.apis import create_source_app
from actividad_ingesta.pipeline.extractor import extract
from actividad_ingesta.pipeline.generator import BASE_TIME, generate
from actividad_ingesta.pipeline.lab import Lab
from actividad_ingesta.pipeline.storage import Storage, encode


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lab = Lab(self.root)

    def test_generator_deterministic_coherent(self):
        a = generate("demo_a", 1)
        self.assertEqual(a, generate("demo_a", 1))
        self.assertNotEqual(a, generate("demo_b", 1))
        self.assertTrue(a["synthetic"])
        self.assertLessEqual(a["anio"], 2025)
        self.assertGreater(a["precio_centimos"], 0)

    def test_revisions_10_12_12_12_with_verified_updates(self):
        original = {}
        totals = []
        for revision in range(4):
            result = self.lab.run_revision(revision)
            totals.append(result["counts"]["ads"])
            if revision == 1:
                original = {r["id"]: r["precio_centimos"] for r in self.lab.store.records()}
            if revision == 2:
                changed = [r for r in self.lab.store.records() if r["precio_centimos"] != original[r["id"]]]
                self.assertEqual(len(changed), 2)
                for r in changed:
                    self.assertEqual(r["precio_centimos"], original[r["id"]] - 10000)
        self.assertEqual(totals, [10, 12, 12, 12])
        self.assertEqual(result["counts"]["price_updates"], 2)
        self.assertEqual(result["counts"]["history"], 14)

    def test_revision_sequence_validation(self):
        with self.assertRaises(ValueError):
            self.lab.run_revision(2)
        with self.assertRaises(ValueError):
            self.lab.run_revision(-1)

    def test_source_preparation_does_not_consume_local_events(self):
        self.lab.prepare_revision(0)
        summary = self.lab.summary()
        self.assertEqual(summary["counts"]["source_ads"], 10)
        self.assertEqual(summary["counts"]["ads"], 0)
        self.assertEqual(summary["counts"]["outbox"], 0)

    def test_revision_repeated_does_not_duplicate(self):
        self.lab.run_revision(0)
        self.lab.run_revision(0)
        self.assertEqual(self.lab.summary()["counts"]["history"], 10)

    def test_api_pagination_and_source_isolation(self):
        self.lab.run_revision(0)
        with TestClient(create_source_app(self.root, "demo_a")) as client:
            first = client.get("/ads?page_size=2").json()
            second = client.get("/ads?page=2&page_size=2").json()
            self.assertEqual(first["total"], 5)
            self.assertEqual(len(first["items"]), 2)
            self.assertTrue(all(r["source"] == "demo_a" for r in first["items"]))
            self.assertTrue({r["id"] for r in first["items"]}.isdisjoint(r["id"] for r in second["items"]))

    def test_api_date_filter(self):
        self.lab.run_revision(0)
        with TestClient(create_source_app(self.root, "demo_a")) as client:
            data = client.get("/ads", params={"updated_since": (BASE_TIME + timedelta(seconds=4)).isoformat()}).json()
            self.assertEqual(len(data["items"]), 2)
            naive = client.get("/ads", params={"updated_since": "2026-01-01T00:00:04"})
            self.assertEqual(naive.status_code, 200)
            self.assertEqual(len(naive.json()["items"]), 2)

    def test_api_input_validation(self):
        with TestClient(create_source_app(self.root, "demo_b")) as client:
            for path in ("/ads?page=0", "/ads?page_size=501", "/changes?since=-1", "/ads?updated_since=invalid"):
                self.assertEqual(client.get(path).status_code, 422)
            self.assertEqual(client.get("/health").json()["synthetic"], True)

    def test_change_snapshot_survives_new_events_between_pages(self):
        for n in range(1, 6):
            self.lab.store.put_source(generate("demo_a", n))
        with TestClient(create_source_app(self.root, "demo_a")) as client:
            def append(page):
                if page == 1:
                    self.lab.store.put_source(generate("demo_a", 6))
            extracted = extract(client, self.lab.store, "demo_a", page_size=2, after_page=append)
            self.assertEqual(extracted, 5)
            self.lab.store.drain()
            self.assertEqual(len(self.lab.store.records()), 5)
            self.assertEqual(extract(client, self.lab.store, "demo_a", page_size=2), 1)
        self.lab.store.drain()
        self.assertEqual(len(self.lab.store.records()), 6)

    def test_interruption_after_page_resumes_without_loss(self):
        for n in range(1, 8):
            self.lab.store.put_source(generate("demo_a", n))
        with TestClient(create_source_app(self.root, "demo_a")) as client:
            def stop(page):
                raise InterruptedError("stop")
            with self.assertRaises(InterruptedError):
                extract(client, self.lab.store, "demo_a", page_size=2, after_page=stop)
            self.assertEqual(self.lab.store.summary()["counts"]["outbox"], 2)
        restarted = Lab(self.root)
        result = restarted.run(page_size=2)
        self.assertEqual(result["counts"]["ads"], 7)
        self.assertEqual(result["counts"]["history"], 7)

    def test_consumer_interruption_resume_and_persistent_state(self):
        for n in range(1, 11):
            self.lab.store.put_source(generate("demo_a", n))
        with self.assertRaises(InterruptedError):
            self.lab.run(stop_after=3)
        before = self.lab.summary()
        self.assertEqual(before["counts"]["ads"], 3)
        self.assertEqual(before["counts"]["pending"], 7)
        self.assertEqual(before["runs"][0]["status"], "interrupted")
        final = Lab(self.root).run()
        self.assertEqual(final["counts"]["ads"], 10)
        self.assertEqual(final["counts"]["history"], 10)

    def test_replayed_and_out_of_order_events(self):
        self.lab.run_revision(0)
        with self.lab.store.db() as db:
            old = json.loads(db.execute("SELECT payload FROM outbox ORDER BY rowid LIMIT 1").fetchone()[0])
            db.execute("UPDATE outbox SET delivered=0")
        self.lab.run_revision(1)
        self.lab.run_revision(2)
        self.assertFalse(self.lab.store.consume(old))
        self.lab.store.drain()
        summary = self.lab.summary()
        self.assertEqual(summary["counts"]["ads"], 12)
        self.assertEqual(summary["counts"]["history"], 14)

    def test_late_event_preserves_complete_history_without_state_regression(self):
        self.lab.prepare_revision(0)
        self.lab.prepare_revision(1)
        self.lab.prepare_revision(2)
        with self.lab.store.db() as db:
            events = [json.loads(r[0]) for r in db.execute("SELECT payload FROM source_changes WHERE source='demo_a' ORDER BY seq")]
        old = events[0]
        new = next(e for e in events if e["ad"]["id"] == old["ad"]["id"] and e["ad"]["version_evento"] == 2)
        self.assertTrue(self.lab.store.consume(new))
        self.assertFalse(self.lab.store.consume(old))
        record = self.lab.store.records()[0]
        self.assertEqual(record["version_evento"], 2)
        with self.lab.store.db() as db:
            history = db.execute("SELECT version,old_price,new_price FROM history ORDER BY version").fetchall()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[1]["old_price"], old["ad"]["precio_centimos"])
        self.assertEqual(history[1]["new_price"], new["ad"]["precio_centimos"])

    def test_conflicting_same_version_is_rejected(self):
        self.lab.run_revision(0)
        with self.lab.store.db() as db:
            event = json.loads(db.execute("SELECT payload FROM outbox LIMIT 1").fetchone()[0])
        event["ad"]["precio_centimos"] += 100
        event["event_id"] = hashlib.sha256(encode(event["ad"]).encode()).hexdigest()
        with self.assertRaises(ValueError):
            self.lab.store.consume(event)

    def test_external_error_preserves_cursor_and_outbox(self):
        self.lab.run_revision(0)
        before = self.lab.summary()
        class Broken:
            calls = 0
            def get(self, *args, **kwargs):
                self.calls += 1
                raise OSError("network unavailable")
        client = Broken()
        with self.assertRaises(RuntimeError):
            extract(client, self.lab.store, "demo_a")
        self.assertEqual(client.calls, 3)
        after = self.lab.summary()
        self.assertEqual(before["counts"], after["counts"])
        self.assertEqual(before["cursors"], after["cursors"])

    def test_schema_rejects_real_data_and_tampered_events(self):
        self.lab.run_revision(0)
        with self.lab.store.db() as db:
            event = json.loads(db.execute("SELECT payload FROM outbox LIMIT 1").fetchone()[0])
        event["ad"]["synthetic"] = False
        with self.assertRaises(ValueError):
            self.lab.store.consume(event)
        event["ad"]["synthetic"] = True
        event["ad"]["precio_centimos"] += 100
        with self.assertRaises(ValueError):
            self.lab.store.consume(event)

    def test_same_id_different_source_remains_distinct(self):
        a = generate("demo_a", 1)
        b = generate("demo_b", 1)
        a["id"] = b["id"] = "DEMO-same"
        self.lab.store.put_source(a)
        self.lab.store.put_source(b)
        self.assertEqual(self.lab.run()["counts"]["ads"], 2)

    def test_tampered_extract_does_not_commit_cursor(self):
        self.lab.run_revision(0)
        with self.lab.store.db() as db:
            event = json.loads(db.execute("SELECT payload FROM outbox LIMIT 1").fetchone()[0])
        before = self.lab.store.cursor("demo_a")
        event["ad"]["precio_centimos"] += 1
        with self.assertRaises(ValueError):
            self.lab.store.enqueue([event], "demo_a", 99999)
        self.assertEqual(self.lab.store.cursor("demo_a"), before)

    def test_volume_1000_50_20(self):
        result = self.lab.volume_demo()
        self.assertTrue(result["passed"])
        self.assertEqual((result["initial"], result["after_add"], result["final"], result["price_updates"]), (1000, 1050, 1050, 20))
        self.assertEqual(self.lab.summary()["counts"]["ads"], 0)

    def test_authorized_api_urls(self):
        from actividad_ingesta.pipeline.distributed import approved_api
        with patch.dict("os.environ", {"RADAR_AUTHORIZED_API_HOSTS": ""}):
            self.assertEqual(approved_api("http://127.0.0.1:8771/"), "http://127.0.0.1:8771")
            for url in ("https://example.org", "ftp://localhost", "http://user:password@localhost", "http://localhost/?key=x", "http://localhost/#x", "http://169.254.169.254"):
                with self.assertRaises(ValueError):
                    approved_api(url)
        with patch.dict("os.environ", {"RADAR_AUTHORIZED_API_HOSTS": "example.org"}):
            self.assertEqual(approved_api("https://example.org"), "https://example.org")
            with self.assertRaises(ValueError):
                approved_api("http://example.org")

    def test_analytics_query_is_whitelisted_before_dependency_access(self):
        from actividad_ingesta.pipeline.distributed import query_analytics
        with patch("actividad_ingesta.pipeline.distributed.duckdb_module") as module:
            with self.assertRaises(ValueError):
                query_analytics(self.root, "DROP TABLE anuncios")
            module.assert_not_called()

    def test_consumer_groups_do_not_share_offsets_across_databases(self):
        from actividad_ingesta.pipeline.distributed import consumer_group
        self.assertEqual(consumer_group(self.root), consumer_group(self.root))
        self.assertNotEqual(consumer_group(self.root), consumer_group(self.root / "other"))

    def test_optional_analytics_endpoint_returns_clear_503_and_rejects_sql(self):
        from fastapi import FastAPI
        from backend.lab_analytics import create_lab_analytics_router
        app = FastAPI()
        app.include_router(create_lab_analytics_router(self.root))
        with TestClient(app) as client:
            with patch("actividad_ingesta.pipeline.distributed.duckdb_module", side_effect=RuntimeError("DuckDB no instalado")):
                result = client.get("/api/lab/analytics")
                self.assertEqual(result.status_code, 503)
                self.assertEqual(result.json()["detail"]["code"], "duckdb_unavailable")
                self.assertFalse(result.json()["detail"]["executed"])
            self.assertEqual(client.get("/api/lab/analytics", params={"query": "SELECT * FROM ads"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
