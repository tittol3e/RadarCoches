# Guía de presentación de RadarCoches

## Antes de empezar

Abre PowerShell y el navegador. Abre Docker Desktop si vas a ejecutar la integración distribuida durante la presentación. El laboratorio local funciona con el entorno Python del proyecto y SQLite.

```powershell
Set-Location 'C:\ruta\RadarCoches'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\iniciar_radarcoches.ps1
```

Abre **http://127.0.0.1:8765** y entra en **Laboratorio de datos** desde el menú. Si falta `.venv`, sigue [Instalación en Windows](INSTALACION_WINDOWS.md). Si ya había una instancia de RadarCoches abierta antes de actualizar el código, ciérrala con `detener_radarcoches.ps1` y vuelve a arrancarla.

## Demostración local en la web

Pulsa **Nueva práctica limpia**. La práctica anterior queda disponible en el selector. Cada práctica tiene su propia base y los anuncios del Radar personal permanecen separados.

| Pulsa | Qué enseñar | Resultado esperado en una práctica nueva |
|---|---|---|
| **Leer las APIs** | En **Respuestas de las APIs**, consulta `demo_a` y `demo_b`. Abre el detalle JSON para ver `/health`, `/ads` y `/changes`. | HTTP 200, cinco anuncios por fuente y diez eventos generados. |
| **Extraer los eventos** | Abre **Ver eventos recogidos en la cola**. Muestra el ID, la versión, el precio y el cursor por fuente. | Diez eventos extraídos y pendientes de consumo. La tabla de anuncios guardados sigue vacía. |
| **Procesar y almacenar** | Señala **Anuncios guardados** y el registro de **Operaciones y evidencias**. | Diez eventos procesados y diez anuncios únicos en SQLite. |
| **Incorporar anuncios nuevos** | En **Altas después del inventario inicial**, busca los dos identificadores terminados en `000006`. | Doce anuncios únicos. |
| **Actualizar precios** | En **Cambios de precio**, enseña las dos versiones nuevas y sus importes anterior y nuevo. | Dos bajadas de 100 € y doce anuncios únicos. En el historial, el precio anterior de un alta figura como «No corresponde». |
| **Reprocesar y verificar** | Lee el resultado del reenvío y abre **Descargar informe de esta práctica (JSON)**. | La consulta incremental no extrae cambios nuevos. El consumidor recibe de nuevo 14 eventos, incorpora cero y conserva 12 anuncios. |

Un anuncio es la ficha vigente. Un evento cuenta una alta o una actualización de esa ficha. Por eso puedes tener **14 eventos distintos y 12 anuncios únicos**. El identificador de la ficha es la pareja de fuente e ID. El consumidor reconoce un reenvío por la huella del evento. Los valores obligatorios de las fuentes sintéticas se validan y la interfaz muestra «Desconocido» cuando un valor no está disponible.

## Integración distribuida y visor de resultados

Con Docker Desktop abierto, ejecuta lo siguiente en PowerShell. Si tienes las APIs de prueba abiertas en otra consola, páralas con Ctrl+C antes de iniciar la integración. La prueba levanta y cierra sus propias APIs en los puertos 8771 y 8772.

```powershell
docker compose -f .\actividad_ingesta\docker-compose.yml up -d
docker compose -f .\actividad_ingesta\docker-compose.yml ps
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\iniciar_ingesta.ps1 -Modo distributed
```

El script pide los metadatos del clúster Kafka antes de ejecutar la primera revisión. Su informe registra el tema Kafka, los mensajes publicados y los recibidos. Espera a que termine y muestra la ruta `Evidencia:` que imprime la consola. El resultado esperado es **10 → 12 → 12 → 12 anuncios**, **dos cambios de precio**, **14 mensajes de reenvío** y **28 mensajes recibidos en el replay** con otro grupo de consumo.

En la web, recarga **Laboratorio de datos** y elige el informe en **Integración distribuida · Evidencias guardadas**. El visor muestra la tabla por revisión, los registros de DuckDB y Parquet y los precios antes y después. El informe y los datos siguen disponibles cuando apagas Kafka. Su etiqueta «histórica» indica que es una lectura de archivos guardados. Si el broker no responde, conserva el informe del fallo y puedes mostrar al profesor una ejecución completada anterior.

Los informes están en `docs/evidencias/distribuido/<id>.json`. Los archivos `landing.duckdb`, `analitica.duckdb` y `anuncios.parquet` se guardan juntos en `data/laboratorio_distribuido/<id>/`. El visor indica si falta un archivo.

Para la prueba distribuida de volumen, añade `-Volumen` al comando de integración. El resultado esperado es **1.050 anuncios únicos y 20 cambios de precio**. Puede tardar varios minutos.

### Mostrar las dos APIs HTTP en directo

Si quieres enseñar Swagger y las respuestas HTTP fuera del laboratorio web, ejecuta estas órdenes en una consola distinta, desde la raíz del proyecto y con la integración detenida. Queda un espacio sintético separado para esta vista.

```powershell
$env:RADAR_LAB_DIR = Join-Path $PWD ('data\apis-presentacion-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -c "import os; from actividad_ingesta.pipeline.lab import Lab; Lab(os.environ['RADAR_LAB_DIR']).prepare_revision(0)"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\iniciar_ingesta.ps1 -Modo apis
```

Abre **http://127.0.0.1:8771/docs** y **http://127.0.0.1:8772/docs**. Prueba también `/ads?page_size=2` y `/changes?since=0&page_size=2` en ambos puertos. Swagger muestra los parámetros que puedes cambiar. Cierra las dos APIs con Ctrl+C en la consola antes de hacer la prueba distribuida.

## Respuestas cortas para el profesor

| Si pregunta… | Puedes responder… |
|---|---|
| ¿Qué es una API? | Es un contrato para solicitar datos. FastAPI ofrece los inventarios y un flujo paginado de cambios. |
| ¿Qué hace dlt? | Llama a las APIs por HTTP, usa un cursor incremental y guarda los eventos en tablas de entrada de DuckDB. |
| ¿Qué hace Kafka? | Transporta los eventos confirmados por el broker. El consumidor usa offsets para saber hasta dónde avanzó dentro de cada partición. |
| ¿Dónde se guardan los resultados? | SQLite guarda el estado operativo del consumidor. DuckDB contiene las tablas analíticas de anuncios e historial. Parquet es el archivo tabular de salida para consultar o compartir datos. |
| ¿Cómo se recupera un envío repetido? | Un evento puede llegar otra vez. El consumidor consulta su huella, conserva una sola entrada en el historial y usa la versión para mantener la ficha vigente. |
| ¿Qué prueba demuestra que se mantienen los datos? | La integración compara las fichas de las APIs, el estado del consumidor y las filas de DuckDB y Parquet. El replay lee de nuevo los mensajes con otro grupo. |

## Guion de cinco minutos

1. **0:00–0:50.** Abre el laboratorio, crea una práctica y enseña el estado y las respuestas de ambas APIs.
2. **0:50–1:40.** Extrae los eventos, abre la cola y procesa las fichas. Compara los contadores antes y después del consumo.
3. **1:40–2:40.** Añade los dos anuncios y señala las dos bajadas de precio en el historial.
4. **2:40–3:25.** Reprocesa y muestra el resultado del reenvío con los doce anuncios.
5. **3:25–5:00.** Abre el informe distribuido, enseña los mensajes Kafka y compara las tablas de DuckDB y Parquet. Inicia la prueba distribuida antes de la presentación si quieres contar con un informe recién completado.

## Pruebas y alcance

En la auditoría pasaron 65 pruebas de Python, la prueba HTTP de las dos APIs, el recorrido con Edge y la integración real de doce anuncios. El volumen distribuido llegó a 1.050 anuncios tras repetir un intento que falló con un error de archivos de Windows. La recuperación ante una caída real del broker sigue pendiente. Consulta los resultados y sus evidencias en el [informe técnico](INFORME_TECNICO_AUDITORIA.md).
