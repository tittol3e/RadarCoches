# Informe de ingesta

El informe técnico completo y los comandos de reproducción están en [docs/INFORME_INGESTA.md](docs/INFORME_INGESTA.md).

Verificado localmente el 16/11/2026: revisiones 10 → 12 → 12 → 12; dos precios actualizados sin duplicados; volumen 1.050 únicos con 20 cambios. Veintitrés pruebas de pipeline y dos del prototipo recuperado cubren paginación, cursores, esquemas, reintentos, idempotencia, interrupción, reinicio y replay. Los datos nunca se añaden al Radar.

Modo ejecutado: APIs FastAPI en proceso, extracción Python y outbox/consumidor SQLite. **No se han ejecutado dlt, broker Kafka, DuckDB ni Parquet.** Sus adaptadores están escritos y falta validarlos con dependencias y motor Docker disponibles. La actividad académica distribuida completa permanece pendiente.

Evidencias reproducibles: `data/laboratorio/resultado_revisiones.json`, `data/laboratorio/resultado_volumen.json`, `actividad_ingesta/evidencias/` y `docs/evidencias/`. La pantalla Laboratorio muestra sus propios registros sintéticos persistentes.
