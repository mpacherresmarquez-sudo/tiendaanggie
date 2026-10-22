import unittest, tempfile, os, sys
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import app
class BusinessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); app.DB=self.tmp.name+'/test.db'; app.init(); self.c=app.connect(); self.u={'id':1,'role':'admin'}
  self.c.execute('DELETE FROM products')
  self.c.execute("INSERT INTO products(id,name,price,cost,stock,minimum) VALUES(1,'Producto de prueba',18500,16200,18,5)")
  self.c.execute("INSERT INTO customers(name) VALUES('Ana')")
  self.c.execute("INSERT INTO suppliers(name) VALUES('Mayorista')");self.c.commit()
 def tearDown(self):self.c.close();self.tmp.cleanup()
 def save(self,k,d,u=None):
  with self.c: app.write(self.c,k,d,u or self.u)
 def test_sale_debt_payment_and_inventory(self):
  self.save('sales',{'mode':'Fiado','customer_id':1,'items':[{'product_id':1,'quantity':2}]})
  self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],16)
  total=self.c.execute('SELECT total FROM sales').fetchone()[0];self.assertEqual(total,37000)
  self.save('payments',{'sale_id':1,'amount':'100.00'})
  with self.assertRaises(ValueError):self.save('payments',{'sale_id':1,'amount':'300.00'})
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM payments').fetchone()[0],1)
 def test_duplicate_lines_cannot_oversell(self):
  with self.assertRaises(ValueError):self.save('sales',{'mode':'Contado','items':[{'product_id':1,'quantity':10},{'product_id':1,'quantity':10}]})
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM sales').fetchone()[0],0)
 def test_purchase_updates_stock(self):
  self.save('purchases',{'supplier_id':1,'items':[{'product_id':1,'quantity':2,'price':'160.00'}]})
  self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],20)
 def test_buy_sacks_sell_kilos(self):
  self.c.execute('UPDATE products SET stock=0,cost=0,price=400 WHERE id=1');self.c.commit()
  self.save('purchases',{'supplier_id':1,'items':[{'product_id':1,'quantity':2,'price':'150','purchase_unit':'Saco','conversion_factor':50}]})
  p=self.c.execute('SELECT * FROM products WHERE id=1').fetchone()
  self.assertEqual(p['stock'],100);self.assertEqual(p['cost'],300)
  self.assertEqual(self.c.execute('SELECT total FROM purchases').fetchone()[0],30000)
  line=self.c.execute('SELECT * FROM items').fetchone()
  self.assertEqual(line['purchase_quantity'],2);self.assertEqual(line['conversion_factor'],50)
  self.assertEqual(line['purchase_price'],15000);self.assertEqual(line['purchase_unit'],'Saco')
  self.save('sales',{'mode':'Contado','items':[{'product_id':1,'quantity':2.5}]})
  self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],97.5)
  sale=self.c.execute('SELECT * FROM sales').fetchone()
  self.assertEqual(sale['total'],1000);self.assertEqual(sale['cost'],750)
 def test_bulk_weighted_cost_and_invalid_factor(self):
  self.c.execute('UPDATE products SET stock=10,cost=200 WHERE id=1');self.c.commit()
  self.save('purchases',{'supplier_id':1,'items':[{'product_id':1,'quantity':1,'price':'40','purchase_unit':'Saco','conversion_factor':10},{'product_id':1,'quantity':1,'price':'60','purchase_unit':'Saco','conversion_factor':10}]})
  p=self.c.execute('SELECT * FROM products WHERE id=1').fetchone()
  self.assertEqual(p['stock'],30);self.assertEqual(p['cost'],400)
  for factor in (0,-5,'nan','inf'):
   with self.assertRaises(ValueError):self.save('purchases',{'supplier_id':1,'items':[{'product_id':1,'quantity':1,'price':'100','conversion_factor':factor}]})
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM purchases').fetchone()[0],1)
 def test_permissions(self):
  with self.assertRaises(PermissionError):self.save('users',{}, {'id':2,'role':'ventas'})
 def test_service_confirmation_and_cancellation_retains_consumption(self):
  self.save('funds',{'amount':'100','reference':'DEP01'})
  self.save('services',{'company_id':1,'destination':'999888777','confirmation':'999888777','payment_method':'Yape','payment_reference':'YAPE123','amount':'20','charge':'1','commission':'0.5'})
  with self.assertRaises(ValueError):self.save('services',{'id':1,'state':'CONFIRMADO','code':'ABC'})
  self.save('services',{'id':1,'state':'CONFIRMADO','code':'ABC','external_confirmation':True})
  self.save('services',{'id':1,'state':'ANULADO','reason':'Reclamo pendiente de reversión'})
  self.assertEqual(self.c.execute('SELECT SUM(amount) FROM funds').fetchone()[0],10000)
 def test_service_payment_validation(self):
  base={'company_id':1,'destination':'999888777','confirmation':'999888777','amount':'20','payment_reference':'REF123'}
  for method in ('Efectivo',None):
   with self.assertRaises(ValueError): self.save('services',dict(base,payment_method=method))
  with self.assertRaises(ValueError): self.save('services',dict(base,payment_method='Transferencia bancaria'))
  self.save('services',dict(base,payment_method='Transferencia bancaria',bank='BCP'))
  self.save('services',{'id':1,'state':'CONFIRMADO','code':'BANK123','external_confirmation':True})
  saved=self.c.execute('SELECT * FROM services').fetchone()
  self.assertEqual(saved['bank'],'BCP');self.assertEqual(saved['payment_method'],'Transferencia bancaria')
  self.assertEqual(saved['state'],'CONFIRMADO')
 def test_recharge_optional_reference_no_period_single_commission(self):
  self.save('services',{'company_id':1,'destination':'987654321','confirmation':'987654321','amount':'10','charge':'2','commission':'99','period':'2026-10','payment_method':'Yape'})
  row=self.c.execute('SELECT * FROM services').fetchone()
  self.assertEqual(row['payment_reference'],'');self.assertEqual(row['period'],'')
  self.assertEqual(row['charge'],200);self.assertEqual(row['commission'],0)
  self.assertEqual(row['amount']+row['charge'],1200)
 def test_electricity_period_and_supply(self):
  self.save('services',{'company_id':5,'destination':'SUM-001','confirmation':'SUM-001','amount':'65','charge':'3','period':'2026-10','payment_method':'Transferencia bancaria','bank':'BCP'})
  row=self.c.execute('SELECT * FROM services').fetchone()
  self.assertEqual(row['period'],'2026-10');self.assertEqual(row['destination'],'SUM-001')
 def test_migration_is_repeatable(self):
  self.c.commit();app.init();app.init()
  self.assertIn('payment_method',[r['name'] for r in self.c.execute('PRAGMA table_info(services)')])
 def test_negative_money_rejected(self):
  with self.assertRaises(ValueError): app.money('-1')
 def test_password_hash(self):
  p=app.password('una-clave-segura');self.assertNotIn('una-clave-segura',p);self.assertEqual(p,app.password('una-clave-segura',p.split(':')[0]))
if __name__=='__main__':unittest.main()
