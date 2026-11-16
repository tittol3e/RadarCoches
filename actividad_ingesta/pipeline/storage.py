"""SQLite separado: fuentes simuladas, outbox durable y consumidor idempotente."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import Change, SyntheticAd


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class Storage:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "laboratorio_sintetico.sqlite"
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS source_ads(
              source TEXT, id TEXT, version INTEGER NOT NULL, payload TEXT NOT NULL,
              PRIMARY KEY(source,id));
            CREATE TABLE IF NOT EXISTS source_changes(
              seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
              source TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cursors(source TEXT PRIMARY KEY, seq INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox(
              event_id TEXT PRIMARY KEY, source TEXT NOT NULL, payload TEXT NOT NULL,
              delivered INTEGER NOT NULL DEFAULT 0, kafka_sent INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS ads(
              source TEXT, id TEXT, version INTEGER NOT NULL, payload TEXT NOT NULL,
              PRIMARY KEY(source,id));
            CREATE TABLE IF NOT EXISTS consumed(event_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS history(
              event_id TEXT PRIMARY KEY, source TEXT, id TEXT, version INTEGER,
              old_price INTEGER, new_price INTEGER, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(
              id INTEGER PRIMARY KEY AUTOINCREMENT, started TEXT DEFAULT CURRENT_TIMESTAMP,
              status TEXT NOT NULL, details TEXT);
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=20000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def put_source(self, raw):
        ad = SyntheticAd.model_validate(raw).model_dump(mode="json")
        with self.db() as db:
            old = db.execute("SELECT payload,version FROM source_ads WHERE source=? AND id=?",
                             (ad["source"], ad["id"])).fetchone()
            if old and old["payload"] == encode(ad):
                return False
            if old and ad["version_evento"] <= old["version"]:
                raise ValueError("Una modificación necesita una versión superior")
            event_id = hashlib.sha256(encode(ad).encode()).hexdigest()
            kind = "updated" if old else "created"
            db.execute("INSERT INTO source_ads VALUES (?,?,?,?) ON CONFLICT(source,id) DO UPDATE SET version=excluded.version,payload=excluded.payload",
                       (ad["source"], ad["id"], ad["version_evento"], encode(ad)))
            # seq se asigna dentro de la misma transacción que cambia el anuncio.
            cur = db.execute("INSERT INTO source_changes(event_id,source,payload) VALUES (?,?,?)",
                             (event_id, ad["source"], ""))
            event = dict(event_id=event_id, seq=cur.lastrowid, source=ad["source"], kind=kind, ad=ad)
            db.execute("UPDATE source_changes SET payload=? WHERE seq=?", (encode(event), cur.lastrowid))
        return True

    def source_ads(self, source):
        with self.db() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT payload FROM source_ads WHERE source=? ORDER BY id", (source,))]

    def highwater(self, source):
        with self.db() as db:
            return db.execute("SELECT COALESCE(MAX(seq),0) FROM source_changes WHERE source=?", (source,)).fetchone()[0]

    def changes(self, source, since, until, limit, offset=0):
        with self.db() as db:
            return [json.loads(r[0]) for r in db.execute(
                "SELECT payload FROM source_changes WHERE source=? AND seq>? AND seq<=? ORDER BY seq LIMIT ? OFFSET ?",
                (source, since, until, limit, offset))]

    def cursor(self, source):
        with self.db() as db:
            row = db.execute("SELECT seq FROM cursors WHERE source=?", (source,)).fetchone()
            return row[0] if row else 0

    def enqueue(self, events, source, cursor):
        validated = [Change.model_validate(e).validated().model_dump(mode="json") for e in events]
        if any(e["source"] != source for e in validated):
            raise ValueError("Mezcla de fuentes en la extracción")
        with self.db() as db:
            for e in validated:
                db.execute("INSERT OR IGNORE INTO outbox(event_id,source,payload) VALUES (?,?,?)", (e["event_id"], source, encode(e)))
            # Cursor y outbox atómicos: ningún evento se pierde tras un reinicio.
            db.execute("INSERT INTO cursors VALUES (?,?) ON CONFLICT(source) DO UPDATE SET seq=MAX(seq,excluded.seq)", (source, cursor))

    def consume(self, event):
        event = Change.model_validate(event).validated().model_dump(mode="json")
        ad, eid = event["ad"], event["event_id"]
        expected = hashlib.sha256(encode(ad).encode()).hexdigest()
        if expected != eid:
            raise ValueError("Huella de evento inválida")
        with self.db() as db:
            if db.execute("SELECT 1 FROM consumed WHERE event_id=?", (eid,)).fetchone():
                return False
            old = db.execute("SELECT payload,version FROM ads WHERE source=? AND id=?", (ad["source"], ad["id"])).fetchone()
            existing_version = db.execute("SELECT event_id FROM history WHERE source=? AND id=? AND version=?",
                                          (ad["source"], ad["id"], ad["version_evento"])).fetchone()
            if existing_version and existing_version[0] != eid:
                raise ValueError("Dos contenidos distintos para la misma versión")
            db.execute("INSERT INTO consumed VALUES (?)", (eid,))
            prior = db.execute("SELECT new_price FROM history WHERE source=? AND id=? AND version<? ORDER BY version DESC LIMIT 1",
                               (ad["source"], ad["id"], ad["version_evento"])).fetchone()
            old_price = prior[0] if prior else None
            db.execute("INSERT INTO history VALUES (?,?,?,?,?,?,?)", (eid, ad["source"], ad["id"], ad["version_evento"], old_price, ad["precio_centimos"], encode(event)))
            # Un evento tardío también pertenece al historial. Reparar el precio
            # anterior del siguiente evento, sin retroceder el estado actual.
            next_version = db.execute("SELECT MIN(version) FROM history WHERE source=? AND id=? AND version>?",
                                      (ad["source"], ad["id"], ad["version_evento"])).fetchone()[0]
            if next_version is not None:
                db.execute("UPDATE history SET old_price=? WHERE source=? AND id=? AND version=?",
                           (ad["precio_centimos"], ad["source"], ad["id"], next_version))
            if old and old["version"] >= ad["version_evento"]:
                return False
            db.execute("INSERT INTO ads VALUES (?,?,?,?) ON CONFLICT(source,id) DO UPDATE SET version=excluded.version,payload=excluded.payload",
                       (ad["source"], ad["id"], ad["version_evento"], encode(ad)))
        return True

    def drain(self, stop_after=None):
        with self.db() as db:
            rows = db.execute("SELECT event_id,payload FROM outbox WHERE delivered=0 ORDER BY rowid").fetchall()
        count = 0
        for row in rows:
            if stop_after is not None and count >= stop_after:
                raise InterruptedError("Interrupción de prueba tras consumo parcial")
            self.consume(json.loads(row["payload"]))
            with self.db() as db:
                db.execute("UPDATE outbox SET delivered=1 WHERE event_id=?", (row["event_id"],))
            count += 1
        return count

    def records(self):
        with self.db() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT payload FROM ads ORDER BY source,id")]

    def begin_run(self):
        with self.db() as db:
            return db.execute("INSERT INTO runs(status) VALUES ('running')").lastrowid

    def end_run(self, run_id, status, details):
        with self.db() as db:
            db.execute("UPDATE runs SET status=?,details=? WHERE id=?", (status, encode(details), run_id))

    def summary(self):
        with self.db() as db:
            counts = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                      for name in ("ads", "source_ads", "outbox", "history", "consumed")}
            counts["pending"] = db.execute("SELECT COUNT(*) FROM outbox WHERE delivered=0").fetchone()[0]
            counts["price_updates"] = db.execute("SELECT COUNT(*) FROM history WHERE old_price IS NOT NULL AND old_price!=new_price").fetchone()[0]
            events = [json.loads(r[0]) for r in db.execute("SELECT payload FROM outbox ORDER BY rowid DESC LIMIT 30")]
            runs = [dict(r) for r in db.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 20")]
            for row in runs:
                row["details"] = json.loads(row["details"]) if row["details"] else None
            return dict(counts=counts, events=events, runs=runs,
                        cursors={r[0]: r[1] for r in db.execute("SELECT source,seq FROM cursors")})
