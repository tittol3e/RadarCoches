# Estado del proyecto — 16/11/2026

## Actualización posterior: Kafka real validado

Se ha reparado el ConnectTimeout previo al arranque de la API DEMO A en 8771.
Las dependencias distribuidas ya están instaladas y Kafka responde en 9092.
La prueba real de revisiones, historial, reenvío y replay ha pasado con lectura
de DuckDB y Parquet. Informe: `INFORME_REPARACION_KAFKA.md`. Las referencias a
dependencias ausentes y motor detenido en el estado anterior son históricas.
Volumen distribuido también superado: 1.050 anuncios, 20 cambios de precio,
1.070 eventos únicos, reenvío y replay de 2.140 mensajes sin duplicados.
Las pruebas de caídas reales del broker/procesos siguen pendientes.

**Aplicación local operativa; proyecto completo todavía pendiente de validar la integración Big Data distribuida.** No se presenta ningún portal o servicio externo como conectado.

| Área | Estado real | Límites |
|---|---|---|
| Auditoría/recuperación | Ejecutada | Solo prototipo CSV local recuperado; sin Mac/ZIP/especificación anterior accesibles |
| FastAPI/SQLite/UI | Operativa y probada | Localhost, ocho pantallas responsive; sin publicación |
| Radar | Operativo manual/CSV/JSON | Sin inventario remoto. Búsquedas clásico/deportivo son heurísticas sobre datos aportados |
| Tasador | Operativo y probado | Requiere comparables comprobados; resultados hipotéticos y confianza limitada; catálogo personal editable, no universal oficial |
| Fichas y tasaciones | Integradas | Guardan instantáneas, parámetros, fuentes y riesgos; deben revisarse de nuevo antes de operar |
| Rentabilidad | Operativa y probada | Parámetros fiscales manuales, referencias fechadas; no asesoría fiscal ni liquidación profesional completa |
| Taller | Operativo y probado | Extracción por palabras clave, no diagnosis; compatibilidad confirmada por usuario con evidencia, sin consulta OEM automática |
| Operaciones/estadísticas | Operativas y probadas | Resultado realizado solo al vender; depende de registrar todos los gastos reales |
| IA | Adaptador local y controles implementados | Desactivada; sin Ollama/modelo real verificado. No Gemini/Groq/OpenAI ni pagos |
| Laboratorio local | Implementado y probado | APIs FastAPI, outbox y consumidor SQLite; etiqueta NO dlt/NO Kafka |
| dlt/Kafka/DuckDB/Parquet | Código de integración escrito | Dependencias no instalables por red restringida y motor Docker no disponible. Sin ejecución distribuida acreditada |
| Seguridad/copias | Implementadas y probadas | Sin cifrado ni login; no exponer fuera de localhost; backup real separado de carpeta académica |
| Scripts Windows | Arranque/parada/reinicio y demo probados | WMI sustituido por Get-Process. Script distribuido falla explícitamente por dependencia ausente |
| Pruebas | 52 aplicación/pipeline + 2 recuperadas; 29 comprobaciones navegador | pytest no ejecutado; unittest sí. HTTP real de dos APIs probado. Sin broker/modelo IA reales |

## Bloqueos externos

La política del entorno deniega conexiones pip externas con WinError 10013. Se instalaron dependencias principales desde caché en `.venv`, sin privilegios ni cambios globales. No estaban disponibles offline dlt, DuckDB, kafka-python o pytest. Docker cliente existe, motor no responde. Falta habilitar un entorno normal de instalación y arrancar Docker Desktop, según `CONTINUAR_CODEX.md`.

No están conectados los portales por falta de acceso autorizado; esto se cubre funcionalmente con importaciones legítimas, como permite la especificación. Recambios siguen con presupuestos manuales. Los proveedores IA remotos no se ofrecen porque no se ha verificado/autorizado una integración gratuita adecuada.

## Pendientes concretos

### Continuación: práctica guiada y verificación distribuida

- Laboratorio simplificado con explicación, cuatro pasos ordenados, resultados
  en lenguaje sencillo y prueba de volumen separada. Guía: `GUIA_DEMOSTRACION.md`.
- Ejecutor distribuido ampliado para revisiones, `--volume`, reenvíos y replay
  con grupo nuevo. Verifica contenido completo, versiones, historial y lectura
  real del Parquet; conserva informe incluso ante fallo.
- Topics separados por ejecución para evitar mezclar escenarios con los mismos
  identificadores. Exportación analítica por lotes antes de confirmar offsets.
- Los contratos de confirmación y recuperación se prueban con dobles de Kafka;
  estas pruebas no acreditan un broker real.
- Se ha reintentado instalar: persiste WinError 10013. Docker sigue sin motor.
  La ejecución distribuida falla explícitamente, con evidencia guardada.


1. Instalar dependencias Big Data en `.venv`, fijar versiones reales compatibles y ejecutar revisiones y volumen por dlt/Kafka/DuckDB/Parquet.
2. Comprobar offsets/ACK/replay/interrupción reales del broker y consumidores, y lectura del Parquet generado.
3. Ejecutar pytest cuando esté disponible y pruebas del adaptador Ollama contra un modelo local si se decide activarlo.
4. Añadir conectores de portales únicamente con método permitido, autorizado y probado.

No hay anuncios inventados en el Radar: cero registros reales al verificar la entrega. El laboratorio persistente queda en revisión 3 con 12 anuncios sintéticos, dos precios actualizados y ningún evento pendiente. Las demos CLI guardan sus espacios independientes.
