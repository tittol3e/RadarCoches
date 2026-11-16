import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from ingesta import BASE, ejecutar


class IngestaTest(unittest.TestCase):
    def test_rechazos_reejecucion_y_actualizacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'salida'
            first = ejecutar(BASE / 'datos/anuncios_demo.csv', output)
            self.assertEqual((first['leidos'], first['insertados'], first['rechazados']), (5, 3, 2))
            second = ejecutar(BASE / 'datos/anuncios_demo.csv', output)
            self.assertEqual((second['insertados'], second['sin_cambios']), (0, 3))
            update = Path(tmp) / 'update.csv'
            update.write_text('id,marca,modelo,anio,precio_eur,kilometros\nDEMO-001,Seat,Ibiza,2020,12000.25,66000\n', encoding='utf-8')
            third = ejecutar(update, output)
            self.assertEqual(third['actualizados'], 1)
            with closing(sqlite3.connect(output / 'radarcoches.sqlite')) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM anuncios').fetchone()[0], 3)
                self.assertEqual(db.execute("SELECT precio_centimos FROM anuncios WHERE id='DEMO-001'").fetchone()[0], 1200025)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM ejecuciones').fetchone()[0], 3)

    def test_cabecera_invalida_no_crea_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'bad.csv'
            source.write_text('id,marca\n1,Seat\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                ejecutar(source, Path(tmp) / 'out')
            self.assertFalse((Path(tmp) / 'out').exists())


if __name__ == '__main__':
    unittest.main()
