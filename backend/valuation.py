"""Comparable asking-price estimation; never fabricates transaction prices."""
from datetime import datetime, timezone
from decimal import Decimal
from statistics import median
from .calculations import calculate, money
from .schemas import Calculation

INSUFFICIENT = 'No existe una tasación fiable con los datos disponibles.'

def evaluate(request, comparables):
    v = request.vehicle
    risks = ['Los comparables son precios solicitados, no precios reales de venta.',
             'Inspección mecánica, titularidad y cargas pendientes de comprobar.']
    candidates, rejected = [], []
    wanted = set(request.comparable_ids)
    urls = set()
    for c in comparables:
        reason = None
        if wanted and c['id'] not in wanted:
            continue
        if c['brand'].casefold() != v.brand.casefold() or c['model'].casefold() != v.model.casefold():
            reason = 'Marca/modelo diferentes'
        elif not c.get('verified') or c.get('availability') in ('withdrawn','sold'):
            reason = 'No verificado o retirado'
        elif v.year is None or v.km is None:
            reason = 'Vehículo objetivo sin año/kilómetros'
        elif abs(c['year']-v.year) > 2:
            reason = 'Año distante (>2)'
        elif v.version and c.get('version','') != v.version:
            reason = 'Versión diferente/no comprobada'
        elif any(getattr(v,f) and c.get(f) != getattr(v,f) for f in ('generation','engine','fuel','transmission','body')):
            reason = 'Características técnicas diferentes/no comprobadas'
        elif (datetime.now(timezone.utc)-datetime.fromisoformat(c['observed_at'])).days > 90:
            reason = 'Observación de más de 90 días'
        elif c['canonical_url'] in urls:
            reason = 'Misma URL; no cuenta dos veces'
        if reason:
            rejected.append({'id':c['id'],'reason':reason})
        else:
            urls.add(c['canonical_url'])
            candidates.append(c)
    if len(candidates) < 3:
        return {'reliable':False,'message':INSUFFICIENT,'confidence':'insuficiente','risks':risks,
                'comparables_used':[],'rejected':rejected,'available_count':len(candidates)}

    # Only fit mileage from homogeneous-year/version/condition/equipment groups.
    # Cross-sectional relationship is evidence, not a causal wear allowance.
    groups = {}
    for c in candidates:
        if any(not c.get(f) for f in ('version','generation','engine','fuel','transmission','condition','equipment','province')):
            continue
        key = tuple(c.get(f) for f in ('year','version','generation','engine','fuel','transmission','condition','equipment','province'))
        groups.setdefault(key,[]).append(c)
    slopes = []
    for group in groups.values():
        for i,a in enumerate(group):
            for b in group[i+1:]:
                delta = b['km']-a['km']
                if abs(delta) >= 30000:
                    slopes.append((Decimal(str(b['price']))-Decimal(str(a['price'])))/Decimal(delta))
    slope = median(slopes) if len(slopes) >= 3 else None
    if slope is not None and slope >= 0:
        slope = None
    used=[]
    for c in candidates:
        distance = abs(v.km-c['km'])
        if slope is None and distance > max(40000,int(v.km*.25)):
            rejected.append({'id':c['id'],'reason':'Kilometraje distante sin evidencia de ajuste'})
            continue
        if slope is not None and not min(x['km'] for x in candidates) <= v.km <= max(x['km'] for x in candidates):
            rejected.append({'id':c['id'],'reason':'Ajuste exigiría extrapolar kilómetros'})
            continue
        price = Decimal(str(c['price']))
        adjusted = price + (slope*Decimal(v.km-c['km']) if slope else 0)
        if adjusted <= 0:
            continue
        # Weight similarity; no invented euro corrections for region or equipment.
        weight = Decimal(1)/(1+Decimal(abs(c['year']-v.year))+Decimal(distance)/Decimal(100000))
        used.append(dict(c,adjusted_price=money(adjusted),similarity=float(weight),adjustment_reason='Relación observada en grupos homogéneos' if slope else 'Sin ajuste monetario; ponderación por cercanía de año/km'))
    if len(used)<3:
        return {'reliable':False,'message':INSUFFICIENT,'confidence':'insuficiente','risks':risks,'comparables_used':used,'rejected':rejected}
    prices=sorted(c['adjusted_price'] for c in used)
    central=sum((c['adjusted_price']*Decimal(str(c['similarity'])) for c in used))/sum(Decimal(str(c['similarity'])) for c in used)
    low,high=prices[0],prices[-1]
    factor=1-request.discount_pct/100
    resale=[money(x*factor) for x in (low,central,high)]
    results=[calculate(Calculation(purchase=request.purchase,resale=p,target_profit=request.target_profit,
                    costs=request.costs,tax_rate=request.tax_rate,tax_base_floor=request.tax_base_floor)) for p in resale]
    max_buy=results[0]['maximum_purchase']
    risks += ['Descuento de reventa y oferta inicial son hipótesis configuradas por el usuario, no descuentos observados.',
              'Región, estado y equipamiento no reciben ajustes monetarios sin evidencia; comprobar diferencias individualmente.']
    if v.mechanical_condition is None or v.maintenance is None:
        risks.append('Estado mecánico o mantenimiento no documentados')
    return {'reliable':True,'confidence':'baja' if len(used)<6 else 'media',
            'asking_range':[min(Decimal(str(c['price'])) for c in used),max(Decimal(str(c['price'])) for c in used)],
            'resale_range':[resale[0],resale[2]],'resale_central':resale[1],
            'maximum_purchase':max_buy,'opening_offer':money(max_buy*(1-request.opening_discount_pct/100)) if max_buy is not None else None,
            'negotiation_range':[money(max_buy*(1-request.opening_discount_pct/100)),max_buy] if max_buy is not None else None,
            'scenarios':dict(zip(('pessimistic','central','optimistic'),results)),
            'comparables_used':used,'rejected':rejected,'mileage_evidence':{'slope_eur_per_km':slope,'pairs':len(slopes)},
            'hypothetical':True,'risks':risks}

