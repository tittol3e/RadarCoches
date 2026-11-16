"""Dos APIs con inventarios DEMO independientes y cambios paginados estables."""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query

from .storage import Storage


def create_source_app(root, source: Literal["demo_a", "demo_b"]):
    if source not in ("demo_a", "demo_b"):
        raise ValueError("Fuente sintética desconocida")
    store = Storage(root)
    app = FastAPI(title=f"DEMO / DATOS SINTÉTICOS — {source}")

    @app.get("/health")
    def health():
        return dict(status="ok", source=source, synthetic=True)

    @app.get("/ads")
    def ads(page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500),
            updated_since: datetime | None = None):
        rows = store.source_ads(source)
        if updated_since:
            if updated_since.tzinfo is None:
                updated_since = updated_since.replace(tzinfo=timezone.utc)
            rows = [r for r in rows if datetime.fromisoformat(r["actualizado"]) >= updated_since]
        start = (page - 1) * page_size
        return dict(synthetic=True, source=source, total=len(rows), page=page,
                    page_size=page_size, items=rows[start:start + page_size])

    @app.get("/changes")
    def changes(since: int = Query(0, ge=0), until: int | None = Query(None, ge=0),
                page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500)):
        snapshot = store.highwater(source) if until is None else until
        items = store.changes(source, since, snapshot, page_size, (page - 1) * page_size)
        return dict(synthetic=True, source=source, highwater=snapshot, page=page,
                    page_size=page_size, items=items, next_page=page + 1 if len(items) == page_size else None)

    return app


ROOT = Path(os.environ.get("RADAR_LAB_DIR", Path(__file__).resolve().parents[2] / "data" / "laboratorio"))
# Factories avoid filesystem mutations merely from importing this module.
def source_a():
    return create_source_app(ROOT, "demo_a")


def source_b():
    return create_source_app(ROOT, "demo_b")
