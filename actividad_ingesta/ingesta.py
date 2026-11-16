"""Prototipo autónomo: CSV de anuncios -> validación -> SQLite y evidencias."""
import argparse
import csv
import hashlib
import io
import json
import sqlite3
import sys
import uuid
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = ('id', 'marca', 'modelo', 'anio', 'precio_eur', 'kilometros')
BASE = Path(__file__).resolve().parent


def normalizar(row):
    if None in row or any(row.get(k) is None for k in FIELDS):
        raise ValueError('Número de columnas incorrecto')
    result = {k: row[k].strip() for k in FIELDS}
    if any(not result[k] for k in FIELDS):
        raise ValueError('Campos obligatorios vacíos')
    try:
        result['anio'] = int(result['anio'])
        result['kilometros'] = int(result['kilometros'])
        price = Decimal(result['precio_eur'])
        if not price.is_finite() or price < 0 or price != price.quantize(Decimal('0.01')):
            raise ValueError('Precio inválido: use euros con hasta dos decimales')
        result['precio_centimos'] = int(price * 100)
        del result['precio_eur']
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError('Precio inválido') from exc
    if not 1886 <= result['anio'] <= datetime.now(timezone.utc).year + 1:
        raise ValueError('Año fuera de rango')
    if result['kilometros'] < 0:
        raise ValueError('Kilometraje negativo')
    return result


def ejecutar(source, output):
    payload = source.read_bytes()
    reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig'), newline=''), strict=True)
    if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) != set(FIELDS):
        raise ValueError('Cabecera requerida: ' + ','.join(FIELDS))
    output.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + uuid.uuid4().hex[:8]
    run = output / 'ejecuciones' / run_id
    run.mkdir(parents=True)
    (run / 'entrada.csv').write_bytes(payload)
    summary = dict(ejecucion=run_id, fuente=str(source.resolve()), sha256=hashlib.sha256(payload).hexdigest(),
                   leidos=0, insertados=0, actualizados=0, sin_cambios=0, rechazados=0)
    rejected = []
    seen = set()
    with closing(sqlite3.connect(output / 'radarcoches.sqlite')) as db, db:
        db.execute('''CREATE TABLE IF NOT EXISTS anuncios (
            id TEXT PRIMARY KEY, marca TEXT NOT NULL, modelo TEXT NOT NULL,
            anio INTEGER NOT NULL, precio_centimos INTEGER NOT NULL,
            kilometros INTEGER NOT NULL, ultima_ejecucion TEXT NOT NULL)''')
        db.execute('CREATE TABLE IF NOT EXISTS ejecuciones (id TEXT PRIMARY KEY, resumen_json TEXT NOT NULL)')
        for row in reader:
            summary['leidos'] += 1
            try:
                car = normalizar(row)
                if car['id'] in seen:
                    raise ValueError('ID duplicado dentro del lote')
                seen.add(car['id'])
            except ValueError as exc:
                rejected.append(dict(linea=reader.line_num, motivo=str(exc), datos=row))
                summary['rechazados'] += 1
                continue
            values = tuple(car[k] for k in ('id', 'marca', 'modelo', 'anio', 'precio_centimos', 'kilometros'))
            old = db.execute('SELECT id,marca,modelo,anio,precio_centimos,kilometros FROM anuncios WHERE id=?', (car['id'],)).fetchone()
            if old == values:
                summary['sin_cambios'] += 1
            else:
                db.execute('''INSERT INTO anuncios VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    marca=excluded.marca, modelo=excluded.modelo, anio=excluded.anio,
                    precio_centimos=excluded.precio_centimos, kilometros=excluded.kilometros,
                    ultima_ejecucion=excluded.ultima_ejecucion''', values + (run_id,))
                summary['insertados' if old is None else 'actualizados'] += 1
        db.execute('INSERT INTO ejecuciones VALUES (?,?)', (run_id, json.dumps(summary, ensure_ascii=False)))
    (run / 'rechazados.json').write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding='utf-8')
    (run / 'resumen.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada', type=Path, default=BASE / 'datos' / 'anuncios_demo.csv')
    parser.add_argument('--salida', type=Path, default=BASE / 'salida')
    args = parser.parse_args()
    try:
        print(json.dumps(ejecutar(args.entrada, args.salida), ensure_ascii=False, indent=2))
    except (OSError, ValueError, csv.Error, sqlite3.Error) as exc:
        print(f'Error de ingesta: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
