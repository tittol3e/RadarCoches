"""Exercise both synthetic APIs over real localhost HTTP in an isolated directory."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def main():
    from actividad_ingesta.pipeline.lab import Lab
    evidence=ROOT/'docs'/'evidencias'
    evidence.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='radar_http_') as tmp:
        Lab(tmp).prepare_revision(0)
        env=dict(os.environ,RADAR_LAB_DIR=tmp)
        children=[]
        checks=[]
        try:
            for name,port in [('source_a',8771),('source_b',8772)]:
                children.append(subprocess.Popen([sys.executable,'-m','uvicorn',f'actividad_ingesta.pipeline.apis:{name}','--factory','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
            with httpx.Client(timeout=3,trust_env=False) as client:
                for port in (8771,8772):
                    base=f'http://127.0.0.1:{port}'
                    for attempt in range(40):
                        try:
                            health=client.get(base+'/health');health.raise_for_status();break
                        except httpx.HTTPError:
                            if any(c.poll() is not None for c in children): raise RuntimeError('API subprocess failed')
                            time.sleep(.1)
                    else: raise AssertionError('API timeout')
                    ads=client.get(base+'/ads',params={'page':1,'page_size':2}).json()
                    assert ads.get('synthetic') is True,ads
                    assert len(ads['items'])==2,ads
                    changes=client.get(base+'/changes',params={'since':0,'page_size':100}).json()
                    assert len(changes['items'])==5,changes
                    assert client.get(base+'/ads',params={'page_size':501}).status_code==422
                    checks.append({'port':port,'source':changes['source'],'changes':len(changes['items']),'http':True,'passed':True})
            report={'passed':True,'checks':checks,'isolated':True,'dlt_executed':False,'kafka_executed':False}
            (evidence/'apis_http.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False,indent=2))
        finally:
            for child in children:
                if child.poll() is None: child.terminate()
            for child in children: child.wait()
    return 0
if __name__=='__main__':sys.exit(main())
