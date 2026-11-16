"""Deterministic financial calculations. Money is Decimal, never binary float."""
from decimal import Decimal, ROUND_HALF_UP
from .schemas import Calculation

D = Decimal
def money(value):
    return D(str(value)).quantize(D('.01'),rounding=ROUND_HALF_UP)

def maximum_purchase(resale, additional, profit, rate=D(0), floor=D(0), fixed_tax=D(0)):
    budget = D(resale)-D(additional)-D(profit)-D(fixed_tax)
    if budget < rate*floor:
        return None
    # x + rate*max(x,floor) <= budget; floor is externally provided tax base.
    x = budget-rate*floor if budget <= floor*(1+rate) else budget/(1+rate)
    # Round down to avoid exceeding the budget.
    from decimal import ROUND_FLOOR
    return x.quantize(D('.01'),rounding=ROUND_FLOOR)

def calculate(c: Calculation):
    warnings = ['Escenario hipotético: precio anunciado o estimado no equivale a venta realizada.',
                'No constituye asesoramiento fiscal. Confirme base imponible, exenciones y obligaciones.']
    rate = c.tax_rate
    if c.transaction_type == 'professional' and rate != 0:
        raise ValueError('Compra con factura profesional: no sumar ITP a una operación sujeta a IVA. Use precio total facturado.')
    if c.manual_tax is not None and rate != 0:
        raise ValueError('Elija impuesto manual o porcentaje, no ambos')
    if c.transaction_type == 'private':
        warnings.append('ITP Andalucía: revisar modelo 621, potencia FISCAL, base y posibles tipos reducidos; no se deduce de CV/kW.')
    if c.transaction_type == 'business':
        warnings.append('Actividad habitual: facturación, impuestos sobre beneficio, IVA/REBU y garantía requieren determinación profesional; no calculados automáticamente.')
    missing = [cost.category for cost in c.costs if cost.amount is None]
    additional = sum((cost.amount for cost in c.costs if cost.amount is not None),D(0))
    tax = money(c.manual_tax if c.manual_tax is not None else rate*max(c.purchase,c.tax_base_floor))
    total = money(c.purchase+additional+tax)
    maximum = maximum_purchase(c.resale,additional,c.target_profit,rate,c.tax_base_floor,c.manual_tax or D(0))
    if missing:
        warnings.append('Costes pendientes: '+', '.join(missing)+'. El margen parcial no es una previsión completa.')
    if any(not cost.verified for cost in c.costs):
        warnings.append('Hay gastos hipotéticos o sin verificar')
    return {'purchase':money(c.purchase),'resale':money(c.resale),'additional_costs':money(additional),
            'tax':tax,'total_cost':total,'margin':money(c.resale-total),
            'maximum_purchase':maximum if not missing else None,'partial_maximum_purchase':maximum,
            'target_profit':money(c.target_profit),'missing_costs':missing,'complete':not missing,
            'scenario':c.scenario,'warnings':warnings,'tax_rate':rate,'tax_base':max(c.purchase,c.tax_base_floor)}

