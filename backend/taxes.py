VERIFIED_AT = '2026-11-16'
RULES = {
    'checked_at': VERIFIED_AT,
    'region':'Andalucía',
    'automatic_application':False,
    'rules':[
        {'name':'ITP general bienes muebles','value':0.04,'unit':'rate','source':'https://www.juntadeandalucia.es/organismos/atrian/areas/informacion-tributaria/impuestos/preguntas-frecuentes/impuestos-transmisiones-actos/aplicar-tp.html','conditions':'Tipo general; comprobar supuestos reducidos y exenciones. Modelo 621 para vehículo usado cuando procede.'},
        {'name':'ITP turismos/todoterrenos >15 CV fiscales','value':0.08,'unit':'rate','source':'https://www.boe.es/buscar/act.php?id=BOE-A-2021-17915','conditions':'La potencia fiscal se obtiene de la ficha técnica, nunca de CV/kW del motor.'},
        {'name':'DGT transferencia ordinaria tasa 1.5','value':55.70,'unit':'EUR','source':'https://sede.dgt.gob.es/export/sites/dgt/.galleries/hojas-informativas/vehiculo/01/01-Cambio-titularidad-vehiculo.pdf','conditions':'Transferencia ordinaria de vehículo; ciclomotores y trámites adicionales distintos.'}
    ],
    'warnings':[
        'Valores de referencia consultados; seleccione manualmente parámetros aplicables y vuelva a verificar en la fecha de operación.',
        'La base imponible puede no coincidir con el precio de compra: aporte base fiscal comprobada. Tipos reducidos o exenciones no se infieren.',
        'Compra a profesional con factura: no añadir ITP a operación sujeta a IVA; indique precio total facturado.',
        'Actividad profesional: verificar alta, facturación, IVA o REBU cuando corresponda, obligaciones de garantía e impuestos sobre beneficio.',
        'Las tasas no se incluyen automáticamente en ningún cálculo.'
    ]
}
