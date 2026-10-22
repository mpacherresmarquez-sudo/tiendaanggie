"""Carga única del catálogo indicado por el dueño; no sobreescribe cambios posteriores."""
import csv
from decimal import Decimal
from pathlib import Path
VERSION='catalogo-cliente-2026-10-22'
def load_catalog(c):
 c.execute('CREATE TABLE IF NOT EXISTS catalog_migrations(version TEXT PRIMARY KEY)')
 if c.execute('SELECT 1 FROM catalog_migrations WHERE version=?',(VERSION,)).fetchone(): return
 columns={r['name'] for r in c.execute('PRAGMA table_info(products)')}
 if 'archived' not in columns: c.execute('ALTER TABLE products ADD COLUMN archived INTEGER NOT NULL DEFAULT 0')
 # Conservar solo los productos anteriores necesarios para documentos históricos.
 c.execute('UPDATE products SET archived=1')
 c.execute('DELETE FROM products WHERE id NOT IN (SELECT product_id FROM items UNION SELECT product_id FROM movements)')
 with (Path(__file__).parent/'catalog/productos.csv').open(encoding='utf-8',newline='') as f:
  rows=list(csv.DictReader(f))
 for r in rows:
  c.execute('INSERT INTO products(name,presentation,price,category,cost,stock,minimum) VALUES(?,?,?,?,0,0,0)',(r['nombre'],r['presentacion'],int(Decimal(r['precio'])*100),r['categoria']))
 c.execute('INSERT INTO catalog_migrations(version) VALUES(?)',(VERSION,))
