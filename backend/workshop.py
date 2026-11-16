"""Deterministic extraction of declared damage; no price/compatibility inference."""
RULES = [
    (('puerta','aleta','paragolpes','chapa'),'Carrocería','Panel o reparación por determinar',False),
    (('aire acondicionado','climatizador'),'Climatización','Diagnosis antes de elegir compresor/fuga',False),
    (('neumático','neumatico'),'Neumáticos','Medidas, índices y homologación pendientes',True),
    (('freno','abs'),'Frenos','Diagnosis y referencia por verificar',True),
    (('airbag','estructur','chasis','larguero'),'Seguridad estructural/retención','Revisión profesional imprescindible',True),
    (('motor','embrague','cambio','aceite'),'Mecánica','Diagnosis, código motor y alcance pendientes',False)
]
def analyze(description):
    text=description.casefold()
    found=[]
    for terms,name,piece,critical in RULES:
        matched=[t for t in terms if t in text]
        if matched:
            found.append({'damage':name,'matched_terms':matched,'possible_parts':piece,'critical':critical,
                          'cost':None,'compatibility':'pendiente','declared_only':True})
    return {'damages':found,'description':description,'warnings':[
        'Extracción por palabras clave de una declaración; puede incluir negaciones o referencias sin avería. Corrija antes de guardar.',
        'Sin diagnosis ni presupuestos no hay coste confirmado.','Elementos críticos requieren revisión profesional.'],
        'required_compatibility':['generation','engine','body','side','doors','oem','evidence'],
        'pending_costs':['piezas','mano de obra','pintura','diagnosis']}

