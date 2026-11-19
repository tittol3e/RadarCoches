# RadarCoches

**Actualización 16/11/2026, reparación de arranque:** la integración distribuida
real ya ha superado las revisiones 10 → 12 → 12 → 12, historial, reenvíos y replay,
con dlt, Kafka, DuckDB y lectura de Parquet. También ha superado el volumen:
1.050 anuncios únicos y 20 cambios de precio. El estado anterior de bloqueo
de dependencias que aparece más abajo es histórico. Causa y evidencias:
[INFORME_REPARACION_KAFKA.md](INFORME_REPARACION_KAFKA.md).

Aplicación web personal para analizar compraventa de vehículos con evidencias, persistencia local y cálculo financiero independiente de IA. Reconstruida en Windows el 16/11/2026. Referencia Cádiz; admite cualquier provincia mediante entrada libre.

**Estado a 19/11/2026:** el laboratorio incluye prácticas SQLite aisladas con anuncios e historial, y un visor de informes de la integración distribuida con sus archivos DuckDB y Parquet. Consulta el [informe técnico de la auditoría](INFORME_TECNICO_AUDITORIA.md) para ver las pruebas recientes.

## Arranque en este equipo

Para presentar el trabajo, abre **Laboratorio de datos**, pulsa **Nueva práctica limpia** y sigue los pasos de la [guía para el profesor](GUIA_PRESENTACION_PROFESOR.md).

Doble clic en `iniciar_radarcoches.bat`, o desde PowerShell:

```powershell
cd "C:\ruta\RadarCoches"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\iniciar_radarcoches.ps1
```

Web: **http://127.0.0.1:8765**. Solo localhost, sin registro, Docker ni claves. `ExecutionPolicy Bypass` afecta a ese proceso; no cambia la política global. Parada: `detener_radarcoches.ps1`. El servidor conserva los datos entre reinicios.

## Módulos implementados

| Pantalla | Uso local |
|---|---|
| Inicio | Contadores reales, fuentes no conectadas, IA desactivada |
| Radar | Alta/edición manual, CSV/JSON, filtros, favoritos, notas, historial y clasificación prudente |
| Tasador | Catálogo editable, entrada libre, comparables fechados, selección, ajuste de km solo con evidencia, escenarios y oferta configurable |
| Rentabilidad | Costes desglosados, impuesto manual/proporcional, base fiscal mínima y precio máximo inverso con Decimal |
| Taller y piezas | Extracción de daños declarados, edición, presupuestos y alternativas; confirmación y compatibilidad explícitas |
| Mis operaciones | Etapas, ofertas, inspecciones, gastos previstos/reales, compras/ventas e historial persistente |
| Laboratorio | Prácticas SQLite con respuestas de las APIs, anuncios, diferencias de precio y replay. Visor de informes, DuckDB y Parquet de la prueba con Kafka |
| Configuración | IA opcional Ollama local, contadores, exportaciones y copias/restauración |

No se añaden coches ficticios al Radar. La aplicación comienza sin anuncios. Los precios desconocidos permanecen vacíos; una URL importada no implica verificación remota. Tres comparables comprobados y suficientemente similares son el mínimo para calcular un rango, sin garantía de venta. Una estimación nunca constituye beneficio realizado.

## Pruebas y actividad académica

```powershell
.\probar_proyecto.ps1
.\.venv\Scripts\python.exe scripts/browser_test.py
.\demo_ingesta.ps1
.\demo_ingesta.ps1 -Volumen
```

Las pruebas escriben datos temporales separados. La demo académica local produce 10 → 12 → 12 → 12 y el ejercicio de volumen espera 1.050 únicos con 20 actualizaciones. La integración con dlt y Kafka se ejecuta por separado y genera su propio informe. Sigue los pasos de la [guía para el profesor](GUIA_PRESENTACION_PROFESOR.md).

## Dependencias

Python 3.12, FastAPI, Uvicorn, httpx y python-dotenv. Instalados en `.venv`, sin cambios globales. Versiones principales en `requirements.txt`; entorno completo probado en `requirements-lock.txt`. Node no necesario. Para una instalación nueva: [INSTALACION_WINDOWS.md](INSTALACION_WINDOWS.md).

Para pytest y las pruebas de navegador usa `requirements-dev.txt`. Los requisitos de la integración distribuida se detallan en `actividad_ingesta/requirements-bigdata.txt`.

## Archivos y privacidad

`backend/`: configuración, esquemas, repositorio, seguridad, proveedores, cálculo, valoración, taller, operaciones, IA y rutas. `frontend/`: HTML/CSS/JS sin CDN. `actividad_ingesta/`: prototipo recuperado y pipeline nuevo. `tests/`: pruebas locales. `scripts/`: utilidades y navegador. `docs/evidencias/`: salidas y capturas. `data/radar.sqlite`: datos personales; `data/laboratorio/`: datos sintéticos. `backups/`: copias personales.

No publiques `data/`, `backups/`, `.env` ni claves. El `.gitignore` los excluye. No se ha creado ni publicado repositorio remoto, comprado servicios ni enviado anuncios a terceros. Ollama solo admite `127.0.0.1:11434`, está desactivado y no descarga modelos.

Consulta [MANUAL_USUARIO.md](MANUAL_USUARIO.md), [ARQUITECTURA.md](ARQUITECTURA.md), [FUENTES_DE_DATOS.md](FUENTES_DE_DATOS.md) y [docs/AUDITORIA.md](docs/AUDITORIA.md).
