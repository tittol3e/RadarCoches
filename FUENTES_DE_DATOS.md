# Fuentes de datos y reglas

Estado comprobado: 16/11/2026. No hay claves, contratos ni APIs de inventario autorizadas configuradas.

| Fuente | Estado | Método utilizable ahora |
|---|---|---|
| Wallapop | No conectada | Ficha manual, enlace, CSV/JSON aportado legítimamente |
| Milanuncios | No conectada | Ficha manual, enlace, CSV/JSON |
| Coches.net | No conectada | Ficha manual, enlace, CSV/JSON |
| AutoScout24 | No conectada | Ficha manual, enlace, CSV/JSON |
| Recambio Verde, Catoira, Desguace Miguel | Sin conector | Registrar presupuesto/enlace, fecha y compatibilidad manualmente |
| Mobile.de / Car & Classic | Futuro | Sin conexión implementada |
| APIs académicas DEMO | Operativas localmente | Datos sintéticos reproducibles; exclusivamente laboratorio |

`Buscar / Actualizar oportunidades` consulta los adaptadores y muestra su indisponibilidad. No hace scraping, no elude CAPTCHAs, no inventa resultados ni cambia fechas de comprobación. Una importación manual no verifica inventario ni disponibilidad. Las URLs se abren por decisión del usuario, no se descargan automáticamente desde el backend.

Cada anuncio conserva su fuente y procedencia de campos. Una ficha repetida requiere identidad fuente+ID o URL; similitud no basta para fusionar. Los comparables exigen URL y observación fechada; marcar comprobado es una declaración del usuario, no una verificación independiente del sistema.

Para incorporar una API real: obtener autorización y documentación, implementar `search`, `fetch_if_authorized`, `status`, `usage`, validar esquema y errores, límites y cuotas; registrar procedencia/fechas sin mezclar datos académicos. Los resultados de buscadores o alertas no están implementados como conectores y no se presentan como inventario en tiempo real.

## Referencias fiscales consultadas

Las reglas guardan fecha y enlace. Se muestran como referencia y se seleccionan manualmente:

- [Agencia Tributaria de Andalucía: preguntas frecuentes](https://www.juntadeandalucia.es/organismos/atrian/areas/informacion-tributaria/impuestos/preguntas-frecuentes/impuestos-transmisiones-actos/aplicar-tp.html): modelo 621 y referencia de tipo general 4%.
- [Ley andaluza 5/2021 en BOE](https://www.boe.es/buscar/act.php?id=BOE-A-2021-17915): referencia 8% para determinados turismos/todoterrenos con más de 15 caballos fiscales; revisar siempre supuestos aplicables y reglas reducidas.
- [DGT: cambio de titularidad](https://sede.dgt.gob.es/export/sites/dgt/.galleries/hojas-informativas/vehiculo/01/01-Cambio-titularidad-vehiculo.pdf): referencia de tasa 1.5 ordinaria 55,70 €, con otros supuestos distintos.

No se deduce potencia fiscal de CV/kW; base fiscal, exenciones, actividad profesional, factura, IVA/REBU y garantía necesitan comprobación específica. La calculadora no resuelve el tratamiento jurídico/fiscal completo y no añade simultáneamente ITP a una compra configurada como profesional sujeta a factura con IVA.

Fuentes técnicas de la integración opcional: [dlt incremental](https://dlthub.com/docs/general-usage/incremental-loading), [Apache Kafka Docker](https://kafka.apache.org/41/getting-started/docker/) y [DuckDB Parquet](https://duckdb.org/docs/current/guides/file_formats/parquet_export). Haber consultado documentación no equivale a haber ejecutado la integración.
