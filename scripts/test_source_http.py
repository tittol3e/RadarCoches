"""Exercise both synthetic APIs over real localhost HTTP in an isolated directory."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def main():
    from actividad_ingesta.pipeline.lab import Lab
    from actividad_ingesta.pipeline.models import Change, SyntheticAd
    evidence=ROOT/'docs'/'evidencias'
    evidence.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='radar_http_') as tmp:
        lab = Lab(tmp)
        lab.prepare_revision(0)
        env=dict(os.environ,RADAR_LAB_DIR=tmp)
        children=[]
        checks=[]
        try:
            for name,port in [('source_a',8771),('source_b',8772)]:
                children.append(subprocess.Popen([sys.executable,'-m','uvicorn',f'actividad_ingesta.pipeline.apis:{name}','--factory','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
            with httpx.Client(timeout=3,trust_env=False) as client:
                for source, port in (('demo_a', 8771), ('demo_b', 8772)):
                    base=f'http://127.0.0.1:{port}'
                    for attempt in range(40):
                        try:
                            health=client.get(base+'/health');health.raise_for_status();break
                        except httpx.HTTPError:
                            if any(c.poll() is not None for c in children): raise RuntimeError('API subprocess failed')
                            time.sleep(.1)
                    else: raise AssertionError('API timeout')
                    assert health.json() == dict(status='ok', source=source, synthetic=True)
                    ads=client.get(base+'/ads',params={'page':1,'page_size':2}).json()
                    assert ads.get('synthetic') is True and ads['source'] == source, ads
                    assert len(ads['items']) == 2 and ads['total'] == 5, ads
                    snapshot = None
                    events = []
                    for page in (1, 2, 3):
                        params = dict(since=0, page=page, page_size=2)
                        if snapshot is not None:
                            params['until'] = snapshot
                        response = client.get(base+'/changes', params=params)
                        response.raise_for_status()
                        changes = response.json()
                        snapshot = changes['highwater']
                        events.extend(Change.model_validate(event).validated() for event in changes['items'])
                    assert len({e.ad.id for e in events}) == 5 and all(e.source == source for e in events)
                    assert [e.ad for e in events[:2]] == [SyntheticAd.model_validate(row) for row in ads['items']]
                    assert changes['next_page'] is None
                    assert not client.get(base+'/changes', params={'since': snapshot}).json()['items']
                    assert client.get(base+'/ads',params={'page_size':501}).status_code==422
                    checks.append({'port':port,'source':source,'changes':len(events),'highwater':snapshot,'http':True,'passed':True})
                for revision, expected_kind in ((1, 'created'), (2, 'updated')):
                    lab.prepare_revision(revision)
                    for check in checks:
                        response = client.get(f"http://127.0.0.1:{check['port']}/changes", params={'since': check['highwater']})
                        response.raise_for_status()
                        increment = response.json()
                        event, = [Change.model_validate(event).validated() for event in increment['items']]
                        assert event.kind == expected_kind and event.source == check['source']
                        check['highwater'] = increment['highwater']
                        check.setdefault('increments', []).append(dict(revision=revision, id=event.ad.id, kind=event.kind))
            report={'passed':True,'checks':checks,'isolated':True,'dlt_executed':False,'kafka_executed':False}
            path = evidence / f'apis_http-{uuid4().hex}.json'
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'Evidencia: {path}')
            print(json.dumps(report,ensure_ascii=False,indent=2))
        finally:
            for child in children:
                if child.poll() is None: child.terminate()
            for child in children: child.wait()
    return 0
if __name__=='__main__':sys.exit(main())
