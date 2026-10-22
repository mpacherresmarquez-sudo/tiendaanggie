"""Respaldo consistente de SQLite. Ejecutar periódicamente fuera del proceso web."""
import sqlite3, datetime, os
from pathlib import Path
from app import DB
folder=Path(os.environ.get('ANGGIE_BACKUPS',str(Path(DB).parent/'backups')))
folder.mkdir(parents=True,exist_ok=True)
if not Path(DB).exists(): raise SystemExit('La base de datos todavía no existe.')
target=folder/('anggie-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.db')
with sqlite3.connect(DB) as source, sqlite3.connect(target) as dest: source.backup(dest)
os.chmod(target,0o600)
print('Respaldo creado:',target)
