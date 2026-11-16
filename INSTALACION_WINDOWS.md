# Instalación y ejecución en Windows

## Equipo auditado

Python 3.12.10, Git 2.45.1, VS Code y cliente Docker instalados. Node no está en PATH y no es necesario. El motor Docker no responde; no bloquea RadarCoches. La descarga pip dentro del entorno de trabajo falla por permisos de socket (WinError 10013). Se ha podido instalar la aplicación desde wheels ya existentes en la caché del equipo.

## Abrir el proyecto

En VS Code: Archivo → Abrir carpeta → `C:\Users\ia\Desktop\INGESTA DATOS\RadarCoches`. Seleccionar intérprete `.venv\Scripts\python.exe`. La carpeta `.venv` está creada y lista en este equipo.

Arrancar mediante doble clic en `iniciar_radarcoches.bat`. Alternativa en terminal:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\iniciar_radarcoches.ps1
```

Abre navegador y servidor oculto en `http://127.0.0.1:8765`. Para arrancar sin abrir navegador añade `-SinNavegador`. La identidad de los procesos se guarda en `data/radar.pid.json`; el script de parada verifica PID, fecha de creación y ejecutable antes de detenerlos. No usa WMI ni privilegios elevados.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\detener_radarcoches.ps1
```

El script no termina otros servidores Python. Si arrancaste manualmente, detén con Ctrl+C en su terminal.

## Instalación reproducible nueva

Con Python 3.12 disponible, sin permisos de administrador:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/instalar.ps1
```

Solo modifica `.venv` dentro del proyecto. Si no hay acceso a Internet pero conservas la caché recuperada de esta instalación:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/instalar.ps1 -SinRed
```

La caché `data/wheelhouse` no forma parte del código versionable. `requirements-lock.txt` registra el entorno ejecutado; para recrearlo exactamente usa `python -m pip install -r requirements-lock.txt` dentro de `.venv`. Contiene las herramientas de pruebas auxiliares, no los módulos Big Data bloqueados.

Arranque manual para ver mensajes:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

No cambies el host a `0.0.0.0`: esta aplicación no tiene autenticación para exposición remota.

## Verificación

```powershell
.\probar_proyecto.ps1
.\.venv\Scripts\python.exe scripts/browser_test.py
```

La primera orden guarda las evidencias bajo `docs/evidencias`. Usa unittest y comprueba dependencias y compilación. pytest queda listo con `scripts/instalar.ps1 -Desarrollo` cuando haya red. El navegador automatizado requiere Edge instalado y websocket-client; usa una base temporal y puertos de prueba 8876/9223. Esos puertos solo se abren durante el test y se cierran al finalizar.

## Laboratorio

```powershell
.\demo_ingesta.ps1
.\demo_ingesta.ps1 -Volumen
.\iniciar_ingesta.ps1 -Modo apis
```

Los dos primeros comandos ejecutan el modo local explícito. El último abre las APIs DEMO HTTP en 127.0.0.1:8771 y :8772, Ctrl+C termina ambas. Las revisiones también están en la pantalla Laboratorio; son independientes del Radar.

Para completar la integración distribuida, abre Docker Desktop de forma normal y, en una terminal con red permitida:

```powershell
.\scripts\instalar.ps1 -BigData
.\iniciar_ingesta.ps1 -Modo kafka
.\iniciar_ingesta.ps1 -Modo distributed
```

Estos pasos distribuidos no están superados en la sesión actual. `run_distributed.py` inicia ambas APIs en un espacio nuevo y ejecuta dlt/publicación/consumo/exportación para las revisiones; debe revisarse su resultado con DuckDB y Parquet reales. Para el volumen y las pruebas de fallo distribuidas, seguir [CONTINUAR_CODEX.md](CONTINUAR_CODEX.md).

## Diagnóstico

- Servidor no arranca: abrir `data/servidor-error.log`; comprobar puerto 8765 y dependencias con `.venv\Scripts\python.exe -m pip check`.
- Socket denegado en pip: restricción del entorno; no desactivar seguridad de Windows. Ejecutar el comando local autorizado desde una terminal con acceso normal o usar ruedas descargadas de procedencia legítima.
- Docker no responde: Radar funciona; la integración Kafka queda pendiente hasta que el motor esté disponible.
- Ollama no responde: dejar IA desactivada o instalar/configurar un modelo por cuenta propia. El proyecto no instala ni descarga modelos automáticamente.
- Copias/restauración: pantalla Configuración. Antes de restaurar se genera una copia de la base actual.
