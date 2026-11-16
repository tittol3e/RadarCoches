"""Two separate localhost processes with a shared synthetic source store."""
import os
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    os.chdir(ROOT)
    children=[]
    try:
        for app,port in [('source_a',8771),('source_b',8772)]:
            children.append(subprocess.Popen([sys.executable,'-m','uvicorn',f'actividad_ingesta.pipeline.apis:{app}','--factory','--host','127.0.0.1','--port',str(port)]))
        for child in children:
            if child.wait(): return 1
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None: child.terminate()
        for child in children: child.wait()
    return 0
if __name__=='__main__': sys.exit(main())
