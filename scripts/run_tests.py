"""Run all local tests and save an honest machine-readable report."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
def main():
    os.chdir(ROOT)
    output=ROOT/'docs'/'evidencias'/f'pruebas-locales-{uuid4().hex}'
    output.mkdir(parents=True)
    checks=[('aplicacion_pipeline',[sys.executable,'-m','unittest','discover','-s','tests','-v']),
            ('prototipo_recuperado',[sys.executable,'-m','unittest','discover','-s','actividad_ingesta','-p','test_ingesta.py','-v']),
            ('dependencias',[sys.executable,'-m','pip','check']),
            ('compilacion',[sys.executable,'-m','compileall','-q','backend','actividad_ingesta','scripts','tests'])]
    results=[]
    with TemporaryDirectory(prefix='radar-tests-') as temp:
        env=dict(os.environ,PYTHONIOENCODING='utf-8',RADAR_DATA_DIR=str(Path(temp)/'data'),
                 PYTHONPYCACHEPREFIX=str(Path(temp)/'pycache'))
        for name,cmd in checks:
            run=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env)
            (output/(name+'.txt')).write_text(run.stdout,encoding='utf-8')
            print(f'{name}: salida {run.returncode}')
            print(run.stdout[-2000:])
            results.append(dict(name=name,exit_code=run.returncode,command=cmd))
    report=dict(at=datetime.now(timezone.utc).isoformat(),checks=results,
                excluded=['Integración distribuida real: se ejecuta por separado con scripts/run_distributed.py; consultar docs/evidencias/distribuido/','Ollama real: modelo/servidor no verificado','Este ejecutor utiliza unittest; no invoca pytest'],
                passed=all(r['exit_code']==0 for r in results))
    (output/'resultado_tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Evidencia: {output}')
    return 0 if report['passed'] else 1
if __name__=='__main__': sys.exit(main())
