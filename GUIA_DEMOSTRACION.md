# Cómo entender y demostrar la ingesta

La ingesta recoge datos y los mantiene disponibles para consultarlos. En este
proyecto recoge anuncios de coches desde dos fuentes de prueba. Los anuncios
son inventados y están separados de los coches que añadas al Radar.

## Demostración en la aplicación

Abre **Laboratorio de datos** y pulsa **Nueva práctica limpia**. La aplicación
separa la lectura de las APIs, la extracción y el consumo en SQLite. Después puedes
incorporar las altas, ver los cambios de precio y ejecutar el replay. Cada práctica
permanece en el selector. Consulta los pasos y el guion actualizado en la
[guía de presentación para el profesor](GUIA_PRESENTACION_PROFESOR.md).

## Qué decir al presentarlo

«Mi aplicación recoge anuncios de dos fuentes. Identifica cada anuncio por su
fuente y su identificador. Cuando aparece uno nuevo, lo añade. Cuando cambia,
actualiza su ficha y conserva el historial. Recuerda hasta dónde ha leído para
continuar en la siguiente ejecución. Repetir la lectura no duplica los datos.
Después podemos consultar esos anuncios y sus cambios».

Un **evento** representa un alta o actualización. El **cursor** funciona como un
marcapáginas de lectura. La **cola** conserva eventos pendientes. El **consumidor**
procesa esos eventos y guarda los anuncios.

## Qué está probado y qué falta

La práctica de la web utiliza APIs FastAPI en proceso y SQLite. Sirve para
demostrar lectura incremental, actualizaciones, historial, recuperación local y
ausencia de duplicados. No demuestra Kafka, dlt, DuckDB ni Parquet.

El circuito distribuido tiene su ejecutor separado:

```powershell
cd "C:\Users\ia\Desktop\INGESTA DATOS\RadarCoches"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/instalar.ps1 -BigData -Desarrollo
docker compose -f actividad_ingesta/docker-compose.yml up -d
powershell.exe -NoProfile -ExecutionPolicy Bypass -File iniciar_ingesta.ps1 -Modo distributed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File iniciar_ingesta.ps1 -Modo distributed -Volumen
```

Estos comandos requieren una terminal con acceso normal a Internet y Docker
Desktop iniciado. El ejecutor compara todos los anuncios y versiones con las
fuentes, comprueba el historial en DuckDB y lee el Parquet. También reenvía
eventos y vuelve a consumir con un grupo nuevo para detectar duplicados. Cada
ejecución usa un topic independiente y guarda su informe, tanto si pasa como
si falla, en `docs/evidencias/distribuido/`.

Actualización del 16/11/2026: las dependencias ya están instaladas y Kafka real
ha superado las revisiones, el historial, los reenvíos y el replay, con lectura
del Parquet. Se corrigió un fallo de comprobación de puertos previo al arranque
de las APIs. Consulta los resultados actuales en
[INFORME_REPARACION_KAFKA.md](INFORME_REPARACION_KAFKA.md).
Las interrupciones reales del broker y los procesos siguen pendientes; un
reenvío no acredita esas caídas.
