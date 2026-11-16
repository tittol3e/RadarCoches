# Manual de usuario

## Primer arranque

Abrir `iniciar_radarcoches.bat` y visitar http://127.0.0.1:8765. El Radar empieza vacío: no hay coches precargados, IA obligatoria ni acceso automático a portales. El laboratorio está rotulado DEMO / DATOS SINTÉTICOS y usa datos independientes.

## Radar

1. Abrir Radar de anuncios y cumplimentar una ficha real obtenida legítimamente. Marca y modelo son obligatorios. Fuente e identificador permiten reconocer futuras actualizaciones; el enlace conserva la procedencia.
2. Dejar vacíos precio, año, kilómetros u otros campos desconocidos. No marcar disponible ni comprobado sin haberlo observado. Una comprobación requiere fecha con hora; el navegador añade la zona local al guardarla.
3. Guardar. La ficha conserva fecha de detección local, fuente y origen de campos. El sistema no visita el enlace.
4. Abrir ficha para editar, añadir favoritos, notas o desperfectos. Cambiar el precio genera historial. Un anuncio retirado no se reactiva al reimportar; solo una edición explícita del usuario puede cambiarlo.
5. Usar filtros por datos del vehículo, provincia, precio, kilómetros, edad desde detección, tipo de vendedor y verificación. Las búsquedas de urgencia se basan en lo declarado y no garantizan descuento. Clásico/deportivo son filtros orientativos, no certificaciones.

El botón Buscar / Actualizar oportunidades informa de los adaptadores. Actualmente no puede traer inventario remoto. Las clasificaciones explican la carencia de datos, necesidad de mecánico o investigación. Interesante condicionado exige evidencia comparativa y sigue sujeto a gastos y comprobaciones; nunca significa beneficio asegurado.

## CSV y JSON

En Radar seleccionar el formato y pegar contenido o cargar un archivo permitido. Máximo 2 MiB y 2.000 fichas. Un error invalida el lote completo, sin importaciones parciales silenciosas. Los campos API están en inglés y se describen en `/openapi.json`.

Cabecera CSV mínima: `source,external_id,url,brand,model,year,km,price,province`. Una columna opcional vacía es desconocida. `damages` y `provenance`, si se usan, contienen JSON válido; booleanos `true`/`false`. En JSON el documento debe ser una lista de objetos. `ejemplos/plantilla_anuncios.csv` contiene solo la cabecera; `ejemplos/plantilla_anuncios.json` contiene una lista vacía, sin anuncios ficticios que puedan confundirse con reales.

La identidad no se deduce del nombre del vendedor ni de las características similares. Una misma URL con otra marca/modelo se rechaza para revisión. Ante conflicto, corregir identificadores y procedencia. No incluir teléfonos, direcciones personales ni otros datos innecesarios.

## Tasador

Abrir una ficha y pulsar Tasar este vehículo, o seleccionar el vehículo en Tasador. También se puede introducir un vehículo libre. El catálogo personal empieza vacío; se amplía con marca/modelo/generación/versión/motor y admite escritura manual. Kilómetros numéricos y deslizador están sincronizados.

Registrar comparables observados: URL, fecha, precio solicitado, año, km y características. Marcar comprobado solo tras comprobar los datos. Se necesitan al menos tres comparables distintos, recientes y suficientemente similares. Seleccionarlos y completar gastos, beneficio objetivo y descuentos hipotéticos. El cambio de beneficio permite previsualizar el nuevo máximo sin guardar una tasación en cada pulsación. Guardar el cálculo asociado conserva una instantánea en la ficha.

Sin evidencia aparece «No existe una tasación fiable con los datos disponibles». Si existe, se muestran rango anunciado, reventa hipotética, escenarios, máximo, oferta inicial, confianza, riesgos y fuentes usadas/rechazadas. La diferencia de km solo genera ajuste monetario cuando hay grupos homogéneos documentados suficientes; no se inventa una depreciación por kilómetro. No se extrapola fuera de la evidencia. La reventa sigue siendo hipotética.

Las tasaciones guardadas pueden quedar desactualizadas. Revisar fechas, disponibilidad, estado, versión y cargas antes de reutilizarlas. No tomar el máximo de compra como recomendación para comprar.

## Rentabilidad

Introducir precio publicado como referencia, oferta/compra prevista, reventa hipotética, beneficio objetivo y gastos. Añadir cada concepto aplicable: transferencia, gestoría, informe, ITV, transporte, desplazamiento, combustible, seguro, reparación, piezas, mano de obra, pintura, preparación, publicación, venta, reserva, garantía u otros. Importe vacío significa pendiente; cero debe introducirse solo si es una hipótesis consciente o está comprobado.

Seleccionar tipo de operación. Los tipos y tasas oficiales se muestran con fuente/fecha; no se aplican automáticamente. Escribir el porcentaje aplicable y, cuando corresponda, la base fiscal mínima comprobada. Los caballos fiscales son independientes de los CV del motor. No sumar ITP sobre una compra profesional con factura sujeta a IVA. Para un impuesto fijo manual usar el campo `manual_tax` de la API; la interfaz permite registrar gastos fiscales manuales como concepto adicional evitando duplicarlos con un porcentaje.

Ejemplo exclusivamente hipotético: compra 10.000 €, reventa 14.000 € y gastos aportados 1.500 € sin impuesto adicional seleccionado → coste 11.500 € y margen 2.500 € antes de impuestos sobre el beneficio. Con objetivo 2.000 €, máximo 10.500 €. El programa no afirma que esos coches, gastos o precios existan.

Los presupuestos confirmados de Taller pueden añadirse a los gastos con un botón. Evitar duplicarlos si ya están incluidos en otro concepto. Costes pendientes dejan el precio máximo completo sin determinar. Revisar fiscalidad profesional con un asesor cuando proceda.

## Taller y piezas

Pegar una descripción para detectar palabras asociadas a daños. Es una extracción determinista y puede equivocarse con negaciones; revisar y corregir el texto. No equivale a diagnosis. Registrar por separado piezas, mano de obra, pintura y diagnosis; importe, envío, URL, fecha y alternativa nueva/usada/reparada.

Una pieza no se confirma como gasto por tener el mismo nombre: documentar generación, motor, carrocería, lado, puertas, OEM y evidencia. Si algo no aplica, justificarlo en el campo correspondiente. No confirmar sin presupuesto e importe fechados. La edición completa permite corregir compatibilidad e importes. Las partidas no confirmadas siguen pendientes y no se trasladan como gasto verificado.

Daños estructurales, airbags, frenos y otros elementos críticos requieren revisión profesional. No hay acceso automático a inventario de recambios ni presupuestos generados por el sistema.

## Mis operaciones

Crear seguimiento desde la ficha o pantalla Operaciones. Registrar etapas, oferta, respuesta, inspección y notas. Completar gastos previstos y reales como partidas separadas. Compra requiere precio y fecha; venta requiere compra previa, precio y fecha de venta no anteriores a la compra.

Solo Vendido genera resultado realizado: venta menos compra y gastos reales registrados. Los coches comprados aún sin vender no generan beneficio ganado. Si faltan impuestos o gastos no registrados, el resultado también será incompleto; completar todos antes de darlo por cerrado. Las estadísticas incluyen inversión, operaciones, descartes, duración y comparación de márgenes. El historial conserva actualizaciones.

## Laboratorio

La pantalla incluye ahora una práctica guiada: explica para qué sirve la ingesta,
habilita los pasos en orden y resume anuncios nuevos y precios actualizados.
La prueba de volumen se habilita al completar los cuatro pasos. Los detalles
técnicos se pueden desplegar cuando se necesiten. Para presentar el proyecto,
consulta [GUIA_DEMOSTRACION.md](GUIA_DEMOSTRACION.md).

Ejecutar revisiones 0, 1, 2 y 3 en orden desde la pantalla. Esperados: 10, 12, 12 y 12 anuncios; dos cambios de precio en revisión 2. Repetir no duplica. La prueba de volumen crea un espacio separado con 1.000 iniciales, 50 nuevos y 20 actualizaciones, para 1.050 únicos. Se pueden desplegar anuncios, eventos, ejecuciones y cursores.

El modo actualmente demostrado dice explícitamente outbox SQLite (NO Kafka) y extracción en proceso (NO dlt). Las consultas DuckDB dependen de la integración opcional y deben mostrar indisponibilidad mientras falten dependencias/resultados. Para comandos y continuación distribuida consultar `docs/INFORME_INGESTA.md`.

## IA y copias

Configuración permite desactivar IA completamente o seleccionar un modelo Ollama ya instalado en localhost. Comprobar conexión antes de usar; no se instala ni descarga el modelo. Se registran solicitudes, tokens cuando se informan y errores. No hay proveedor remoto ni de pago habilitado. La IA interpreta textos; no se usa para cálculos, impuestos, precios o compatibilidad.

Crear copia en Configuración antes de cambios importantes. Restaurar exige confirmación y genera copia preventiva. Incluye anuncios, operaciones y demás datos reales. Exportar CSV/JSON produce anuncios importables; para conservar operaciones y relaciones utilizar la copia SQLite. El laboratorio se conserva aparte copiando su carpeta con procesos detenidos. Guardar copias en un lugar privado; no se cifran.
