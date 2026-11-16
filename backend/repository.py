"""SQLite repository, parameterized SQL, atomic imports and online backups."""
import json
import sqlite3
import uuid
from contextlib import contextmanager, closing
from pathlib import Path
from .schemas import now
from .security import canonical_url

class Conflict(ValueError):
    pass

class Repository:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT OR IGNORE INTO metadata VALUES ('schema','1');
                CREATE TABLE IF NOT EXISTS listings (
                  id INTEGER PRIMARY KEY, source TEXT NOT NULL, external_id TEXT,
                  canonical_url TEXT, data TEXT NOT NULL, detected_at TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS listing_external ON listings(source,external_id) WHERE external_id IS NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS listing_url ON listings(canonical_url) WHERE canonical_url IS NOT NULL;
                CREATE TABLE IF NOT EXISTS price_history(id INTEGER PRIMARY KEY,listing_id INTEGER NOT NULL REFERENCES listings(id),price TEXT,observed_at TEXT NOT NULL,origin TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS comparables(id INTEGER PRIMARY KEY,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS quotes(id INTEGER PRIMARY KEY,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS operations(id INTEGER PRIMARY KEY,listing_id INTEGER UNIQUE REFERENCES listings(id),data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS operation_history(id INTEGER PRIMARY KEY,operation_id INTEGER NOT NULL REFERENCES operations(id),data TEXT NOT NULL,at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS catalog(id INTEGER PRIMARY KEY,data TEXT NOT NULL UNIQUE);
                CREATE TABLE IF NOT EXISTS assessments(id INTEGER PRIMARY KEY,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,data TEXT NOT NULL);
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _listing(self, row):
        if row is None:
            raise KeyError('Anuncio no encontrado')
        return dict(json.loads(row['data']), id=row['id'], canonical_url=row['canonical_url'], detected_at=row['detected_at'])

    def listings(self):
        with self.db() as db:
            return [self._listing(r) for r in db.execute('SELECT * FROM listings ORDER BY id DESC')]

    def listing(self, item_id):
        with self.db() as db:
            data = self._listing(db.execute('SELECT * FROM listings WHERE id=?',(item_id,)).fetchone())
            data['history'] = [dict(r) for r in db.execute('SELECT price,observed_at,origin FROM price_history WHERE listing_id=? ORDER BY id',(item_id,))]
            return data

    def _save_listing(self, db, item, existing_id=None):
        data = item.model_dump(mode='json')
        data['source'] = data['source'].strip().lower()
        data['external_id'] = data['external_id'] or None
        url = canonical_url(data['url'])
        candidates = []
        if data['external_id']:
            candidates += list(db.execute('SELECT * FROM listings WHERE source=? AND external_id=?',(data['source'],data['external_id'])))
        if url:
            candidates += list(db.execute('SELECT * FROM listings WHERE canonical_url=?',(url,)))
        ids = {r['id'] for r in candidates}
        if existing_id:
            ids.add(existing_id)
        if len(ids) > 1:
            raise Conflict('Identificadores contradictorios: revisión manual requerida')
        old = None
        if ids:
            old = db.execute('SELECT * FROM listings WHERE id=?',(next(iter(ids)),)).fetchone()
            if old is None:
                raise KeyError('Anuncio no encontrado')
            prev = json.loads(old['data'])
            if (prev['brand'].casefold(),prev['model'].casefold()) != (data['brand'].casefold(),data['model'].casefold()):
                raise Conflict('La identidad coincide con otro vehículo; no se fusiona')
            if old['source'] != data['source']:
                raise Conflict('Una URL no puede cambiar de fuente sin revisión')
            if existing_id is None and prev['availability'] in ('withdrawn','sold'):
                data['availability'] = prev['availability']
            if existing_id is None:
                data['favorite'], data['notes'] = prev['favorite'], prev['notes']
            item_id = old['id']
        else:
            prev = None
            item_id = None
        observed = now()
        for field in data:
            if field != 'provenance' and data[field] not in (None, '', [], {}):
                data['provenance'].setdefault(field, 'aportado por usuario; no verificado automáticamente')
        payload = json.dumps(data,ensure_ascii=False)
        if old:
            db.execute('UPDATE listings SET source=?,external_id=?,canonical_url=?,data=? WHERE id=?',(data['source'],data['external_id'],url,payload,item_id))
        else:
            item_id = db.execute('INSERT INTO listings(source,external_id,canonical_url,data,detected_at) VALUES(?,?,?,?,?)',(data['source'],data['external_id'],url,payload,observed)).lastrowid
        if not prev or prev['price'] != data['price']:
            db.execute('INSERT INTO price_history(listing_id,price,observed_at,origin) VALUES(?,?,?,?)',(item_id,data['price'],observed,'registro local; no comprobación remota'))
        return {'id':item_id,'action':'updated' if old else 'inserted'}

    def save_listings(self, items):
        with self.db() as db:
            return [self._save_listing(db,item) for item in items]

    def update_listing(self, item_id, item):
        with self.db() as db:
            return self._save_listing(db,item,item_id)

    def rows(self, table):
        self._table(table)
        with self.db() as db:
            return [dict(json.loads(r['data']),id=r['id']) for r in db.execute(f'SELECT * FROM {table} ORDER BY id DESC')]

    def _table(self, table):
        if table not in ('comparables','quotes','operations','catalog','assessments'):
            raise ValueError('Tabla no permitida')

    def save(self, table, data, item_id=None):
        self._table(table)
        data = data.model_dump(mode='json') if hasattr(data,'model_dump') else dict(data)
        with self.db() as db:
            if data.get('listing_id') is not None and not db.execute('SELECT 1 FROM listings WHERE id=?',(data['listing_id'],)).fetchone():
                raise ValueError('El anuncio vinculado no existe')
            if table == 'operations':
                listing = self._listing(db.execute('SELECT * FROM listings WHERE id=?',(data['listing_id'],)).fetchone())
                data['detected_at'] = listing['detected_at']
                data['initial_price'] = self.listing(data['listing_id'])['history'][0]['price']
            raw = json.dumps(data,ensure_ascii=False)
            if item_id is not None:
                result = db.execute(f'UPDATE {table} SET data=? WHERE id=?',(raw,item_id))
                if not result.rowcount:
                    raise KeyError('Registro no encontrado')
            elif table == 'operations':
                try:
                    item_id = db.execute('INSERT INTO operations(listing_id,data) VALUES(?,?)',(data['listing_id'],raw)).lastrowid
                except sqlite3.IntegrityError as exc:
                    raise Conflict('El anuncio ya tiene una operación') from exc
            else:
                item_id = db.execute(f'INSERT INTO {table}(data) VALUES(?)',(raw,)).lastrowid
            if table == 'operations':
                db.execute('INSERT INTO operation_history(operation_id,data,at) VALUES(?,?,?)',(item_id,raw,now()))
            return dict(data,id=item_id)

    def operation_history(self,item_id):
        with self.db() as db:
            return [dict(data=json.loads(r['data']),at=r['at']) for r in db.execute('SELECT data,at FROM operation_history WHERE operation_id=? ORDER BY id',(item_id,))]

    def setting(self,key,default):
        with self.db() as db:
            row = db.execute('SELECT data FROM settings WHERE key=?',(key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_setting(self,key,data):
        with self.db() as db:
            db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data',(key,json.dumps(data)))

    def backup(self,directory):
        directory = Path(directory)
        directory.mkdir(parents=True,exist_ok=True)
        name = 'radar_' + now().replace(':','').replace('.','')[:22] + '_' + uuid.uuid4().hex[:8] + '.sqlite'
        with self.db() as src, closing(sqlite3.connect(directory/name)) as dest:
            src.backup(dest)
        return name

    def restore(self,directory,name):
        directory = Path(directory).resolve()
        path = (directory/name).resolve()
        if path.parent != directory or path.suffix != '.sqlite' or not path.is_file():
            raise ValueError('Copia inválida')
        # Validate read-only; sqlite online backup replaces pages transactionally.
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as source:
            if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Copia dañada')
            tables = {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'metadata','listings','operations','price_history','comparables','quotes','catalog','assessments','settings','operation_history'} <= tables:
                raise ValueError('No es una copia RadarCoches')
            if source.execute("SELECT value FROM metadata WHERE key='schema'").fetchone() != ('1',):
                raise ValueError('Versión incompatible')
            safety = self.backup(directory)
            with closing(sqlite3.connect(self.path)) as dest:
                source.backup(dest)
        return safety
