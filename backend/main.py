import csv
import io
import json
import sqlite3
import threading
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
from .config import DATA, BACKUPS, FRONTEND, MAX_BODY
from .repository import Repository, Conflict
from .schemas import Listing, Comparable, Calculation, Valuation, Quote, Operation, Vehicle, Strict, Cost, now
from .providers import PROVIDERS
from .calculations import calculate
from .valuation import evaluate
from .workshop import analyze
from .operations import stats
from .ai import AI
from .taxes import RULES

class ImportRequest(Strict):
    format: str
    content: str = Field(max_length=MAX_BODY)

class TextRequest(Strict):
    description: str = Field(max_length=20000)

class AIText(Strict):
    text: str = Field(min_length=1,max_length=16000)

class AIConfig(Strict):
    provider: str
    model: str = ''

class Restore(Strict):
    name: str = Field(max_length=150)
    confirm: bool = False

class Assessment(Strict):
    listing_id: int
    valuation: Valuation

def classification(item):
    if item['availability'] in ('withdrawn','sold'):
        return {'state':'DESCARTAR','reason':'Anuncio retirado o vendido; no se presupone disponibilidad.'}
    if item['damages']:
        return {'state':'REVISAR CON MECÁNICO','reason':'Daños declarados; alcance, seguridad y costes pendientes de diagnosis.'}
    if item['verification']=='unverified' or any(item.get(k) is None for k in ('price','year','km')):
        return {'state':'DATOS INSUFICIENTES','reason':'Faltan datos esenciales o comprobación. No hay evidencia para recomendar compra.'}
    return {'state':'INVESTIGAR','reason':'Datos aportados; comparar precios, revisar cargas, estado y costes antes de decidir.'}

def create_app(data_dir=None, backups_dir=None):
    data_dir=Path(data_dir or DATA)
    backups_dir=Path(backups_dir or BACKUPS)
    repo=Repository(data_dir/'radar.sqlite')
    ai=AI(repo)
    lock=threading.RLock()
    lab_lock=threading.Lock()
    app=FastAPI(title='RadarCoches',version='0.1.0',docs_url=None,redoc_url=None)
    app.state.repo=repo
    from .lab_analytics import create_lab_analytics_router
    app.include_router(create_lab_analytics_router(data_dir/'laboratorio'))

    @app.get('/api/docs',include_in_schema=False,response_class=HTMLResponse)
    def api_docs():
        import html
        paths=app.openapi()['paths']
        rows=''.join('<tr><td>'+html.escape(method.upper())+'</td><td>'+html.escape(path)+'</td><td>'+html.escape(info.get('summary',''))+'</td></tr>'
                     for path,methods in paths.items() for method,info in methods.items())
        return '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>API RadarCoches</title><link rel="stylesheet" href="/static/styles.css"><body><main><h1>API local RadarCoches</h1><p>Contrato completo con tipos y campos: <a href="/openapi.json">OpenAPI JSON</a>. Peticiones de escritura JSON; solo localhost. Sin recursos CDN.</p><p><a href="/">Volver a RadarCoches</a></p><table><thead><tr><th>Método</th><th>Ruta</th><th>Función</th></tr></thead><tbody>'+rows+'</tbody></table></main></body></html>'

    @app.middleware('http')
    async def local_security(request,call_next):
        host=request.headers.get('host','').split(':')[0]
        if host not in ('127.0.0.1','localhost','testserver'):
            return JSONResponse({'detail':'Solo localhost'},status_code=403)
        origin=request.headers.get('origin')
        if origin and (urlsplit(origin).hostname not in ('127.0.0.1','localhost') or urlsplit(origin).netloc != request.headers.get('host')):
            return JSONResponse({'detail':'Origen no permitido'},status_code=403)
        if request.method in ('POST','PUT','PATCH','DELETE'):
            if not request.headers.get('content-type','').startswith('application/json'):
                return JSONResponse({'detail':'Use application/json'},status_code=415)
            size=0
            chunks=[]
            async for chunk in request.stream():
                size+=len(chunk)
                if size>MAX_BODY:
                    return JSONResponse({'detail':'Máximo 2 MiB por petición'},status_code=413)
                chunks.append(chunk)
            request._body=b''.join(chunks)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request,exc):
        return JSONResponse({'detail':str(exc)},status_code=409 if isinstance(exc,Conflict) else 422)
    @app.exception_handler(KeyError)
    async def missing(request,exc):
        return JSONResponse({'detail':str(exc)},status_code=404)
    @app.exception_handler(sqlite3.Error)
    async def database_error(request,exc):
        return JSONResponse({'detail':'Error de almacenamiento local; operación revertida. Revise permisos y espacio.'},status_code=503)

    def lab():
        from actividad_ingesta.pipeline.lab import Lab
        return Lab(data_dir/'laboratorio')

    @app.get('/api/health')
    def health():
        return {'status':'ok','local_only':True,'ai_optional':True,'process_id':os.getpid(),'instance_id':os.environ.get('RADAR_INSTANCE_ID','manual')}

    @app.get('/api/dashboard')
    def dashboard():
        items=repo.listings()
        drops=0
        for item in items:
            history=repo.listing(item['id'])['history']
            if len(history)>1 and history[-1]['price'] is not None and history[-2]['price'] is not None and Decimal(history[-1]['price'])<Decimal(history[-2]['price']):
                drops+=1
        return dict(stats(repo.rows('operations')),listings=len(items),price_drops=drops,
                    pending=sum(classification(x)['state']!='DESCARTAR' for x in items),
                    sources=[p.status() for p in PROVIDERS],ai=ai.status(),lab=lab().summary())

    @app.get('/api/sources')
    def sources():
        return [dict(p.status(),usage=p.usage()) for p in PROVIDERS]

    @app.post('/api/radar/refresh')
    def refresh():
        return {'results':[p.search({}) for p in PROVIDERS],
                'message':'No hay inventario remoto autorizado conectado. Los anuncios locales no se marcan como comprobados.'}

    @app.get('/api/listings')
    def listings(brand:str='',model:str='',province:str='',fuel:str='',transmission:str='',seller_type:str='',verification:str='',availability:str='',
                 year_min:int|None=None,year_max:int|None=None,price_min:float|None=None,price_max:float|None=None,
                 km_max:int|None=None,km_min:int|None=None,age_days:int|None=None,special:str='',favorite:bool=False):
        result=[]
        for x in repo.listings():
            if any(value and value.casefold() not in (x.get(key) or '').casefold() for key,value in [('brand',brand),('model',model),('province',province),('fuel',fuel),('transmission',transmission),('seller_type',seller_type),('verification',verification),('availability',availability)]):
                continue
            if favorite and not x['favorite']:
                continue
            if any(bound is not None and (x[key] is None or (float(x[key])<bound if lower else float(x[key])>bound)) for key,bound,lower in [('year',year_min,True),('year',year_max,False),('price',price_min,True),('price',price_max,False),('km',km_min,True),('km',km_max,False)]):
                continue
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(x['detected_at'])).days
            if age_days is not None and age>age_days:
                continue
            x['classification']=classification(x)
            history=repo.listing(x['id'])['history']
            x['price_drop']=len(history)>1 and history[-1]['price'] is not None and history[-2]['price'] is not None and Decimal(history[-1]['price'])<Decimal(history[-2]['price'])
            if special=='recent' and age>7: continue
            if special=='drops' and not x['price_drop']: continue
            if special=='urgent' and not x['urgency']: continue
            if special=='damaged' and not x['damages']: continue
            if special=='review' and x['classification']['state'] not in ('INVESTIGAR','DATOS INSUFICIENTES','REVISAR CON MECÁNICO'): continue
            if special=='classic' and (x['year'] is None or datetime.now().year-x['year']<30): continue
            if special=='sport' and not any(t in (x.get('version') or '').lower() for t in ('sport','gti','cupra','rs','gt')): continue
            if special=='undervalued':
                val=evaluate(Valuation(vehicle=Vehicle.model_validate({k:v for k,v in x.items() if k in Vehicle.model_fields})),_comparables())
                if not val['reliable'] or x['price'] is None or Decimal(x['price'])>=val['resale_range'][0]: continue
                x['classification']={'state':'INTERESANTE CONDICIONADO','reason':'Precio inferior al rango solicitado ajustado. Reventa hipotética; gastos, inspección y cargas pendientes.'}
            result.append(x)
        return result

    @app.post('/api/listings',status_code=201)
    def add_listing(item:Listing):
        with lock:
            saved=repo.save_listings([item])[0]
        return dict(repo.listing(saved['id']),action=saved['action'])

    @app.get('/api/listings/{item_id}')
    def listing_detail(item_id:int):
        item=repo.listing(item_id)
        quotes=[q for q in repo.rows('quotes') if q.get('listing_id')==item_id]
        snapshots=[s for s in repo.rows('assessments') if s['listing_id']==item_id]
        costs=[Cost(category=q['category']+': '+q['description'],
                    amount=Decimal(q['amount'])+Decimal(q['shipping']) if q['confirmed'] and q['amount'] is not None and (q['category']!='parts' or q['compatibility_verified']) else None,
                    verified=q['confirmed']) for q in quotes]
        costs.append(Cost(category='Otros costes e impuestos de operación pendientes de aportar',amount=None))
        auto=evaluate(Valuation(vehicle=Vehicle.model_validate({k:v for k,v in item.items() if k in Vehicle.model_fields}),
                    purchase=item['price'] or 0,costs=costs),_comparables())
        return dict(item,classification=classification(item),
                    comparables=[c for c in _comparables() if c.get('listing_id')==item_id],
                    quotes=quotes,latest_assessment=snapshots[0] if snapshots else None,
                    analysis={'valuation':auto,'costs':[c.model_dump(mode='json') for c in costs],
                              'warnings':['El análisis automático usa el precio publicado como compra hipotética. Complete costes, impuestos y beneficio objetivo en Tasador.',
                                          'Una tasación guardada es una instantánea: revise fechas de comparables y gastos antes de reutilizarla.']})

    @app.patch('/api/listings/{item_id}')
    def edit_listing(item_id:int,patch:dict):
        with lock:
            existing=repo.listing(item_id)
            editable={k:v for k,v in existing.items() if k in Listing.model_fields}
            editable.update(patch)
            repo.update_listing(item_id,Listing.model_validate(editable))
            return listing_detail(item_id)

    @app.post('/api/import')
    def import_listings(batch:ImportRequest):
        if batch.format=='json':
            try: rows=json.loads(batch.content)
            except json.JSONDecodeError as exc: raise ValueError('JSON inválido') from exc
            if not isinstance(rows,list): raise ValueError('Se requiere una lista JSON')
        elif batch.format=='csv':
            reader=csv.DictReader(io.StringIO(batch.content.lstrip('\ufeff')),strict=True)
            if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)):
                raise ValueError('Cabecera CSV inválida')
            rows=list(reader)
            for row in rows:
                if None in row: raise ValueError('Columnas CSV inconsistentes')
                for key in list(row):
                    if row[key]=='': row.pop(key)
                for key in ('damages','provenance'):
                    if key in row:
                        try: row[key]=json.loads(row[key])
                        except json.JSONDecodeError as exc: raise ValueError('JSON inválido en columna '+key) from exc
        else:
            raise ValueError('Formato permitido: csv o json')
        if len(rows)>2000: raise ValueError('Máximo 2000 fichas por lote')
        validated=[Listing.model_validate(row) for row in rows]
        with lock:
            results=repo.save_listings(validated)
        return {'results':results,'total':len(results),'atomic':True}

    def _comparables():
        from .security import canonical_url
        return [dict(c,canonical_url=canonical_url(c['url'])) for c in repo.rows('comparables')]

    @app.get('/api/comparables')
    def comparables(): return _comparables()
    @app.post('/api/comparables',status_code=201)
    def add_comparable(item:Comparable):
        from .security import canonical_url
        for prev in _comparables():
            if canonical_url(item.url)==prev['canonical_url']:
                raise Conflict('Comparable con la misma URL existente; edite el registro')
        return repo.save('comparables',item)
    @app.patch('/api/comparables/{item_id}')
    def edit_comparable(item_id:int,patch:dict):
        old=next((r for r in repo.rows('comparables') if r['id']==item_id),None)
        if not old: raise KeyError('Comparable no encontrado')
        old.pop('id')
        old.update(patch)
        item=Comparable.model_validate(old)
        from .security import canonical_url
        if any(c['id']!=item_id and c['canonical_url']==canonical_url(item.url) for c in _comparables()):
            raise Conflict('URL de comparable duplicada')
        return repo.save('comparables',item,item_id)
    @app.post('/api/valuations')
    def valuation(item:Valuation): return evaluate(item,_comparables())
    @app.post('/api/assessments')
    def save_assessment(item:Assessment):
        listing=repo.listing(item.listing_id)
        if (item.valuation.vehicle.brand.casefold(),item.valuation.vehicle.model.casefold()) != (listing['brand'].casefold(),listing['model'].casefold()):
            raise ValueError('La tasación debe corresponder al vehículo asociado')
        result=evaluate(item.valuation,_comparables())
        from fastapi.encoders import jsonable_encoder
        repo.save('assessments',{'listing_id':item.listing_id,'request':item.valuation.model_dump(mode='json'),
                                'result':jsonable_encoder(result),'created_at':now()})
        return result
    @app.post('/api/calculator')
    def calculator(item:Calculation): return calculate(item)
    @app.get('/api/tax-rules')
    def tax_rules(): return RULES

    @app.get('/api/catalog')
    def catalog(brand:str='',model:str='',generation:str='',version:str=''):
        rows=repo.rows('catalog')
        def choices(field,filters):
            return sorted({r[field] for r in rows if r.get(field) and all(not v or r.get(k)==v for k,v in filters.items())})
        return {'brands':choices('brand',{}),'models':choices('model',{'brand':brand}),
                'generations':choices('generation',{'brand':brand,'model':model}),
                'versions':choices('version',{'brand':brand,'model':model,'generation':generation}),
                'engines':choices('engine',{'brand':brand,'model':model,'generation':generation,'version':version}),
                'message':'Catálogo local editable; puede escribir cualquier vehículo. No es un catálogo oficial completo.'}
    @app.post('/api/catalog')
    def add_catalog(item:Vehicle):
        return repo.save('catalog',item)

    @app.post('/api/workshop/analyze')
    def workshop(item:TextRequest): return analyze(item.description)
    @app.get('/api/quotes')
    def quotes(): return repo.rows('quotes')
    @app.post('/api/quotes',status_code=201)
    def add_quote(item:Quote): return repo.save('quotes',item)
    @app.patch('/api/quotes/{item_id}')
    def edit_quote(item_id:int,patch:dict):
        old=next((r for r in repo.rows('quotes') if r['id']==item_id),None)
        if not old: raise KeyError('Presupuesto no encontrado')
        old.pop('id');old.update(patch)
        return repo.save('quotes',Quote.model_validate(old),item_id)
    @app.get('/api/quotes/costs/{listing_id}')
    def quote_costs(listing_id:int):
        return {'costs':[{'category':q['category']+': '+q['description'],'amount':Decimal(q['amount'])+Decimal(q['shipping']),'verified':True}
                         for q in repo.rows('quotes') if q.get('listing_id')==listing_id and q['confirmed'] and (q['category']!='parts' or q['compatibility_verified'])],
                'warning':'Solo presupuestos confirmados y piezas con compatibilidad comprobada; otros costes pendientes.'}

    @app.get('/api/operations')
    def operations(): return repo.rows('operations')
    @app.post('/api/operations',status_code=201)
    def add_operation(item:Operation): return repo.save('operations',item)
    @app.patch('/api/operations/{item_id}')
    def edit_operation(item_id:int,patch:dict):
        old=next((r for r in repo.rows('operations') if r['id']==item_id),None)
        if not old: raise KeyError('Operación no encontrada')
        old={k:v for k,v in old.items() if k in Operation.model_fields}
        if 'listing_id' in patch and patch['listing_id']!=old['listing_id']:
            raise ValueError('No se permite cambiar el vehículo de una operación')
        old.update(patch)
        return repo.save('operations',Operation.model_validate(old),item_id)
    @app.get('/api/operations/{item_id}/history')
    def operation_history(item_id:int): return repo.operation_history(item_id)
    @app.get('/api/statistics')
    def statistics(): return stats(repo.rows('operations'))

    @app.get('/api/lab')
    def lab_summary():
        with lab_lock: return lab().summary()
    @app.post('/api/lab/revision/{revision}')
    def lab_revision(revision:int):
        if revision not in (0,1,2,3): raise ValueError('Revisión 0..3')
        with lab_lock: return lab().run_revision(revision)
    @app.post('/api/lab/volume')
    def volume():
        with lab_lock: return lab().volume_demo()
    @app.get('/api/ai')
    def ai_status(): return ai.status()
    @app.post('/api/ai/probe')
    def ai_probe(): return ai.probe()
    @app.put('/api/ai')
    def ai_config(item:AIConfig): return ai.configure(item.provider,item.model)
    @app.post('/api/ai/analyze')
    def ai_analyze(item:AIText): return ai.analyze(item.text)

    @app.get('/api/export')
    def export(format:str='json'):
        data=repo.listings()
        if format=='json':
            # Import-compatible listing export; backup covers all linked entities.
            rows=[{k:v for k,v in r.items() if k in Listing.model_fields} for r in data]
            return Response(json.dumps(rows,ensure_ascii=False),media_type='application/json',headers={'Content-Disposition':'attachment; filename=anuncios.json'})
        if format!='csv': raise ValueError('Formato no permitido')
        fields=list(Listing.model_fields)
        out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
        for row in data:
            clean={k:row.get(k) for k in fields}
            for k,v in clean.items():
                if isinstance(v,(dict,list)): clean[k]=json.dumps(v,ensure_ascii=False)
                elif isinstance(v,bool): clean[k]='true' if v else 'false'
                elif isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')): clean[k]="'"+v
            writer.writerow(clean)
        return Response('\ufeff'+out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=anuncios.csv'})

    @app.get('/api/backups')
    def backups():
        backups_dir.mkdir(parents=True,exist_ok=True)
        return [{'name':p.name,'bytes':p.stat().st_size} for p in sorted(backups_dir.glob('radar_*.sqlite'),reverse=True)]
    @app.post('/api/backups')
    def backup():
        with lock: return {'name':repo.backup(backups_dir)}
    @app.post('/api/backups/restore')
    def restore(item:Restore):
        if not item.confirm: raise ValueError('Restauración requiere confirm:true; sustituye los datos reales actuales y conserva copia de seguridad')
        with lock: return {'restored':item.name,'safety_backup':repo.restore(backups_dir,item.name)}

    @app.get('/')
    def index(): return FileResponse(FRONTEND/'index.html')
    app.mount('/static',StaticFiles(directory=FRONTEND),name='static')
    return app

app=create_app()
