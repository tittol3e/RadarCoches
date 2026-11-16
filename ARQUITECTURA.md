# Arquitectura

## Aplicación

Navegador → FastAPI en 127.0.0.1:8765 → servicios Python → repositorio SQLite. HTML, CSS y JavaScript locales evitan dependencias Node y CDN. Contrato de endpoints en `/api/docs` y `/openapi.json`.

| Componente | Responsabilidad |
|---|---|
| `schemas.py` | Pydantic: datos, límites, importes, fechas, operaciones y compatibilidad |
| `repository.py` | SQL parametrizado, transacciones, identidad de anuncios, historial y backups |
| `providers.py` | Interfaz común; portales no autorizados devuelven estado no disponible |
| `calculations.py` | Decimal, coste total, margen e inversión del impuesto proporcional con base mínima |
| `valuation.py` | Filtrado, evidencia, ponderaciones, escenarios hipotéticos y rechazo por insuficiencia |
| `operations.py` | Estadísticas de compra/venta y beneficios únicamente de operaciones vendidas |
| `workshop.py` | Extracción determinista de daños declarados y requisitos pendientes |
| `ai.py` | Adaptador opcional Ollama fijo en localhost, sin proveedores externos ni cambio automático |
| `main.py` | Rutas, límites HTTP, origen local, importación/exportación e integración |
| `lab_analytics.py` | Consultas analíticas cerradas; 503 explícito cuando DuckDB no está disponible |

## Persistencia real

`data/radar.sqlite` contiene anuncios, historial de precios, comparables, presupuestos, operaciones, historial de operaciones, catálogo, tasaciones guardadas y configuración. Los importes se serializan como decimales exactos; SQLite almacena fichas JSON validadas y columnas de identidad indexadas. Claves únicas: fuente+ID externo y URL canónica. Se conserva el query de identidad y se eliminan parámetros de seguimiento conocidos. Coincidencia contradictoria o cambio marca/modelo con misma identidad exige revisión; no se deduplica por marca/km/precio.

Cada lote importado se valida antes y se escribe en una transacción. Un error revierte el lote entero. La reimportación no reactiva anuncios retirados/vendidos ni sustituye notas/favoritos. La detección y el historial son observaciones del sistema local; no se confunden con comprobaciones remotas.

Las tasaciones asociadas a anuncios guardan petición, resultado, comparables usados y fecha de cálculo local. Una instantánea no prueba que el anuncio siga disponible. Los impuestos se aplican solo según parámetros aportados; las referencias oficiales no se convierten en valores automáticos.

## Valoración

Mínimo tres URLs distintas, datos comprobados por el usuario, observación reciente (90 días), marca/modelo y características compatibles. Se rechazan años distantes y kilómetros fuera del ámbito justificable. La ponderación de cercanía de año/km no equivale a un ajuste monetario por equipamiento o provincia.

El ajuste de km requiere al menos tres pares con separación de 30.000 km en grupos de año, versión, generación, motor, combustible, cambio, estado, equipamiento y provincia documentados. Se usa la mediana de pendientes negativas observadas. No se extrapola fuera del intervalo de km de los comparables. Es evidencia descriptiva de precios solicitados, no una relación causal ni precio de venta confirmado. Las demás diferencias permanecen como riesgos.

Escenarios usan mínimo, media ponderada y máximo ajustados. El descuento de reventa y oferta inicial los decide el usuario y siempre son hipótesis. Costes con importe pendiente impiden dar un precio máximo completo. El margen se expresa antes de impuestos sobre beneficio.

## Laboratorio separado

Modo probado: generador → dos APIs FastAPI en proceso → extracción paginada con reintentos y cursor → outbox SQLite → consumidor idempotente SQLite. Fuentes, journal y resultados están exclusivamente bajo `data/laboratorio/`. Los ejercicios de volumen y demostraciones CLI usan subcarpetas propias. Nunca se importa de ese directorio al Radar.

Modo distribuido escrito, sin ejecutar: APIs HTTP → recurso incremental dlt → landing DuckDB durable → outbox → Kafka → consumidor → journal → DuckDB/Parquet. El landing conserva eventos cuando dlt ya ha confirmado cursor y el envío falla. Se conserva la outbox hasta ACK; el consumidor confirma offsets después de guardar y exportar. Repeticiones se deduplican por hash/identidad de evento; versiones anteriores se archivan sin hacer retroceder el estado actual. No se ha verificado el comportamiento real del broker ni las dependencias.

## Seguridad y recuperación

Servidor y scripts exclusivamente localhost. Control de Host/Origin, JSON obligatorio para escrituras, máximo 2 MiB, esquemas estrictos y máximo 2.000 fichas por lote. URLs externas se validan pero no se descargan. Ollama usa un destino fijo local y no sigue redirecciones. Configuración de API académica externa requiere allowlist HTTPS explícita. UI usa nodos/textContent; CSP bloquea scripts externos e inline. Exportación CSV neutraliza fórmulas de hoja de cálculo.

Copias SQLite mediante API online de SQLite, comprobación de integridad y tablas antes de restaurar. Se crea copia preventiva de la base actual. Las copias de Configuración cubren los datos reales, no el laboratorio; para conservar este último copiar su carpeta con los procesos parados. No existe cifrado en reposo ni autenticación: proteger la sesión y los archivos del usuario de Windows. No exponer el servicio en una red compartida.
