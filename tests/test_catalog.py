import unittest,tempfile,os,sys
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import app
class CatalogTests(unittest.TestCase):
 def test_catalog_prices_and_repeatability(self):
  with tempfile.TemporaryDirectory() as t:
   old=app.DB;app.DB=t+'/catalog.db'
   try:
    app.init()
    with app.connect() as c:
     self.assertEqual(c.execute('SELECT COUNT(*) FROM products').fetchone()[0],100)
     for name,presentation,price in [('Arroz','1 kg',400),('Azúcar','1 kg',450),('Huevo','Unidad',70),('Tallarín Lavaggi','Unidad',350),('Anís','Sobre individual',10)]:
      self.assertEqual(c.execute('SELECT price FROM products WHERE name=? AND presentation=?',(name,presentation)).fetchone()[0],price)
     self.assertEqual(c.execute('SELECT SUM(stock),SUM(cost) FROM products').fetchone()[0],0)
     c.execute("UPDATE products SET price=425,stock=3 WHERE name='Arroz'")
    app.init()
    with app.connect() as c:
     self.assertEqual(c.execute('SELECT COUNT(*) FROM products').fetchone()[0],100)
     self.assertEqual(tuple(c.execute("SELECT price,stock FROM products WHERE name='Arroz'").fetchone()),(425,3))
   finally:app.DB=old
 def test_old_catalog_preserves_history(self):
  from catalog import load_catalog
  with tempfile.TemporaryDirectory() as t:
   old=app.DB;app.DB=t+'/history.db'
   try:
    app.init()
    with app.connect() as c:
     c.execute('DELETE FROM catalog_migrations');c.execute('DELETE FROM products')
     c.execute("INSERT INTO products(id,name,price,cost) VALUES(500,'Producto anterior',100,50)")
     c.execute("INSERT INTO products(id,name,price,cost) VALUES(501,'Producto sin movimientos',100,50)")
     c.execute("INSERT INTO items(kind,document_id,product_id,quantity,price,cost) VALUES('sales',1,500,1,100,50)")
     load_catalog(c)
     self.assertEqual(c.execute('SELECT archived FROM products WHERE id=500').fetchone()[0],1)
     self.assertIsNone(c.execute("SELECT 1 FROM products WHERE name='Producto sin movimientos'").fetchone())
     self.assertEqual(c.execute('SELECT COUNT(*) FROM products WHERE archived=0').fetchone()[0],100)
     self.assertEqual(c.execute('SELECT product_id FROM items').fetchone()[0],500)
   finally:app.DB=old
