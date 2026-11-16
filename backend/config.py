"""Local-only configuration. No credentials are persisted by the application."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
DATA = Path(os.environ.get('RADAR_DATA_DIR', ROOT / 'data')).resolve()
BACKUPS = ROOT / 'backups'
FRONTEND = ROOT / 'frontend'
MAX_BODY = 2 * 1024 * 1024

