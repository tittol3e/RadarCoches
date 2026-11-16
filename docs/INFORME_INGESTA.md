# Informe de ingesta — RadarCoches

Fecha de ejecución local: 16 de noviembre de 2026. Todos los vehículos de este módulo son **DEMO / DATOS SINTÉTICOS**. No son anuncios disponibles, comparables reales ni precios de mercado.

## Estado comprobado

El circuito local ejecutado es:

`Generador reproducible → dos APIs FastAPI en proceso → extracción incremental propia → outbox SQLite → consumidor idempotente → SQLite analítico de laboratorio`.

Las dos APIs se han probado mediante TestClient, sin sockets HTTP. Este modo es funcional y persistente; **no ejecuta dlt, Kafka, DuckDB ni Parquet**. La interfaz y los JSON de evidencias declaran `mode=local_sqlite` y `kafka_executed=false`, `dlt_executed=false`, `duckdb_executed=false`.

La integración distribuida tiene código independiente en `actividad_ingesta/pipeline/distributed.py`:

`APIs HTTP → dlt incremental → DuckDB landing durable → outbox SQLite → Kafka → consumidor → SQLite journal → DuckDB analítico + Parquet`.

Este segundo circuito **está implementado, pero pendiente de ejecución y validación integral**. No se afirma que funcione en este Windows: faltan sus dependencias y Docker no tiene motor disponible. La capa landing guarda los eventos cargados por dlt antes del relay, por lo que el cursor de dlt puede confirmarse sin perder la posibilidad de reenviar. Se relee el landing completo y la outbox deduplica por event_id.

## Recuperación del trabajo anterior

Se encontraron `actividad_ingesta/ingesta.py`, `test_ingesta.py` y un CSV sintético. Se conservaron copias byte a byte de los dos programas en `actividad_ingesta/legacy_recuperado/*.original` antes de corregirlos.

Las pruebas originales se ejecutaron: inicialmente una de dos falló al limpiar un directorio temporal en Windows. La causa era una conexión SQLite sin cerrar: `with sqlite3.connect(...)` confirma/deshace transacciones, pero no cierra la conexión. Se añadió `contextlib.closing` tanto en el programa como en la prueba. Tras la corrección **las dos pruebas originales pasan**. No se han recuperado ni confirmado las antiguas trece pruebas mencionadas en la especificación.

## Datos y separación

- Base exclusiva: `data/laboratorio/laboratorio_sintetico.sqlite`.
- Cada demostración CLI utiliza un subdirectorio nuevo `demostraciones/<uuid>`.
- Cada ejercicio de volumen utiliza un subdirectorio nuevo `volumen/<uuid>`.
- Las ejecuciones no borran ejercicios anteriores.
- Los esquemas exigen `synthetic=true` y fuente `demo_a` o `demo_b`.
- No existe un puente de estos anuncios al Radar real.
- Los IDs, características y precios se generan con semilla estable. Los precios son ficticios por diseño.

## Control incremental y recuperación

Cada fuente conserva un registro append-only de cambios con secuencia creciente. `/changes?since=...&until=...&page=...&page_size=...` pagina una instantánea con límite superior fijo; un alta concurrente se recoge en la siguiente extracción. La API `/ads` también ofrece paginación y `updated_since` (fechas sin zona se interpretan UTC).

La extracción valida esquema, origen y huella SHA-256 antes de confirmar. Por página, la outbox y el cursor se guardan en una transacción SQLite. Ante una interrupción se vuelve a extraer desde la última página confirmada. Tres intentos con espera exponencial limitada gestionan fallos externos; al agotarlos se conserva el cursor confirmado.

El consumidor identifica anuncios por `(source,id)` y eventos por su huella. Guarda versiones, evita retroceder el estado actual y conserva incluso eventos tardíos en el historial. Un evento tardío reconstruye la relación con el siguiente precio conocido por número de versión. Dos contenidos diferentes para la misma versión se rechazan. Confirmar la entrega después del commit permite repetir un evento si el proceso cae entre ambos pasos. Las ejecuciones registran inicio, éxito, error e interrupción controlada. Un cierre abrupto puede dejar una ejecución marcada `running`, pero la siguiente ejecución recupera la outbox pendiente.

En Kafka se confirma el offset de cada evento solo después de guardar y exportar. El grupo de consumo predeterminado se deriva de la ruta de la base: se conserva tras un reinicio y cambia al usar otra base, evitando reutilizar offsets ajenos. Los eventos del mismo anuncio llevan la misma clave Kafka. La garantía buscada es entrega al menos una vez con consumidor idempotente; no se afirma una transacción distribuida exactamente una vez. El procesamiento distribuido y su comportamiento ante fallos todavía requieren las pruebas reales indicadas abajo.

## Resultados ejecutados

Se ejecutaron **23 pruebas nuevas** en `tests/test_pipeline.py`, con resultado **OK** (15,275 segundos), además de las **2 pruebas originales corregidas**, también **OK** (0,043 segundos). `actividad_ingesta/evidencias/pruebas_resultado.json` registra el código de salida real 0 de ambos intérpretes.

| Ejercicio local | Resultado comprobado |
|---|---|
| Revisión 0: cinco anuncios por API | 10 únicos |
| Revisión 1: un alta por API | 12 únicos |
| Revisión 2: precio de un anuncio por API | 12 únicos; ambos precios disminuyen exactamente 100 € sintéticos |
| Revisión 3: repetición sin cambios | 12 únicos; 14 eventos históricos en total |
| Volumen inicial | 1.000 únicos |
| Volumen: 50 altas | 1.050 únicos |
| Volumen: 20 actualizaciones | 1.050 únicos; 20 cambios de precio |
| Interrupción después de una página | Reinicio sin pérdida ni duplicados |
| Interrupción tras tres consumos | Siete pendientes; reinicio completa diez |
| Eventos repetidos y desordenados | Sin duplicación ni retroceso del estado |
| Error externo | Tres intentos; cursor y datos conservados |
| Alta concurrente entre páginas | Instantánea de cinco; alta sexta en la siguiente ingesta |
| Evento alterado | Rechazado antes de confirmar cursor |
| Identificador igual, distinta fuente | Dos anuncios independientes |
| Eventos tardíos | Se conserva todo el historial sin retroceder la versión actual |
| Conflicto de contenido en una versión | Rechazado con rollback |
| Autorización de APIs | Solo localhost o host HTTPS expresamente autorizado; sin credenciales en URL ni redirecciones |
| Grupo de consumo | Mismo directorio conserva identidad; directorios diferentes no comparten grupo |
| Consulta analítica web | Lista cerrada de tres consultas; SQL arbitrario rechazado; 503 claro cuando falta DuckDB |

Evidencias persistidas:

- `data/laboratorio/resultado_revisiones.json`.
- `data/laboratorio/resultado_volumen.json`.
- `actividad_ingesta/evidencias/revisiones.txt`.
- `actividad_ingesta/evidencias/pruebas_pipeline.txt`, `pruebas_recuperadas.txt` y `pruebas_resultado.json`.
- Bases SQLite de cada ejercicio, con anuncios, eventos, historial, cursores y ejecuciones.

El intérprete informó de una advertencia de obsolescencia de Starlette sobre el uso de httpx en TestClient. No fue un fallo. El código usa FastAPI/TestClient y httpx disponibles en la caché local; la migración a httpx2 debe verificarse al actualizar dependencias.

## Comandos locales reproducibles

Desde la raíz RadarCoches:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_pipeline.py -v
.\.venv\Scripts\python.exe -m unittest discover -s actividad_ingesta -p test_ingesta.py -v
.\.venv\Scripts\python.exe -m actividad_ingesta.pipeline demo
.\.venv\Scripts\python.exe -m actividad_ingesta.pipeline volume
.\.venv\Scripts\python.exe -m actividad_ingesta.pipeline status
```

La demostración completa CLI crea un espacio nuevo en cada llamada; repetirla vuelve a comprobar 10/12/12/12. Los botones de revisión de la interfaz mantienen un ejercicio persistente; repetir una revisión anterior no revierte datos.

## Puesta en marcha distribuida pendiente

Estos comandos no se han podido validar en este equipo. Requieren que el usuario ejecute el proyecto en un entorno con red y motor Docker disponible. No instalan nada global:

```powershell
.\.venv\Scripts\python.exe -m pip install -r actividad_ingesta/requirements-bigdata.txt
docker compose -f actividad_ingesta/docker-compose.yml up -d
```

Utilizar un directorio nuevo para la prueba distribuida, separado del ejercicio local. Preparar exclusivamente las fuentes, sin consumidor local:

```powershell
$env:RADAR_LAB_DIR = "$PWD/data/laboratorio-distribuido"
.\.venv\Scripts\python.exe -m actividad_ingesta.pipeline simulate --revision 0 --root data/laboratorio-distribuido
```

Configurar `RADAR_LAB_DIR` con esa misma ruta en cada terminal de API. Abrir dos terminales para las APIs:

```powershell
.\.venv\Scripts\python.exe -m uvicorn actividad_ingesta.pipeline.apis:source_a --factory --host 127.0.0.1 --port 8771
.\.venv\Scripts\python.exe -m uvicorn actividad_ingesta.pipeline.apis:source_b --factory --host 127.0.0.1 --port 8772
```

Después ejecutar secuencialmente:

```powershell
.\.venv\Scripts\python.exe -m actividad_ingesta.pipeline extract-dlt --root data/laboratorio-distribuido
.\.venv\Scripts\python.exe -m actividad_ingesta.pipeline publish --root data/laboratorio-distribuido
.\.venv\Scripts\python.exe -m actividad_ingesta.pipeline consume --root data/laboratorio-distribuido
.\.venv\Scripts\python.exe -m actividad_ingesta.pipeline query --query counts --root data/laboratorio-distribuido
.\.venv\Scripts\python.exe -m actividad_ingesta.pipeline query --query history --root data/laboratorio-distribuido
```

Las salidas previstas son `landing.duckdb`, `analitica.duckdb` y `anuncios.parquet` dentro de `data/laboratorio-distribuido`. Para avanzar cada revisión, ejecutar `simulate --revision 1`, después 2 y 3, siempre con ese `--root`, y repetir extracción/publicación/consumo/consulta. No se han generado archivos con extensión Parquet falsa como sustitución. Los puertos Docker y APIs se enlazan exclusivamente a localhost.

Para una API externa posterior se debe implementar el contrato `/changes`, autorizar explícitamente su host HTTPS mediante `RADAR_AUTHORIZED_API_HOSTS` y mantener su carácter sintético dentro del laboratorio. Redirecciones HTTP están desactivadas. El módulo no recupera anuncios reales ni elude restricciones de portales.

## Bloqueos y pruebas que faltan

El primer intento de instalación desde PyPI devolvió WinError 10013 (socket no permitido). La instalación offline de `requirements-bigdata.txt` confirma que no hay dlt disponible en la caché. Docker dispone de cliente, pero `docker version` no encuentra el motor. Por ello quedan pendientes:

1. Resolución y fijación de versiones efectivamente compatibles de dlt, DuckDB y kafka-python.
2. Inicio del broker real y creación del tema.
3. Ejecución HTTP real de ambas APIs.
4. Repetir revisiones y volumen por dlt/Kafka/DuckDB, comprobando consultas DuckDB y lectura del Parquet generado.
5. Fallos reales del productor, broker y consumidor; confirmar offsets y reinicio sin pérdida.

La actividad académica completa solicitada **no debe considerarse terminada** hasta superar esas pruebas distribuidas.

## Punto exacto para continuar la integración distribuida

No es necesario repetir la reconstrucción ni las pruebas locales que ya pasan. Primero resolver la instalación de dependencias dentro de `.venv` y arrancar Docker Desktop por el procedimiento normal del usuario. No se han solicitado privilegios elevados ni instalado software global. Después:

1. Crear un directorio nuevo de laboratorio distribuido y ejecutar `simulate --revision 0`, tal como se indica arriba. No usar el comando `revision` para preparar esta prueba: también consumiría localmente y falsearía la evidencia sobre Kafka.
2. Iniciar ambas APIs HTTP, verificar `/health` y comprobar cinco anuncios por API.
3. Iniciar el broker y ejecutar `extract-dlt`, `publish`, `consume` y consultas. Confirmar 10 únicos en DuckDB y lectura real del archivo Parquet.
4. Repetir el circuito con `simulate --revision 1`, 2 y 3, comparando los precios exactos y totales 12/12/12.
5. Repetir el ejercicio de volumen a través de la ruta distribuida: el comando `volume` actual demuestra exclusivamente la ruta local. Para esta prueba se necesita preparar 500 anuncios por fuente, luego 25 nuevos por fuente y finalmente 10 actualizaciones por fuente usando el generador y `Storage.put_source`, sin `Lab.run` local.
6. Interrumpir productor entre ACK y actualización outbox, broker durante publicación y consumidor entre commit de journal y commit Kafka. Verificar ausencia de pérdida, repetición segura y contenido completo del historial, no solo el contador final.
7. Fijar las versiones efectivamente instaladas en un lock del entorno Big Data, añadir pruebas integradas distribuibles y actualizar este informe con los comandos, salidas y tiempos reales.

El router opcional `backend/lab_analytics.py` expone `GET /api/lab/analytics?query=counts|prices|history`. Integrado en `create_app` mediante `app.include_router(create_lab_analytics_router(data_dir/'laboratorio'))`. No ejecuta SQL arbitrario ni instala dependencias. Si DuckDB falta devuelve HTTP 503 con `code=duckdb_unavailable` y `executed=false`.

## Fuentes técnicas consultadas

- [dlt: carga incremental](https://dlthub.com/docs/general-usage/incremental-loading).
- [dlt: carga merge y claves](https://dlthub.com/docs/general-usage/merge-loading).
- [Apache Kafka: imagen Docker oficial 4.1.2](https://kafka.apache.org/41/getting-started/docker/).
- [DuckDB: exportación Parquet](https://duckdb.org/docs/current/guides/file_formats/parquet_export).
- [kafka-python: consumidor y confirmación de offsets](https://kafka-python.readthedocs.io/en/master/apidoc/KafkaConsumer.html).
