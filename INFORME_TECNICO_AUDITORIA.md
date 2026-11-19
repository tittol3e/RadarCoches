# Auditoría técnica de RadarCoches

Fecha de ejecución: 19 de noviembre de 2026.

## Hallazgos y cambios

| Hallazgo | Cambio |
|---|---|
| La práctica web reutilizaba una única base sintética y combinaba extracción y consumo en la primera revisión. | Las prácticas nuevas tienen SQLite propio. La carga inicial permite consultar las APIs, inspeccionar la cola y procesarla como tres operaciones separadas. Las prácticas guardadas se pueden retomar y el inventario local anterior sigue consultable. |
| Los totales no permitían identificar qué cambió. | El laboratorio muestra inventario, altas, historial con versiones, precios anterior y nuevo, cursores, contadores por etapa y verificaciones. El replay local comprueba que fichas e historial completos conservan su contenido. |
| La ruta analítica anterior consultaba el directorio local, mientras las ejecuciones distribuidas guardaban sus archivos en un directorio por ID. | El nuevo visor vincula cada informe distribuido completado con sus propios resultados DuckDB y Parquet. Abre DuckDB en solo lectura y ejecuta consultas fijas. Si falta un archivo, lo indica por separado. |
| La verificación distribuida comparaba el JSON de cada ficha, dejando fuera las columnas analíticas extraídas. | El verificador compara también marca, modelo, año, kilómetros y precio en DuckDB y Parquet. Exige los mensajes enviados, recibidos y reprocesados esperados por revisión. |
| El consumidor hacía una exportación adicional después de proyectar y confirmar el último lote. | El resultado reutiliza la proyección del último checkpoint. Sigue exportando antes de confirmar offsets. Una prueba cubre el caso en que el último lote se llena exactamente. |
| Los informes del navegador, la prueba HTTP y el volumen local reutilizaban nombres. | Las nuevas ejecuciones escriben en rutas independientes. El informe de volumen local se puede descargar desde la práctica. |

## Recorrido y recuperación

- Cada API sirve un inventario vigente y un flujo paginado de cambios. El límite superior del flujo se fija al empezar la lectura. Los esquemas validan los datos sintéticos y la huella comprueba la correspondencia con el contenido. En un alta, el precio anterior es inaplicable. La interfaz muestra explícitamente valores desconocidos cuando no dispone de ellos.
- En local, el cursor y la inserción en la cola SQLite son atómicos. Las pruebas cubren interrupción tras guardar una página, extracción reanudada, fallo de conexión, consumo parcial, reenvío, llegada fuera de orden y versiones incompatibles.
- En distribuido, dlt carga los cambios de cada fuente en el DuckDB de entrada. Se copia el landing completo a la cola con clave única por evento. El productor marca solo los mensajes confirmados por Kafka. Si el mismo mensaje vuelve a aparecer, el consumidor conserva la única entrada de historial y la versión vigente por fuente e ID.
- El consumidor registra cambios primero en SQLite, proyecta a DuckDB y reemplaza el Parquet tras escribir un archivo temporal. Confirma offsets después de proyectar. La suite cubre el fallo de exportación y la ausencia de confirmación con un consumidor simulado. El replay con broker real comprueba idempotencia con otro grupo de consumo.

## Pruebas ejecutadas

| Prueba | Resultado y evidencia |
|---|---|
| Pytest, incluidos aplicación, prototipo CSV, pipeline, recuperación simulada y visor | **65 superadas**. [Salida de pytest](docs/evidencias/pytest-auditoria-1db25f89505e473ba04ce2cecc70e46d.txt). |
| Ambas APIs en procesos Uvicorn independientes | **Superada**. HTTP 200, esquema, páginas, cursores, altas y actualizaciones incrementales e HTTP 422 ante parámetros inválidos. [Informe HTTP](docs/evidencias/apis_http-b82b7e41a2684b67a0ae2106e9a1ec0d.json). |
| Uvicorn y Microsoft Edge, escritorio y móvil de 390 px | **Superada**. Se recorrió la práctica completa, el volumen local y el visor distribuido con copias de los resultados reales. [Informe de Edge](docs/evidencias/navegador-02b14024c60541d8b7700c91800bbb78/pruebas_navegador.json), [captura de precios](docs/evidencias/navegador-02b14024c60541d8b7700c91800bbb78/navegador-cambios-precio.png) y [captura analítica](docs/evidencias/navegador-02b14024c60541d8b7700c91800bbb78/navegador-resultados-distribuidos.png). |
| `probar_proyecto.ps1` | **Superada**. El ejecutor comprobó 63 pruebas de unittest, dependencias y compilación, con una base temporal. [Informe del ejecutor](docs/evidencias/pruebas-locales-738fa4c3877941509e7601e299d73643/resultado_tests.json). |
| Distribuida, cuatro revisiones, reenvío y replay | **Superada dos veces con el broker real**. La segunda usó el verificador ampliado. [Primera ejecución nueva](docs/evidencias/distribuido/64d628066c28435f97865b5287134a2b.json) y [segunda ejecución nueva](docs/evidencias/distribuido/82eece76d69d45edb2a625ac50387ad8.json). |
| Distribuida, primer intento de volumen | **Falló** con `WinError 5` al reemplazar `schema.json` dentro del estado de dlt. [Informe del fallo](docs/evidencias/distribuido/da46004a8b9745e19a81f343cfcffd34.json). |
| Distribuida, segundo intento de volumen | **Superada** en un directorio nuevo. Pasó de 1.000 a 1.050 anuncios, aplicó 20 cambios de precio y conservó 1.050 fichas tras recibir 2.140 mensajes en el replay. [Informe de volumen](docs/evidencias/distribuido/5be4a8037e9341a7af54d506ab672319.json). |

Resultados de la segunda ejecución distribuida de revisiones:

| Etapa | Enviados y recibidos | Eventos distintos en el historial | Anuncios únicos |
|---|---:|---:|---:|
| Revisión 0 | 10 | 10 | 10 |
| Revisión 1 | 2 | 12 | 12 |
| Revisión 2 | 2 | 14 | 12 |
| Revisión 3 | 0 | 14 | 12 |
| Reenvío | 14 | 14 | 12 |
| Replay con otro grupo | 28 recibidos | 14 | 12 |

Los dos cambios registrados en DuckDB corresponden a `DEMO-demo_a-000001` (8.032 € → 7.932 €) y `DEMO-demo_b-000001` (24.301 € → 24.201 €). El informe facilitado al iniciar la auditoría sigue siendo una [evidencia histórica independiente](docs/evidencias/distribuido/9c626f9c22bd4b419188b86d9d669f04.json).

## Archivos modificados

- Web y API: `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`, `frontend/laboratorio.js`, `backend/main.py` y `backend/lab_demo.py`.
- Pipeline: `actividad_ingesta/pipeline/lab.py`, `actividad_ingesta/pipeline/storage.py` y `actividad_ingesta/pipeline/distributed.py`.
- Pruebas y utilidades: `tests/test_lab_demo.py`, `tests/test_distributed_checkpoint.py`, `actividad_ingesta/test_ingesta.py`, `scripts/run_distributed.py`, `scripts/test_source_http.py`, `scripts/browser_test.py` y `scripts/run_tests.py`.
- Documentación: `README.md`, `GUIA_DEMOSTRACION.md`, `GUIA_PRESENTACION_PROFESOR.md` y este informe.

## Límites de la verificación

- El broker estaba accesible por el protocolo Kafka. El acceso a la interfaz de Docker Desktop fue denegado por los permisos de esta sesión. Queda pendiente comprobar una caída real del broker y su recuperación. El reenvío de la prueba fuerza el estado de envío de la cola y el replay usa otro grupo. Son pruebas distintas de una caída del broker.
- El error de Windows durante el primer volumen ocurrió dentro del reemplazo de archivos de dlt. El intento posterior pasó con la misma versión. No se determinó el origen del bloqueo del archivo.
- Starlette 1.10.0 avisa del uso de httpx 0.28.1 con `TestClient`. La advertencia se reprodujo y las pruebas terminaron. La documentación de Starlette indica que ese cliente sigue soportado y está deprecado. Se conservó el entorno instalado, que también pasó `pip check`. [Documentación de TestClient](https://starlette.dev/testclient/).
- El visor distribuido enseña hasta 100 filas por tabla e indica el total. La prueba de 12 anuncios cabe completa. El flujo está preparado para un proceso que gestione cada directorio de ejecución.
- La carpeta de trabajo no incluye `.git`. Se editó la copia local y quedan preservados los datos personales, las copias y los informes preexistentes. No se creó commit ni se publicó nada.
