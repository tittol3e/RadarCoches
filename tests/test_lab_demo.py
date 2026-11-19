import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from actividad_ingesta.pipeline.distributed import export_analytics
from actividad_ingesta.pipeline.lab import Lab
from backend.lab_demo import create_demo_router
from backend.main import create_app


def test_practice_stages_use_actual_sources_and_preserve_other_runs(tmp_path):
    with TestClient(create_app(tmp_path / "data", tmp_path / "backups")) as client:
        base = "/api/lab/practices"
        first_id = client.post(base, json={}).json()["id"]
        practice = f"{base}/{first_id}"

        assert client.post(practice + "/stage/store", json={}).status_code == 422
        prepared = client.post(practice + "/stage/read", json={}).json()
        assert prepared["counts"]["source_changes"] == 10
        assert prepared["records"] == []
        for source in ("demo_a", "demo_b"):
            data = client.get(practice + f"/sources/{source}").json()
            assert data["/health"]["body"] == {"status": "ok", "source": source, "synthetic": True}
            assert data["/ads"]["body"]["total"] == 5
            assert len(data["/changes"]["body"]["items"]) == 5

        extracted = client.post(practice + "/stage/extract", json={}).json()
        assert extracted["counts"]["pending"] == len(extracted["events"]) == 10
        assert extracted["records"] == []
        consumed = client.post(practice + "/stage/store", json={}).json()
        assert consumed["counts"]["consumed"] == len(consumed["records"]) == 10
        assert client.post(practice + "/revision/2", json={}).status_code == 422
        added = client.post(practice + "/revision/1", json={}).json()
        assert len(added["runs"][0]["details"]["new_records"]) == 2
        assert all(added["runs"][0]["details"]["checks"].values())

        updated = client.post(practice + "/revision/2", json={}).json()
        changes = [row for row in updated["history"] if row["kind"] == "updated"]
        assert len(changes) == 2
        assert all(row["old_price"] - row["new_price"] == 10_000 for row in changes)
        replayed = client.post(practice + "/revision/3", json={}).json()
        assert replayed["records"] == updated["records"]
        assert replayed["history"] == updated["history"]
        assert replayed["runs"][0]["details"]["received"] == 14
        assert replayed["runs"][0]["details"]["processed"] == 0
        assert replayed["runs"][0]["details"]["passed"]
        assert client.get("/api/listings").json() == []

        second_id = client.post(base, json={}).json()["id"]
        assert client.get(f"{base}/{second_id}").json()["counts"]["ads"] == 0
        assert {row["id"] for row in client.get(base).json()} == {first_id, second_id}
        report = client.get(practice + "/report")
        assert report.json() == replayed
        assert "attachment" in report.headers["content-disposition"]


def test_artifacts_are_read_from_fixed_paths_and_missing_parquet_is_reported(tmp_path):
    pytest.importorskip("duckdb")
    run_id = "a" * 32
    data_dir = tmp_path / "data"
    root = data_dir / "laboratorio_distribuido" / run_id
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    report = dict(passed=True, synthetic=True, mode="distributed", phase="completed", root="obsolete path")
    (evidence / f"{run_id}.json").write_text(json.dumps(report), encoding="utf-8")
    lab = Lab(root)
    for revision in (0, 1, 2):
        lab.run_revision(revision)
    export_analytics(root)

    app = FastAPI()
    app.include_router(create_demo_router(data_dir, evidence))
    with TestClient(app) as client:
        base = "/api/lab/distributed"
        assert client.get(base).json()[0]["id"] == run_id
        assert client.get(f"{base}/invalid/report").status_code == 404
        artifacts_url = f"{base}/{run_id}/artifacts"
        artifacts = client.get(artifacts_url).json()
        assert artifacts["duckdb"]["records"] == artifacts["parquet"]["records"]
        assert artifacts["duckdb"]["total"] == 12
        assert artifacts["duckdb"]["history_total"] == 14
        assert len(artifacts["duckdb"]["price_changes"]) == 2

        (root / "anuncios.parquet").rename(root / "anuncios.test.parquet")
        partial = client.get(artifacts_url).json()
        assert partial["duckdb"]["available"]
        assert partial["parquet"]["available"] is False
