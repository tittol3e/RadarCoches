"""Extracción paginada con cursor, instantánea y reintentos limitados."""
import time

from .models import Change


def get_json(client, path, params, attempts=3):
    last = None
    for attempt in range(attempts):
        try:
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last = exc
            if attempt < attempts - 1:
                time.sleep(0.05 * (2 ** attempt))
    raise RuntimeError("Extracción fallida; cursor conservado y reintentos agotados") from last


def extract(client, store, source, page_size=100, after_page=None):
    since, until, page, count = store.cursor(source), None, 1, 0
    while True:
        params = dict(since=since, page=page, page_size=page_size)
        if until is not None:
            params["until"] = until
        data = get_json(client, "/changes", params)
        if data.get("synthetic") is not True or data.get("source") != source:
            raise ValueError("El laboratorio solo admite fuentes sintéticas identificadas")
        until = data["highwater"] if until is None else until
        events = [Change.model_validate(r).validated().model_dump(mode="json") for r in data["items"]]
        if any(e["seq"] <= since or e["seq"] > until for e in events):
            raise ValueError("Respuesta fuera de los límites del cursor")
        # El cursor de página solo avanza a eventos ya guardados duraderamente.
        # Usar since constante conserva el offset durante una misma extracción.
        high = max((e["seq"] for e in events), default=since)
        store.enqueue(events, source, high)
        count += len(events)
        if after_page:
            after_page(page)
        if not data.get("next_page"):
            store.enqueue([], source, until)
            break
        page += 1
    return count
