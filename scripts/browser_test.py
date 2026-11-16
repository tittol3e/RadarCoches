"""Real headless Edge checks. Uses a temporary database, never the user's Radar data."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

import websocket

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8876'
DEBUG = 'http://127.0.0.1:9223'
EDGE = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
EVIDENCE = ROOT / 'docs' / 'evidencias'


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=20, origin=DEBUG)
        self.counter = 0
        self.errors = []

    def call(self, method, params=None):
        self.counter += 1
        ident = self.counter
        self.ws.send(json.dumps(dict(id=ident, method=method, params=params or {})))
        while True:
            message = json.loads(self.ws.recv())
            if message.get('method') == 'Runtime.exceptionThrown':
                self.errors.append(message['params'])
            if message.get('method') == 'Log.entryAdded' and message['params']['entry']['level'] == 'error':
                entry = message['params']['entry']
                # The browser probes favicon.ico; this is unrelated to JS execution.
                if 'favicon.ico' not in entry.get('url', ''):
                    self.errors.append(entry)
            if message.get('id') == ident:
                if 'error' in message:
                    raise RuntimeError(message['error'])
                return message.get('result', {})

    def evaluate(self, expression):
        result = self.call('Runtime.evaluate', dict(expression=expression, returnByValue=True, awaitPromise=True))
        if 'exceptionDetails' in result:
            raise RuntimeError(result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def wait(self, expression, timeout=20):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.evaluate(expression):
                return
            time.sleep(.1)
        raise AssertionError('Browser condition timed out: ' + expression)

    def route(self, page, title):
        self.evaluate('location.hash=' + json.dumps(page))
        self.wait('document.querySelector("main h1")?.textContent === ' + json.dumps(title))

    def submit(self, text, values):
        self.evaluate('''(() => {
            const f=[...document.querySelectorAll('main form')].find(f=>f.querySelector('button[type=submit]')?.textContent===%s);
            if(!f) throw Error('Form not found');
            for(const [name,value] of Object.entries(%s)){
                const e=f.querySelector('[name="'+name+'"]');
                if(!e) throw Error('Field not found: '+name);
                if(e.type==='checkbox') e.checked=value; else e.value=value;
            }
            if(!f.checkValidity()) throw Error('Invalid form: '+[...f.elements].filter(e=>!e.checkValidity()).map(e=>e.name));
            f.requestSubmit(); return true;
        })()''' % (json.dumps(text), json.dumps(values)))

    def screenshot(self, name):
        self.evaluate('document.querySelector("#toast").hidden=true;scrollTo(0,0)')
        value = self.call('Page.captureScreenshot', dict(format='png', captureBeyondViewport=False))
        (EVIDENCE / name).write_bytes(base64.b64decode(value['data']))


def get_json(url):
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.load(response)


def wait_http(url, process, timeout=25):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if process.poll() is not None:
            raise RuntimeError('Background process stopped with code ' + str(process.returncode))
        try:
            return get_json(url)
        except OSError:
            time.sleep(.2)
    raise TimeoutError(url)


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    checks = []
    browser = server = cdp = None
    result = {'database': 'temporary_only', 'browser': str(EDGE), 'checks': checks}
    try:
        temporary = tempfile.TemporaryDirectory(prefix='radar-browser-', ignore_cleanup_errors=True)
        with temporary as temp:
            temp = Path(temp)
            env = dict(os.environ, RADAR_DATA_DIR=str(temp / 'data'))
            with (EVIDENCE / 'navegador-procesos.log').open('w', encoding='utf-8') as log:
                server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8876'], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
                wait_http(BASE + '/api/health', server)
                browser = subprocess.Popen([str(EDGE), '--headless=new', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--disable-background-networking', '--remote-debugging-port=9223', '--remote-allow-origins=' + DEBUG, '--user-data-dir=' + str(temp / 'profile'), 'about:blank'], stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
                tabs = wait_http(DEBUG + '/json', browser)
                target = next(x for x in tabs if x['type'] == 'page')
                cdp = CDP(target['webSocketDebuggerUrl'])
                cdp.call('Page.enable'); cdp.call('Runtime.enable'); cdp.call('Log.enable')
                cdp.call('Emulation.setDeviceMetricsOverride', dict(width=1440, height=1000, deviceScaleFactor=1, mobile=False))
                cdp.call('Page.navigate', dict(url=BASE))
                cdp.wait('document.querySelector("main h1")?.textContent === "Tu radar, con los pies en el suelo"')
                assert get_json(BASE + '/api/listings') == []
                checks.append('Startup with empty temporary database and disabled AI')
                cdp.screenshot('navegador-dashboard.png')
                for page, title in [('radar', 'Radar de anuncios'), ('tasador', 'Tasador de vehículos'), ('taller', 'Taller y piezas'), ('calculadora', 'Calculadora de rentabilidad'), ('operaciones', 'Mis operaciones'), ('laboratorio', 'Laboratorio de datos'), ('configuracion', 'Configuración')]:
                    cdp.route(page, title)
                    checks.append('Navigation ' + page)
                cdp.route('radar', 'Radar de anuncios')
                cdp.submit('Guardar anuncio', dict(source='manual', external_id='UI-TEMPORAL', brand='Vehículo de prueba temporal', model='Prueba navegador', year=2022, km=80000, price=12000, description='<img src=x onerror="window.xssExecuted=true">', notes='Prueba aislada; no es un anuncio real'))
                cdp.wait('document.querySelector("main table")?.textContent.includes("Vehículo de prueba temporal")')
                assert len(get_json(BASE + '/api/listings')) == 1
                assert not cdp.evaluate('window.xssExecuted === true')
                checks.append('Manual listing form saves and renders without XSS')
                cdp.evaluate('[...document.querySelectorAll("main button")].find(b=>b.textContent==="Ver ficha").click()')
                cdp.wait('document.querySelector("dialog").open')
                cdp.evaluate('document.querySelector("dialog input[name=price]").value=11500; document.querySelector("dialog form").requestSubmit()')
                cdp.wait('!document.querySelector("dialog").open')
                assert get_json(BASE + '/api/listings/1')['price'] == '11500'
                assert len(get_json(BASE + '/api/listings/1')['history']) == 2
                checks.append('Listing dialog saves price update with history')
                cdp.screenshot('navegador-radar.png')
                cdp.route('calculadora', 'Calculadora de rentabilidad')
                cdp.evaluate('[...document.querySelectorAll("main button")].find(b=>b.textContent.includes("Añadir gasto")).click(); const row=document.querySelector(".cost-row"); row.querySelectorAll("input")[0].value="Gastos adicionales de prueba";row.querySelectorAll("input")[1].value=1500;')
                cdp.submit('Calcular rentabilidad', dict(purchase=10000, resale=14000, target_profit=1000, tax_rate=0))
                cdp.wait('document.querySelector(".result")?.textContent.includes("2500,00")')
                checks.append('Calculator form computes 2500 EUR margin from 10000/14000/1500')
                cdp.route('taller', 'Taller y piezas')
                cdp.submit('Identificar daños declarados', dict(description='Puerta derecha dañada, aire acondicionado averiado y neumáticos desgastados'))
                cdp.wait('document.querySelector(".result")?.textContent.includes("Climatización")')
                checks.append('Workshop damage description form works without inventing costs')
                observed_local = cdp.evaluate('new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16)')
                cdp.submit('Guardar presupuesto', dict(listing_id='1', category='labor', description='Diagnosis de prueba temporal', amount=80, observed_at=observed_local, confirmed=True))
                cdp.wait('document.querySelector(".quote-card")?.textContent.includes("Diagnosis de prueba temporal")')
                assert get_json(BASE + '/api/quotes')[0]['confirmed'] is True
                checks.append('Workshop quote form saves confirmed dated labor estimate')
                cdp.evaluate('[...document.querySelectorAll("main button")].find(b=>b.textContent==="Editar presupuesto").click()')
                cdp.wait('document.querySelector("dialog").open')
                cdp.evaluate('document.querySelector("dialog input[name=amount]").value=95;document.querySelector("dialog form").requestSubmit()')
                cdp.wait('!document.querySelector("dialog").open')
                assert get_json(BASE + '/api/quotes')[0]['amount'] == '95'
                checks.append('Workshop quote editing dialog persists amount')

                cdp.route('operaciones', 'Mis operaciones')
                cdp.submit('Registrar operación', dict(listing_id='1', stage='Detectado', notes='Seguimiento de prueba temporal'))
                cdp.wait('document.querySelector(".operation-card")?.textContent.includes("Seguimiento de prueba temporal")')
                assert len(get_json(BASE + '/api/operations')) == 1
                checks.append('Operation form persists vehicle tracking')
                cdp.route('tasador', 'Tasador de vehículos')
                cdp.submit('Calcular con los comparables seleccionados', dict(brand='Vehículo de prueba temporal', model='Prueba navegador', year=2022, km=80000))
                cdp.wait('document.querySelector(".result")?.textContent.includes("No existe una tasación fiable")')
                checks.append('Valuation form refuses invented values without comparables')
                for index in range(3):
                    cdp.submit('Guardar comparable', dict(source='manual', url='https://example.org/prueba-temporal/'+str(index), brand='Veh\u00edculo de prueba temporal', model='Prueba navegador', year=2022, km=80000+index*1000, price=12000+index*500, observed_at=observed_local, verified=True))
                    cdp.wait('document.querySelectorAll("input[name=comparable_id]").length === ' + str(index+1))
                checks.append('Comparable form saves three sourced dated records')
                cdp.submit('Calcular con los comparables seleccionados', dict(brand='Veh\u00edculo de prueba temporal', model='Prueba navegador', year=2022, km=81000, purchase=10000, target_profit=1000))
                cdp.wait('document.querySelector(".result")?.textContent.includes("Precio m\u00e1ximo de compra")')
                assert get_json(BASE+'/api/comparables').__len__() == 3
                checks.append('Valuation form calculates using three verified comparable records')
                cdp.route('radar', 'Radar de anuncios')
                cdp.evaluate('[...document.querySelectorAll("main button")].find(b=>b.textContent==="Ver ficha").click()')
                cdp.wait('document.querySelector("dialog").open')
                assert cdp.evaluate('document.querySelector("dialog").textContent.includes("Confianza")')
                assert cdp.evaluate('document.querySelector("dialog").textContent.includes("Margen central estimado")')
                cdp.evaluate('[...document.querySelectorAll("dialog button")].find(b=>b.textContent==="Tasar este veh\u00edculo").click()')
                cdp.wait('document.querySelector("main h1")?.textContent === "Tasador de veh\u00edculos"')
                assert cdp.evaluate('document.querySelector("[name=selected_listing]").value === "1"')
                assert cdp.evaluate('document.querySelector("main input[name=brand]").value === "Veh\u00edculo de prueba temporal"')
                checks.append('Vehicle detail shows complete assessment and opens prefilled valuer')
                cdp.evaluate('const rows=document.querySelectorAll("main form .cost-row");for(const row of rows){if(row.querySelectorAll("input")[1].value==="")row.querySelectorAll("input")[1].value=1500;}')
                cdp.submit('Calcular con los comparables seleccionados', dict(purchase=10000, target_profit=1000))
                cdp.wait('document.querySelector(".result")?.textContent.includes("TASACI\u00d3N GUARDADA EN LA FICHA")')
                snapshot = get_json(BASE+'/api/listings/1')['latest_assessment']
                assert snapshot and snapshot['request']['target_profit'] == '1000'
                saved_maximum = float(snapshot['result']['maximum_purchase'])
                checks.append('Valuation associated with listing persists input and result snapshot')
                cdp.evaluate('const target=document.querySelector("main input[name=target_profit]");target.value=2000;target.dispatchEvent(new Event("input",{bubbles:true}));')
                cdp.wait('document.querySelector(".result")?.textContent.includes("PREVISUALIZACI\u00d3N")')
                assert get_json(BASE+'/api/listings/1')['latest_assessment']['request']['target_profit'] == '1000'
                cdp.submit('Calcular con los comparables seleccionados', dict(target_profit=2000))
                cdp.wait('document.querySelector(".result")?.textContent.includes("TASACI\u00d3N GUARDADA EN LA FICHA")')
                snapshot = get_json(BASE+'/api/listings/1')['latest_assessment']
                assert float(snapshot['result']['maximum_purchase']) < saved_maximum
                checks.append('Target-profit change previews without saving and reduces maximum purchase on submit')


                cdp.route('laboratorio', 'Laboratorio de datos')
                assert cdp.evaluate('document.querySelector("main").textContent.includes("Para qué sirve la ingesta")')
                assert cdp.evaluate('[...document.querySelectorAll("main button")].filter(b=>b.textContent==="Ejecutar paso" && !b.disabled).length === 1')
                for revision, total in enumerate((10, 12, 12, 12)):
                    cdp.evaluate('[...document.querySelectorAll("main button")].find(b=>b.textContent==="Ejecutar paso" && !b.disabled).click()')
                    cdp.wait('document.querySelector("main").textContent.includes("Paso terminado: '+str(total)+' anuncios guardados") && ![...document.querySelectorAll("main button")].some(b=>b.textContent==="Repetir paso" && b.disabled)')
                    assert get_json(BASE+'/api/lab')['revision'] == revision
                cdp.evaluate('[...document.querySelectorAll("main button")].find(b=>b.textContent==="Repetir paso").click()')
                cdp.wait('document.querySelector("main").textContent.includes("La lectura no ha añadido duplicados")')
                assert get_json(BASE+'/api/lab')['counts']['ads'] == 12
                assert get_json(BASE+'/api/lab')['counts']['price_updates'] == 2
                cdp.screenshot('navegador-laboratorio-guiado.png')
                checks.append('Guided ingestion: ordered steps, 10/12/12/12, two prices and repeat without duplicates')
                cdp.evaluate('[...document.querySelectorAll("main button")].find(b=>b.textContent==="Comprobar con 1.000 anuncios").click()')
                cdp.wait('document.querySelector("main").textContent.includes("Prueba de volumen superada")', timeout=60)
                assert get_json(BASE+'/api/lab')['counts']['ads'] == 12
                checks.append('Guided volume test passes and preserves the four-step exercise')

                cdp.call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=1, mobile=True))
                cdp.route('dashboard', 'Tu radar, con los pies en el suelo')
                assert cdp.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                cdp.screenshot('navegador-movil.png')
                checks.append('Mobile dashboard has no horizontal overflow at 390px')
                for page, title in [('radar', 'Radar de anuncios'), ('tasador', 'Tasador de veh\u00edculos'), ('taller', 'Taller y piezas'), ('calculadora', 'Calculadora de rentabilidad'), ('operaciones', 'Mis operaciones'), ('laboratorio', 'Laboratorio de datos'), ('configuracion', 'Configuraci\u00f3n')]:
                    cdp.route(page, title)
                    assert cdp.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Mobile horizontal overflow: ' + page
                    checks.append('Mobile layout ' + page)
                cdp.screenshot('navegador-movil-configuracion.png')
                result.update(passed=True, javascript_errors=cdp.errors)
                if cdp.errors:
                    result['passed'] = False
                    raise AssertionError('Browser errors: ' + json.dumps(cdp.errors))
    except Exception as exc:
        result.update(passed=False, error=str(exc))
        if cdp:
            result['javascript_errors'] = cdp.errors
            try:
                cdp.screenshot('navegador-fallo.png')
            except Exception:
                pass
        raise
    finally:
        if cdp:
            try:
                cdp.call('Browser.close')
            except Exception:
                pass
            cdp.ws.close()
        for process in (browser, server):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        if 'temporary' in locals():
            temporary.cleanup()
        (EVIDENCE / 'pruebas_navegador.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
