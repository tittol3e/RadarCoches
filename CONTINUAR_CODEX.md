# Continuar RadarCoches — punto de relevo

**Última continuación:** consultar primero `INFORME_REPARACION_KAFKA.md`.
ConnectTimeout reproducido y corregido en preflight HTTP antes de iniciar APIs.
dlt 1.32.0, DuckDB 1.5.6 y kafka-python 2.3.3 instalados. Kafka real responde.
Revisiones, historial, Parquet, reenvíos y replay superados. Volumen distribuido
superado: 1.050 anuncios y 20 cambios; evidencia 801f173136444fbfafdc8b0831033771.
El estado previo de
dependencias ausentes/motor detenido que sigue más abajo es histórico.

Proyecto único: `C:\Users\ia\Desktop\INGESTA DATOS\RadarCoches`. El prompt llegó repetido tres veces por error; no crear proyectos adicionales. No hay Mac, chats antiguos, ZIP ni especificación recuperados. Se conserva prototipo CSV original y copia de sus archivos previos a corrección Windows en `actividad_ingesta/legacy_recuperado/`.

## Trabajo ya realizado

Backend FastAPI modular, SQLite real, interfaz con ocho pantallas y scripts Windows. Radar/importación/historial/filtros/favoritos, comparables y tasación prudente con ajustes respaldados, motor Decimal/fiscalidad manual documentada, taller/presupuestos/compatibilidad, operaciones/estadísticas realizadas, IA local opcional desactivada, copias/restauración/exportaciones. Tasaciones vinculadas guardan instantáneas y aparecen en las fichas.

Laboratorio local implementado y probado con dos APIs, cursores, snapshots, outbox, idempotencia, historial, reintentos e interrupciones. Ejercicios 10/12/12/12 y volumen 1.050+20 superados con transporte SQLite explícito. Adaptador dlt → landing DuckDB → outbox → Kafka → consumidor → DuckDB/Parquet escrito, **no ejecutado**. No presentarlo como integración terminada.

Pruebas y estado actual: `INFORME_FINAL.md`, `ESTADO_PROYECTO.md`, `docs/evidencias/resultado_tests.json`, `docs/evidencias/pruebas_navegador.json`, `docs/INFORME_INGESTA.md`. No repetir auditoría ni reconstrucción. Las pruebas unittest son compatibles con pytest, pero pytest no se pudo instalar ni ejecutar en esta sesión.

## Bloqueo real y siguiente paso

Actualización de continuación: Laboratorio convertido en práctica guiada y
probado con navegador. `scripts/run_distributed.py` ahora acepta `--volume`,
comprueba fuentes/SQLite/DuckDB/Parquet e historial, reenvía y reproduce eventos,
aisla topics por directorio y guarda evidencia incluso si falla. Estas nuevas
comprobaciones distribuidas están escritas pero no ejecutadas con dependencias
reales. El consumidor exporta por lotes antes de confirmar offsets; contratos
de orden de ACK y replay comprobados con dobles de Kafka. Las caídas reales de
broker/productor/consumidor siguen pendientes. Ver `GUIA_DEMOSTRACION.md`.

La red de procesos de este entorno deniega sockets externos (pip WinError 10013). No hay dlt/DuckDB/kafka-python/pytest en la caché recuperada. Docker tiene cliente pero no motor disponible. No se han pedido privilegios elevados ni se ha cambiado seguridad del equipo. La aplicación principal ya funciona con ruedas instaladas offline en `.venv`.

El usuario debe disponer de una terminal con red normal para instalar dependencias del proyecto y abrir su Docker Desktop existente. No requiere publicar ni contratar nada:

```powershell
cd "C:\Users\ia\Desktop\INGESTA DATOS\RadarCoches"
.\scripts\instalar.ps1 -BigData -Desarrollo
docker version
docker compose -f actividad_ingesta/docker-compose.yml up -d
.\iniciar_ingesta.ps1 -Modo distributed
```

Ese último script prepara un espacio nuevo en `data/laboratorio_distribuido/<uuid>`, inicia las APIs 8771/8772 y recorre revisiones por el circuito distribuido. Antes de darlo por válido, corregir cualquier diferencia de API de las dependencias instaladas, comprobar totales y ambos precios en DuckDB, y leer realmente el Parquet. Registrar versiones efectivas y fijar un lock Big Data. Los rangos actuales de dependencias son propuesta sin validación instalada.

Continuar con volumen distribuido (500+500, 25+25 altas, 10+10 precios), interrupción/reinicio del productor, broker y consumidor entre ACK/outbox/commit y replay con offsets reales. Conservar todos los eventos de historial aunque lleguen tarde, no solo el estado final. El comando `volume` actual solo acredita modo local. Ver instrucciones detalladas y contrato en `docs/INFORME_INGESTA.md`.

La consulta analítica `/api/lab/analytics?query=counts|prices|history` está integrada, devuelve 503 explícito sin DuckDB y rechaza SQL libre. Revisar raíz de consulta si se utiliza un directorio distribuido nuevo: el endpoint de la aplicación consulta por defecto su laboratorio, no los subdirectorios arbitrarios de cada ejecución CLI.

## Integraciones externas posteriores

Portales reales: no conectados por falta de acceso autorizado; mantener alta manual/CSV/JSON y estados honestos. No scrapear ni eludir restricciones. Recambios: presupuestos manuales, sin inventario conectado. Ollama: adaptador implementado y errores probados, modelo/servidor real no instalado ni validado. Gemini/Groq y servicios de pago no activados; no asumir gratuidad ni enviar datos a terceros.

## Comandos ya operativos

```powershell
.\iniciar_radarcoches.ps1
.\detener_radarcoches.ps1
.\probar_proyecto.ps1
.\.venv\Scripts\python.exe scripts/browser_test.py
.\demo_ingesta.ps1
.\demo_ingesta.ps1 -Volumen
```

El script navegador usa Edge headless, base temporal, puertos 8876/9223 y no toca `data/radar.sqlite`. Si falla tras cambios, inspeccionar screenshots y errores reales. No declarar éxito por generar el archivo de prueba.

El servidor principal solo localhost 8765; no cambiar a exposición pública. Las bases, backups y `.env` están ignorados por Git. No se han hecho publicaciones ni escrituras remotas. Antes de modificar datos personales, copia desde Configuración. Los scripts de parada usan Get-Process y registros PID+tiempo+ejecutable, porque WMI está denegado en este Windows.
