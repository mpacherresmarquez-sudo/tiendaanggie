import unittest, tempfile, os, sys
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import app
class BusinessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); app.DB=self.tmp.name+'/test.db'; app.init(); self.c=app.connect(); self.u={'id':1,'role':'admin'}
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
 def test_migration_is_repeatable(self):
  self.c.commit();app.init();app.init()
  self.assertIn('payment_method',[r['name'] for r in self.c.execute('PRAGMA table_info(services)')])
 def test_negative_money_rejected(self):
  with self.assertRaises(ValueError): app.money('-1')
 def test_password_hash(self):
  p=app.password('una-clave-segura');self.assertNotIn('una-clave-segura',p);self.assertEqual(p,app.password('una-clave-segura',p.split(':')[0]))
if __name__=='__main__':unittest.main()
