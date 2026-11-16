"""Router opcional de consultas DuckDB con lista cerrada, sin SQL arbitrario."""
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException


def create_lab_analytics_router(lab_root):
    root = Path(lab_root).resolve()
    router = APIRouter()

    @router.get("/api/lab/analytics")
    def analytics(query: Literal["counts", "prices", "history"] = "counts"):
        from actividad_ingesta.pipeline.distributed import query_analytics
        try:
            return query_analytics(root, query)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail={
                "code": "duckdb_unavailable", "message": str(exc),
                "synthetic": True, "executed": False,
            }) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail={
                "code": "analytics_query_failed",
                "message": "No se pudo consultar la base analítica local; no se han modificado datos.",
                "synthetic": True, "executed": False,
            }) from exc

    return router
