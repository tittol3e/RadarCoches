# Reparación del arranque distribuido — 16/11/2026

## Causa raíz del ConnectTimeout

Los informes anteriores `9c3f48a86d374df6a0f9dfd191217e26.json` y
`e7558373130b4ceebb8eafa95048720e.json` fallaban sin completar ningún paso.
Sus directorios estaban vacíos: ni siquiera habían arrancado las APIs.

La conexión que fallaba era **HTTP a 127.0.0.1:8771, ruta /health, API DEMO A**.
La comprobación previa del script intentaba consultar esa API antes de crearla.
Solo trataba `httpx.ConnectError` como puerto libre. En este Windows se midieron
aproximadamente 2,03 segundos para recibir el rechazo TCP de un puerto vacío
(WinError 10061), pero el cliente HTTP tenía un timeout de 2 segundos: producía
`httpx.ConnectTimeout`, que escapaba y terminaba la prueba. La API B, puerto
8772, reprodujo el mismo comportamiento al probarla por separado.

Es un defecto del código de comprobación previa, expuesto por los tiempos de
rechazo de conexión de Windows. No era un timeout de Kafka ni un fallo de dlt.

## Kafka y Docker

Se estableció conexión TCP con **127.0.0.1:9092** y se consultó el clúster con
`KafkaAdminClient.describe_cluster()`. Respondió el broker 1, anunciado como
`127.0.0.1:9092`, con controlador 1 y cluster_id `5L6g3nShT-eMCtK--X86sw`.
La configuración de listeners en Compose coincide; no se modificó.

Se intentaron `docker compose ps` y `docker compose logs --tail 80 kafka`.
Este entorno deniega el acceso a la named pipe del motor Docker. Por tanto, no
se afirma haber leído el stdout del contenedor Kafka. Sí se inspeccionaron los
logs locales de Docker Desktop (`log/host/com.docker.backend.exe.log` y
`log/vm/init.log`); el segundo registra la creación del contenedor
`actividad_ingesta-kafka-1` con `apache/kafka:4.1.2`. La disponibilidad real se
acredita por el protocolo Kafka y por la publicación/lectura de los eventos.

## Cambios

- `scripts/run_distributed.py`: sustituida la petición HTTP previa por una
  comprobación de bind exclusivo al puerto en Windows. No toca los servicios
  existentes. El arranque posterior conserva la detección de conflictos.
- Espera limitada de disponibilidad del broker mediante metadatos Kafka y de
  ambas APIs mediante `/health`, comprobando fuente e identificación sintética.
- Evidencia con fase, conexiones, metadatos Kafka y traceback ante errores;
  cada fase terminada queda registrada aunque falle la siguiente.
- `distributed.py`: cliente HTTP de extracción con `trust_env=False`, igual
  que los chequeos de localhost, para no depender de proxies del sistema.
- Durante la primera repetición apareció otro bloqueo: dlt intentaba comprobar
  escritura en el perfil del usuario, fuera del workspace permitido. Un volcado
  de pila lo situó en `RunContext.global_dir → is_folder_writable → tempfile`.
  Ahora su contexto y configuración viven dentro del directorio de ejecución,
  en `dlt_runtime`. Se desactiva la telemetría de ese contexto local.
- Cuatro pruebas de regresión de arranque añadidas. Versiones del entorno
  instalado fijadas en `actividad_ingesta/requirements-bigdata-lock.txt`.

No se borraron volúmenes, no se recreó el broker y no se modificó la base real
del Radar. Las nuevas pruebas utilizan directorios y topics propios. Se
conservan las ejecuciones anteriores, incluidas las fallidas.

## Resultados

Prueba distribuida básica: **SUPERADA**, informe
`docs/evidencias/distribuido/9fa92b8d3ee9401cbee7a5b19110b1ae.json`.

| Etapa | Anuncios únicos | Eventos originales |
|---|---:|---:|
| Revisión 0 | 10 | 10 |
| Revisión 1 | 12 | 12 |
| Revisión 2 | 12 | 14 |
| Revisión 3 | 12 | 14 |
| Reenvío de 14 eventos | 12 | 14 |
| Replay con grupo nuevo: 28 mensajes | 12 | 14 |

Los 28 mensajes del replay incluyen los 14 originales más sus 14 reenvíos:
siguen existiendo solo 14 eventos de historial y 12 anuncios. Se comparan
contenido y versiones con las fuentes, historial SQLite con DuckDB y anuncios
SQLite con DuckDB y con la lectura real del Parquet. El ejecutor también exige
exactamente dos cambios de precio antes de declarar éxito.

Comprobación independiente del historial: DEMO A pasó de 803.200 a 793.200
céntimos; DEMO B de 2.430.100 a 2.420.100 céntimos. Ambos cambios son de 100 €
y versión 2.

Prueba distribuida de volumen: **SUPERADA**, ejecutada únicamente después de
la básica. Informe:
`docs/evidencias/distribuido/801f173136444fbfafdc8b0831033771.json`.

| Etapa | Anuncios únicos | Eventos originales |
|---|---:|---:|
| Recogida inicial | 1.000 | 1.000 |
| 50 altas | 1.050 | 1.050 |
| 20 precios modificados | 1.050 | 1.070 |
| Reenvío de los 1.070 eventos | 1.050 | 1.070 |
| Replay con grupo nuevo: 2.140 mensajes | 1.050 | 1.070 |

Se han comprobado independientemente 20 bajadas de 250 €, todas en versión 2,
y 1.050 filas al leer el Parquet final. Los offsets consultados al broker son
28 para ambos grupos de la prueba básica y 2.140 para ambos de volumen, en sus
respectivos topics. No se han confundido mensajes retransmitidos con eventos
únicos. Verificación adicional guardada en
`docs/evidencias/verificacion_reparacion_kafka.json`, con precios y offsets.

Versiones reales: dlt 1.32.0, DuckDB 1.5.6, kafka-python 2.3.3; Python 3.12.
Suite local: **60 pruebas de aplicación/pipeline + 2 del prototipo**, todas
superadas. `pip check` y compilación también superados.

## Repetir en Windows

Con Docker Desktop iniciado y Kafka en ejecución, desde la carpeta RadarCoches:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File iniciar_ingesta.ps1 -Modo distributed
```

Solo después de superar esa prueba:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File iniciar_ingesta.ps1 -Modo distributed -Volumen
```

Para recrear las versiones instaladas en un entorno Python 3.12 de Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r actividad_ingesta/requirements-bigdata-lock.txt
```

El lock incluye el entorno completo, incluidas herramientas de pruebas. No
instala Docker ni cambia su configuración. Los puertos 8771 y 8772 deben estar
libres al arrancar; los logs de esas APIs se guardan en el directorio que indica
el JSON. Las pruebas no detienen ni reinician el broker. No acreditan todavía
caídas reales del broker o de los procesos en cada punto de confirmación.
