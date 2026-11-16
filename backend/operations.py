from decimal import Decimal
from datetime import date
from .calculations import money

def stats(operations):
    sold=[o for o in operations if o['stage']=='Vendido']
    bought=[o for o in operations if o['stage'] in ('Comprado','Vendido')]
    profit=Decimal(0)
    evolution=[]
    days=[]
    for o in sorted(sold,key=lambda x:x['sale_date']):
        costs=sum((Decimal(str(c['amount'])) for c in o['actual_costs'] if c['amount'] is not None),Decimal(0))
        margin=money(Decimal(str(o['sale_price']))-Decimal(str(o['purchase_price']))-costs)
        profit+=margin
        days.append((date.fromisoformat(o['sale_date'])-date.fromisoformat(o['purchase_date'])).days)
        evolution.append({'operation_id':o['id'],'date':o['sale_date'],'realized_profit':margin,'expected_margin':o.get('expected_margin')})
    return {'analyzed':sum(o['stage']!='Detectado' for o in operations),
            'discarded':sum(o['stage']=='No comprado' for o in operations),'completed':len(sold),
            'purchased':len(bought),'tracking':sum(o['stage'] not in ('Vendido','No comprado') for o in operations),
            'invested':money(sum((Decimal(str(o['purchase_price']))+sum((Decimal(str(c['amount'])) for c in o['actual_costs'] if c['amount'] is not None),Decimal(0)) for o in bought),Decimal(0))),
            'realized_profit':money(profit),'average_days_to_sell':sum(days)/len(days) if days else None,
            'evolution':evolution,'warning':'El beneficio realizado depende de que se registren todos los gastos reales e impuestos. Margen antes de impuestos sobre beneficio.'}

