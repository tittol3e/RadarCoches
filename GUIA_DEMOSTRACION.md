# Cómo entender y demostrar la ingesta

La ingesta recoge datos y los mantiene disponibles para consultarlos. En este
proyecto recoge anuncios de coches desde dos fuentes de prueba. Los anuncios
son inventados y están separados de los coches que añadas al Radar.

## Demostración en la aplicación

1. Arranca `iniciar_radarcoches.bat` y abre **Laboratorio de datos**.
2. Lee la explicación inicial: leer → identificar → guardar → consultar.
3. Ejecuta los cuatro pasos de la práctica guiada. El siguiente paso se habilita
   al terminar el anterior. Los resultados se conservan al cerrar la aplicación.
4. Comprueba los totales: **10 → 12 → 12 → 12**. El tercer paso cambia dos precios.
5. Repite un paso: no aparecen anuncios duplicados. Repetir un paso anterior no
   retrocede los datos ni restaura precios antiguos.
6. Despliega los anuncios y eventos para ver identificadores, precios y versiones.
7. Ejecuta **Comprobar con 1.000 anuncios**. Deben quedar **1.050 únicos** y
   **20 precios actualizados**. Esta prueba usa un espacio separado.

Si los cuatro pasos ya aparecen completados, se trata de una ejecución anterior
guardada. Puedes repetirlos para demostrar la ausencia de duplicados; no volverán
a aparecer las altas como nuevas.

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
