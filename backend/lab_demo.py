"""Prácticas locales aisladas y visor de informes distribuidos guardados."""
import json
import re
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from actividad_ingesta.pipeline.lab import Lab


RUN_ID = re.compile(r"[0-9a-f]{32}")


def create_demo_router(data_dir, evidence_dir):
    router = APIRouter(prefix="/api/lab")
    practice_root = data_dir / "laboratorio_practicas"

    def practice(run_id):
        if not RUN_ID.fullmatch(run_id) or not (practice_root / run_id / "laboratorio_sintetico.sqlite").is_file():
            raise HTTPException(404, "Práctica local no encontrada")
        return Lab(practice_root / run_id)

    def report(run_id):
        if not RUN_ID.fullmatch(run_id):
            raise HTTPException(404, "Informe distribuido no encontrado")
        path = evidence_dir / f"{run_id}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise HTTPException(404, "Informe distribuido no disponible") from exc
        if not isinstance(data, dict) or data.get("mode") != "distributed" or data.get("synthetic") is not True:
            raise HTTPException(404, "Informe distribuido no reconocido")
        return data

    @router.post("/practices")
    def new_practice():
        run_id = uuid4().hex
        Lab(practice_root / run_id)
        return {"id": run_id}

    @router.get("/practices")
    def saved_practices():
        runs = []
        for path in practice_root.glob("*/laboratorio_sintetico.sqlite"):
            if RUN_ID.fullmatch(path.parent.name):
                try:
                    saved = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
                except OSError:
                    continue
                runs.append(dict(id=path.parent.name, saved=saved))
        return sorted(runs, key=lambda row: row["saved"], reverse=True)

    @router.get("/practices/{run_id}")
    def practice_summary(run_id: str):
        return practice(run_id).summary()

    @router.get("/practices/{run_id}/report")
    def practice_report(run_id: str):
        return JSONResponse(practice(run_id).summary(), headers={
            "Content-Disposition": f'attachment; filename="practica-{run_id}.json"',
        })

    @router.post("/practices/{run_id}/stage/{stage}")
    def practice_stage(run_id: str, stage: Literal["read", "extract", "store"]):
        try:
            return practice(run_id).demo_stage(stage)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

    @router.post("/practices/{run_id}/revision/{revision}")
    def practice_revision(run_id: str, revision: Literal["1", "2", "3"]):
        try:
            return practice(run_id).demo_revision(int(revision))
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

    @router.get("/volume/{run_id}/report")
    def volume_report(run_id: str):
        from fastapi.responses import FileResponse

        path = data_dir / "laboratorio" / "volumen" / run_id / "resultado_volumen.json"
        if not RUN_ID.fullmatch(run_id) or not path.is_file():
            raise HTTPException(404, "Informe de volumen no disponible")
        return FileResponse(path, media_type="application/json", filename=f"volumen-{run_id}.json")

    @router.get("/practices/{run_id}/sources/{source}")
    def local_source(run_id: str, source: Literal["demo_a", "demo_b"]):
        lab = practice(run_id)
        try:
            return lab.source_preview(source)
        except Exception as exc:
            raise HTTPException(503, f"No se pudo leer la API local {source}") from exc

    @router.get("/distributed")
    def distributed_runs():
        runs = []
        for path in evidence_dir.glob("*.json"):
            if RUN_ID.fullmatch(path.stem):
                try:
                    data = report(path.stem)
                    saved = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
                except (HTTPException, OSError):
                    continue
                runs.append(dict(id=path.stem, saved=saved, passed=data.get("passed") is True,
                                 phase=data.get("phase")))
        return sorted(runs, key=lambda row: row["saved"], reverse=True)

    @router.get("/distributed/{run_id}/report")
    def distributed_report(run_id: str):
        return report(run_id)

    @router.get("/distributed/{run_id}/artifacts")
    def artifacts(run_id: str):
        from actividad_ingesta.pipeline.distributed import duckdb_module

        data = report(run_id)
        if data.get("passed") is not True or data.get("phase") != "completed":
            raise HTTPException(404, "Esta ejecución no tiene artefactos finales verificados")
        # Derivar la ruta del identificador. Los paths absolutos del informe son informativos.
        root = data_dir / "laboratorio_distribuido" / run_id
        result = {}
        columns = "source,id,version,marca,modelo,anio,kilometros,precio_centimos"
        for name, filename in (("duckdb", "analitica.duckdb"), ("parquet", "anuncios.parquet")):
            path = root / filename
            if not path.is_file():
                result[name] = dict(available=False, message=f"Archivo {filename} no disponible")
                continue
            try:
                duckdb = duckdb_module()
                with duckdb.connect(str(path) if name == "duckdb" else ":memory:", read_only=name == "duckdb") as db:
                    query = (f"SELECT {columns} FROM anuncios" if name == "duckdb"
                             else f"SELECT {columns} FROM read_parquet(?)")
                    params = [] if name == "duckdb" else [str(path)]
                    count = db.execute(f"SELECT COUNT(*) FROM ({query})", params).fetchone()[0]
                    rows = db.execute(query + " ORDER BY source,id LIMIT 100", params)
                    entry = dict(available=True, records=_rows(rows), total=count)
                    if name == "duckdb":
                        entry["history_total"] = db.execute("SELECT COUNT(*) FROM historial").fetchone()[0]
                        entry["history"] = _history(db)
                        entry["price_changes"] = _history(db, only_price_changes=True)
                    result[name] = entry
            except RuntimeError as exc:
                result[name] = dict(available=False, message=str(exc))
            except Exception:
                result[name] = dict(available=False, message=f"No se pudo leer {filename}")
        return result

    return router


def _rows(cursor):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _history(db, only_price_changes=False):
    where = "WHERE old_price IS NOT NULL AND old_price <> new_price" if only_price_changes else ""
    rows = _rows(db.execute(
        "SELECT event_id,source,id,version,old_price,new_price,payload "
        f"FROM historial {where} ORDER BY source,id,version LIMIT 100"
    ))
    for row in rows:
        event = json.loads(row.pop("payload"))
        row.update(kind=event["kind"], ad=event["ad"])
    return rows
