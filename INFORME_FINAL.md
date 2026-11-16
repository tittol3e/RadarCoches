# Informe de implementación y verificación — 16/11/2026

## Resultado real

RadarCoches está implementado y funcionando localmente en `C:\Users\ia\Desktop\INGESTA DATOS\RadarCoches`, http://127.0.0.1:8765. Arranque por `iniciar_radarcoches.bat` o `iniciar_radarcoches.ps1`; parada por `detener_radarcoches.ps1`. La aplicación no exige Docker ni IA. No se ha publicado, contratado, pagado ni modificado ningún repositorio remoto.

**No se da por terminado el alcance completo:** falta ejecutar el flujo distribuido dlt/Kafka/DuckDB/Parquet. Sus adaptadores están escritos pero faltan dependencias instaladas y motor Docker. El informe diferencia esa carencia de la actividad local demostrada.

## Implementación

Backend modular con modelos Pydantic, persistencia SQLite y servicios separados. Interfaz HTML/CSS/JS con Dashboard, Radar, Tasador, Taller y piezas, Rentabilidad, Operaciones, Laboratorio y Configuración. Importación atómica CSV/JSON y manual; historial de precios, identidad por fuente/ID/URL, filtros, favoritos y notas. No se marcan anuncios comprobados al refrescar fuentes no conectadas.

Tasador basado en comparables seleccionados, fechados y comprobados. Mínimo tres; rechazo por carencia de datos, similitud o antigüedad. Ajuste monetario de km solo a partir de grupos homogéneos explícitamente documentados; sin extrapolación. Fichas integradas muestran costes, confianza, riesgos y margen pendiente, y conservan tasaciones con parámetros y resultados. Escenarios y negociación son hipótesis configurables.

Motor financiero Decimal independiente de IA, con partidas, gastos pendientes, impuestos incompatibles rechazados y máximo de compra inverso con base fiscal mínima. Referencias oficiales consultadas y fechadas; no aplicación fiscal automática. Taller registra daños declarados y presupuestos por categoría, fecha y evidencia de compatibilidad. No inventa precios ni presupuestos.

Operaciones conservan negociación, inspección, gastos y etapas; compras/ventas requieren importes y fechas. Solo operaciones vendidas generan resultado realizado. IA desactivada, adaptador exclusivo Ollama local, sin proveedores remotos/de pago ni descarga de modelos. Copias verificadas/restaurables y exportaciones sin credenciales.

Laboratorio separado con generador coherente reproducible, dos APIs, paginación, fechas, cursores, outbox, consumidor idempotente, historial completo, reintentos e interrupción/reanudación. Modo ejecutado SQLite explícito; no se disfraza de Kafka.

## Pruebas ejecutadas

| Ejecución | Resultado | Evidencia |
|---|---|---|
| unittest aplicación y pipeline | 52 pruebas, OK | `docs/evidencias/aplicacion_pipeline.txt` |
| unittest prototipo recuperado | 2 pruebas, OK | `docs/evidencias/prototipo_recuperado.txt` |
| Edge headless real | 29 comprobaciones, OK; cero errores JavaScript | `docs/evidencias/pruebas_navegador.json` |
| Dos APIs en procesos HTTP localhost | Ambas sirven 5 cambios y paginación/validación, OK | `docs/evidencias/apis_http.json` |
| pip check | Sin dependencias rotas | `docs/evidencias/dependencias.txt` |
| compileall | Salida 0 | `docs/evidencias/compilacion.txt` |
| Scripts arranque/parada/reinicio | Ejecutados correctamente después de corregir WMI | `docs/evidencias/servidor_final.json` y `data/radar.pid.json` |
| Demo revisiones CLI PowerShell | 10 → 12 → 12 → 12; dos precios actualizados | `data/laboratorio/resultado_revisiones.json` |
| Demo volumen CLI PowerShell | 1.000 → 1.050 → 1.050; 20 precios actualizados | `data/laboratorio/resultado_volumen.json` |
| Integración distribuida | NO ejecutada; salida de bloqueo explícita | `scripts/run_distributed.py` informa falta de dependencias |
| Ollama/modelo real | NO ejecutado | Se probaron desactivación, rechazo de proveedores y fallo sin pérdida |
| pytest | NO ejecutado | No disponible offline; se usó unittest, tests compatibles con pytest |

Las 29 comprobaciones de Edge incluyen navegación de ocho pantallas, guardado/edición/historial, prevención de ejecución XSS, simulación con margen 2.500 €, daños sin precios, presupuesto fechado/confirmado y edición, creación de operación, tasación rechazada sin evidencia y calculada con tres comparables, tasación vinculada persistente y recálculo del beneficio objetivo sin guardar automáticamente. Se comprobó ancho móvil de 390 px sin desbordamiento horizontal. Datos de prueba en carpetas temporales, nunca en el Radar personal.

Capturas inspeccionadas: `navegador-dashboard.png`, `navegador-radar.png`, `navegador-movil.png`, `navegador-movil-configuracion.png` en `docs/evidencias/`. La prueba de navegador usa un perfil temporal Edge; su bandera de sandbox es exclusiva del navegador de prueba, no modifica configuración de Windows ni del navegador del usuario.

## Trazabilidad de requisitos de pruebas

| Requisito solicitado | Comprobación ejecutada |
|---|---|
| 1 Inicio sin IA | test_start_without_ai_and_empty_real_dashboard + navegador |
| 2,3 Guardado y fuente | test_manual_persistence_restart_and_provenance; importación CSV/JSON |
| 4 Duplicados sin fusionar otros coches | test_duplicate_safe_and_distinct_vehicles; claves contradictorias |
| 5 Historial | test_price_history_and_filter + edición en navegador |
| 6 Fuentes no conectadas | dashboard y test_withdrawn_stays_withdrawn_after_import_refresh |
| 7 Retirado no reactivado | test_withdrawn_stays_withdrawn_after_import_refresh |
| 8 Sin inventar tasación | test_insufficient_comparables_no_value + navegador |
| 9 Kilometraje con evidencia | test_comparable_dedup_observation_and_mileage_evidence |
| 10,11 Gastos/objetivo | test_financial_example_cost_and_target_change + navegador |
| 12 Parámetros fiscales/inversión | test_tax_inverse_floor_and_no_incompatible_tax; no acreditación de liquidación jurídica completa |
| 13,14 Daños/compatibilidad | test_workshop_no_invented_quotes_critical; test_parts_compatibility_and_confirmed_costs |
| 15,16 Persistencia/beneficio realizado | test_operations_persist_only_sold_profit |
| 17 DEMO separado | test_lab_never_real_radar; revisión servidor final con Radar vacío |
| 18 IA pago desactivada | test_ai_paid_and_external_disabled |
| 19 Ingesta sin duplicar | test_revisions_10_12_12_12_with_verified_updates y test_volume_1000_50_20; solo transporte local |
| 20 Copia restaurable | test_backup_restore_real_database |
| 21 Fallos externos conservan datos | test_ai_error_persists_data_no_fallback; test_external_error_preserves_cursor_and_outbox |
| 22 Botones/formularios | 29 comprobaciones navegador real; no equivale a comprobar todos los casos posibles |

También se probaron límites de tamaño, Host/Origin, tipos de contenido, SQL parametrizado, URLs peligrosas, fechas, no finitos, rollback del lote, catálogo, snapshots, replay y eventos desordenados. La suite no es una auditoría de seguridad externa.

## Correcciones observadas

La primera suite de aplicación detectó una mezcla Decimal/float en valores por defecto y conexiones SQLite no cerradas en Windows. Se corrigieron validando defaults Pydantic y cerrando explícitamente conexiones; la suite completa posterior pasa. La prueba del fallo IA inicialmente interceptaba también al TestClient; se aisló el transporte del adaptador y se verificó la ruta de error real de la aplicación. Las dos pruebas recuperadas también requirieron cerrar conexiones para liberar archivos en Windows; se conserva copia de los originales.

El primer script de parada falló porque WMI está denegado. Se sustituyó por PID+hora de creación+ejecutable, registrando también el intérprete hijo de `.venv`; se ejecutó arranque/parada/reinicio correctamente. Las revisiones sobre un laboratorio ya avanzado no vuelven a diez: conservan doce por idempotencia. Para demostrar 10/12/12/12 se usa el espacio nuevo del comando `demo`, sin borrar datos existentes.

## Continuación necesaria

Seguir [CONTINUAR_CODEX.md](CONTINUAR_CODEX.md). Instalar módulos Big Data con una terminal que disponga de red normal y abrir Docker Desktop; ejecutar revisiones, volumen, fallos, offsets y lectura real Parquet por el circuito distribuido. Fijar versiones instaladas y actualizar informes. Mantener portales sin conexión hasta tener autorización. Ollama sigue opcional y desactivado hasta verificar modelo local.

No se han añadido anuncios de ejemplo al Radar. La última verificación del servidor confirmó cero anuncios reales, IA desactivada, cero fuentes remotas conectadas y laboratorio sintético en revisión 3 con doce anuncios y cero eventos pendientes.

La apertura autom?tica del navegador desde el entorno devolvi? Acceso denegado. El servidor s? funciona; el script lo informa y ofrece abrir la URL manualmente, sin considerar fallido el arranque. Las pruebas headless de Edge s? se ejecutaron.
