import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.schemas import Calculation, Listing, Valuation, Vehicle
from backend.calculations import calculate
from backend.valuation import evaluate, INSUFFICIENT
from backend.security import canonical_url

class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.app=create_app(self.root/'data',self.root/'backups')
        self.client=TestClient(self.app)
        self.base={'source':'wallapop','external_id':'evidence-test-1','url':'https://es.wallapop.com/item/test-1',
                   'brand':'SEAT','model':'Ibiza','year':2020,'km':100000,'price':'10000.00','province':'Cádiz'}
    def tearDown(self):
        self.client.close()
        self.temp.cleanup()
    def post(self,path,data):
        r=self.client.post(path,json=data)
        self.assertLess(r.status_code,300,r.text)
        return r.json()
    def add(self,**updates):
        return self.post('/api/listings',dict(self.base,**updates))
    def test_start_without_ai_and_empty_real_dashboard(self):
        self.assertEqual(self.client.get('/api/health').json()['status'],'ok')
        d=self.client.get('/api/dashboard').json()
        self.assertEqual(d['listings'],0)
        self.assertEqual(d['ai']['provider'],'disabled')
        self.assertTrue(all(not s['available'] for s in d['sources']))
        self.assertEqual(float(d['realized_profit']),0)
    def test_manual_persistence_restart_and_provenance(self):
        a=self.add()
        app2=create_app(self.root/'data',self.root/'backups')
        with TestClient(app2) as c:
            stored=c.get('/api/listings/'+str(a['id'])).json()
            self.assertEqual(stored['source'],'wallapop')
            self.assertIn('price',stored['provenance'])
            self.assertIsNone(stored['last_checked'])
    def test_duplicate_safe_and_distinct_vehicles(self):
        a=self.add()
        b=self.add()
        self.assertEqual(a['id'],b['id'])
        self.add(external_id='different',url='https://es.wallapop.com/item/test-2')
        self.assertEqual(len(self.client.get('/api/listings').json()),2)
        r=self.client.post('/api/listings',json=dict(self.base,model='Leon'))
        self.assertEqual(r.status_code,409)
    def test_canonical_tracking_removed_query_identity_retained(self):
        self.assertEqual(canonical_url('https://example.org/ad/12?utm_source=x#detail'),'https://example.org/ad/12')
        self.assertNotEqual(canonical_url('https://example.org/ad?id=1'),canonical_url('https://example.org/ad?id=2'))
    def test_price_history_and_filter(self):
        a=self.add()
        self.add(price='9000.00')
        detail=self.client.get(f"/api/listings/{a['id']}").json()
        self.assertEqual([float(r['price']) for r in detail['history']],[10000,9000])
        self.assertEqual(len(self.client.get('/api/listings?special=drops').json()),1)
        self.assertEqual(len(self.client.get('/api/listings?price_max=8000').json()),0)
    def test_withdrawn_stays_withdrawn_after_import_refresh(self):
        a=self.add(availability='withdrawn')
        self.add(availability='available')
        self.post('/api/radar/refresh',{})
        detail=self.client.get(f"/api/listings/{a['id']}").json()
        self.assertEqual(detail['availability'],'withdrawn')
        self.assertEqual(detail['classification']['state'],'DESCARTAR')
        self.assertIsNone(detail['last_checked'])
    def test_csv_json_import_and_atomic_rollback(self):
        self.post('/api/import',{'format':'csv','content':'source,external_id,brand,model,price\ncoches.net,1,SEAT,Ibiza,9999\n'})
        self.post('/api/import',{'format':'json','content':json.dumps([dict(self.base)])})
        self.assertEqual({x['source'] for x in self.client.get('/api/listings').json()},{'coches.net','wallapop'})
        r=self.client.post('/api/import',json={'format':'json','content':json.dumps([dict(self.base,external_id='other',url=None),dict(self.base,model='Other')])})
        self.assertEqual(r.status_code,409)
        self.assertEqual(len(self.client.get('/api/listings').json()),2)
    def test_invalid_input_and_urls(self):
        for url in ('javascript:alert(1)','http://127.0.0.1/a','http://192.168.1.1/a','http://localhost/a','https://user:pass@example.org/a','http://[::1]/a'):
            self.assertEqual(self.client.post('/api/listings',json=dict(self.base,url=url)).status_code,422,url)
        self.assertEqual(self.client.post('/api/listings',json=dict(self.base,km=-1)).status_code,422)
        self.assertEqual(self.client.post('/api/listings',json=dict(self.base,price='NaN')).status_code,422)
        self.assertEqual(self.client.post('/api/listings',json=dict(self.base,source='demo_a')).status_code,422)
    def test_verification_requires_real_date(self):
        self.assertEqual(self.client.post('/api/listings',json=dict(self.base,verification='user_checked')).status_code,422)
        a=self.add(verification='user_checked',last_checked=datetime.now(timezone.utc).isoformat())
        self.assertEqual(a['verification'],'user_checked')
    def test_favorite_notes_patch(self):
        a=self.add()
        r=self.client.patch(f"/api/listings/{a['id']}",json={'favorite':True,'notes':'Revisar ITV'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(len(self.client.get('/api/listings?favorite=true').json()),1)
    def test_insufficient_comparables_no_value(self):
        result=self.post('/api/valuations',{'vehicle':{'brand':'SEAT','model':'Ibiza','year':2020,'km':100000}})
        self.assertFalse(result['reliable'])
        self.assertEqual(result['message'],INSUFFICIENT)
        self.assertNotIn('maximum_purchase',result)
    def test_comparable_dedup_observation_and_mileage_evidence(self):
        for n,(km,price) in enumerate(((100000,12000),(150000,11000),(200000,10000),(250000,9000),(300000,8000))):
            self.post('/api/comparables',dict(self.base,external_id=str(n),url=f'https://example.org/evidence/{n}',km=km,price=price,
                      verified=True,observed_at=datetime.now(timezone.utc).isoformat(),condition='documentado',equipment='igual',version='1.0',generation='V',engine='1.0 MPI',fuel='gasoline',transmission='manual'))
        def value(km):
            return self.post('/api/valuations',{'vehicle':{'brand':'SEAT','model':'Ibiza','version':'1.0','generation':'V','engine':'1.0 MPI','fuel':'gasoline','transmission':'manual','year':2020,'km':km},'purchase':5000})
        low,high=value(100000),value(300000)
        self.assertTrue(low['reliable'])
        self.assertGreater(float(low['resale_central']),float(high['resale_central']))
        self.assertEqual(low['mileage_evidence']['pairs'],10)
        duplicate=dict(self.base,url='https://example.org/evidence/0',verified=True,observed_at=datetime.now(timezone.utc).isoformat())
        self.assertEqual(self.client.post('/api/comparables',json=duplicate).status_code,409)
        self.assertFalse(value(500000)['reliable'])
    def test_financial_example_cost_and_target_change(self):
        data={'purchase':10000,'resale':14000,'costs':[{'category':'otros','amount':1500}],'target_profit':2000}
        result=self.post('/api/calculator',data)
        self.assertEqual(float(result['total_cost']),11500)
        self.assertEqual(float(result['margin']),2500)
        self.assertEqual(float(result['maximum_purchase']),10500)
        second=self.post('/api/calculator',dict(data,target_profit=3000))
        self.assertEqual(float(second['maximum_purchase']),9500)
        third=self.post('/api/calculator',dict(data,costs=[{'category':'otros','amount':2000}]))
        self.assertEqual(float(third['margin']),2000)
    def test_tax_inverse_floor_and_no_incompatible_tax(self):
        result=self.post('/api/calculator',{'purchase':10000,'resale':15000,'tax_rate':.04,'tax_base_floor':12000,'target_profit':2000})
        self.assertEqual(float(result['tax']),480)
        max_buy=Decimal(str(result['maximum_purchase']))
        self.assertLessEqual(max_buy+max(max_buy,Decimal(12000))*Decimal('.04'),Decimal(13000))
        result=self.client.post('/api/calculator',json={'purchase':10000,'resale':15000,'tax_rate':.04,'transaction_type':'professional'})
        self.assertEqual(result.status_code,422)
        result=self.client.post('/api/calculator',json={'purchase':10000,'resale':15000,'tax_rate':.04,'manual_tax':400})
        self.assertEqual(result.status_code,422)
    def test_missing_cost_not_silently_zero(self):
        result=self.post('/api/calculator',{'purchase':10000,'resale':14000,'costs':[{'category':'reparación','amount':None}]})
        self.assertFalse(result['complete'])
        self.assertIsNone(result['maximum_purchase'])
        self.assertEqual(result['missing_costs'],['reparación'])
    def test_workshop_no_invented_quotes_critical(self):
        r=self.post('/api/workshop/analyze',{'description':'Puerta derecha dañada, aire acondicionado averiado, neumáticos desgastados y airbag activado'})
        self.assertGreaterEqual(len(r['damages']),4)
        self.assertTrue(all(d['cost'] is None for d in r['damages']))
        self.assertTrue(any(d['critical'] for d in r['damages']))
    def test_parts_compatibility_and_confirmed_costs(self):
        a=self.add()
        q={'listing_id':a['id'],'category':'parts','description':'Puerta derecha','amount':250,'confirmed':True,'observed_at':datetime.now(timezone.utc).isoformat()}
        self.assertEqual(self.client.post('/api/quotes',json=q).status_code,422)
        q['compatibility_verified']=True
        self.assertEqual(self.client.post('/api/quotes',json=q).status_code,422)
        q['compatibility']={k:'comprobado en presupuesto' for k in ('generation','engine','body','side','doors','oem','evidence')}
        self.post('/api/quotes',dict(q,shipping=20))
        self.post('/api/quotes',{'listing_id':a['id'],'category':'labor','description':'Pendiente'})
        costs=self.client.get(f"/api/quotes/costs/{a['id']}").json()['costs']
        self.assertEqual(len(costs),1)
        self.assertEqual(float(costs[0]['amount']),270)
    def test_operations_persist_only_sold_profit(self):
        a=self.add()
        op=self.post('/api/operations',{'listing_id':a['id'],'stage':'Comprado','purchase_price':10000,'purchase_date':'2026-01-01','actual_costs':[{'category':'todos gastos','amount':1500,'verified':True}],'expected_margin':5000})
        self.assertEqual(float(self.client.get('/api/statistics').json()['realized_profit']),0)
        r=self.client.patch(f"/api/operations/{op['id']}",json={'stage':'Vendido','sale_price':14000,'sale_date':'2026-01-21'})
        self.assertEqual(r.status_code,200,r.text)
        with TestClient(create_app(self.root/'data',self.root/'backups')) as c:
            stat=c.get('/api/statistics').json()
            self.assertEqual(float(stat['realized_profit']),2500)
            self.assertEqual(stat['average_days_to_sell'],20)
            self.assertEqual(len(c.get(f"/api/operations/{op['id']}/history").json()),2)
    def test_sale_requires_actual_purchase_and_date(self):
        a=self.add()
        r=self.client.post('/api/operations',json={'listing_id':a['id'],'stage':'Vendido','sale_price':14000})
        self.assertEqual(r.status_code,422)
    def test_backup_restore_real_database(self):
        self.add()
        backup=self.post('/api/backups',{})
        self.add(external_id='2',url='https://example.org/2')
        self.assertEqual(len(self.client.get('/api/listings').json()),2)
        result=self.post('/api/backups/restore',{'name':backup['name'],'confirm':True})
        self.assertIn('safety_backup',result)
        self.assertEqual(len(self.client.get('/api/listings').json()),1)
        self.assertEqual(self.client.post('/api/backups/restore',json={'name':'../radar.sqlite','confirm':True}).status_code,422)
    def test_export_csv_json_and_formula_injection(self):
        self.add(notes='=HYPERLINK("evil")')
        csv_result=self.client.get('/api/export?format=csv')
        self.assertIn("'=HYPERLINK",csv_result.text)
        rows=self.client.get('/api/export?format=json').json()
        self.assertEqual(rows[0]['source'],'wallapop')
        self.post('/api/import',{'format':'json','content':json.dumps(rows)})
        self.assertEqual(len(self.client.get('/api/listings').json()),1)
    def test_local_origin_host_content_and_size(self):
        self.assertEqual(self.client.get('/api/health',headers={'Host':'attacker.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/backups',json={},headers={'Origin':'https://attacker.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/listings',content='abc',headers={'Content-Type':'text/plain'}).status_code,415)
        self.assertEqual(self.client.post('/api/import',content='x'*(2*1024*1024+1),headers={'Content-Type':'application/json'}).status_code,413)
    def test_ai_paid_and_external_disabled(self):
        self.assertEqual(self.client.put('/api/ai',json={'provider':'openai','model':'any'}).status_code,422)
        self.assertEqual(self.client.post('/api/ai/analyze',json={'text':'test'}).status_code,422)
        self.assertEqual(self.client.get('/api/ai').json()['requests'],0)
    def test_ai_error_persists_data_no_fallback(self):
        self.add()
        self.assertEqual(self.client.put('/api/ai',json={'provider':'ollama','model':'local:small'}).status_code,200)
        import httpx
        with patch('backend.ai.AI._request',side_effect=httpx.ConnectError('offline')):
            self.assertEqual(self.client.post('/api/ai/analyze',json={'text':'Descripción'}).status_code,422)
        state=self.client.get('/api/ai').json()
        self.assertEqual(state['requests'],1)
        self.assertEqual(state['provider'],'ollama')
        self.assertEqual(len(self.client.get('/api/listings').json()),1)
    def test_catalog_dependency_and_manual_vehicle(self):
        self.post('/api/catalog',{'brand':'Marca no catalogada','model':'Modelo libre','generation':'I','version':'Manual','engine':'Motor'})
        r=self.client.get('/api/catalog?brand=Marca%20no%20catalogada').json()
        self.assertEqual(r['models'],['Modelo libre'])
    def test_assessment_snapshot_persists_and_ficha_exposes_pending_costs(self):
        a=self.add()
        request={'listing_id':a['id'],'valuation':{'vehicle':{'brand':'SEAT','model':'Ibiza','year':2020,'km':100000},'target_profit':1500}}
        self.post('/api/assessments',request)
        with TestClient(create_app(self.root/'data',self.root/'backups')) as c:
            detail=c.get(f"/api/listings/{a['id']}").json()
            self.assertEqual(float(detail['latest_assessment']['request']['target_profit']),1500)
            self.assertFalse(detail['latest_assessment']['result']['reliable'])
            self.assertIsNone(detail['analysis']['costs'][-1]['amount'])
            self.assertIn('valuation',detail['analysis'])
    def test_lab_never_real_radar(self):
        self.post('/api/lab/revision/0',{})
        self.assertEqual(self.client.get('/api/lab').json()['counts']['ads'],10)
        self.assertEqual(self.client.get('/api/listings').json(),[])
    def test_static_ui_assets_and_security_headers(self):
        for url in ('/','/static/styles.css','/static/app.js'):
            r=self.client.get(url)
            self.assertEqual(r.status_code,200,url)
            self.assertIn("frame-ancestors 'none'",r.headers['content-security-policy'])
        html=self.client.get('/').text
        self.assertIn('RadarCoches',html)
        js=self.client.get('/static/app.js').text
        self.assertNotIn('.innerHTML',js)
    def test_sql_injection_does_not_modify_data(self):
        self.add(brand="SEAT'; DROP TABLE listings;--")
        self.assertEqual(len(self.client.get('/api/listings').json()),1)

if __name__=='__main__': unittest.main()
