import unittest,tempfile,threading,urllib.request,urllib.error,http.cookiejar,json,sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import app
class HttpTests(unittest.TestCase):
 def test_login_permissions_and_sale(self):
  with tempfile.TemporaryDirectory() as t:
   old=app.DB;app.DB=t+'/http.db';app.init()
   with app.connect() as c: c.execute('UPDATE products SET stock=18 WHERE id=1')
   server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
   def req(path,data=None):
    body=json.dumps(data).encode() if data is not None else None
    r=client.open(urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+path,data=body,headers={'X-Anggie':'1','Content-Type':'application/json'}));return json.load(r)
   try:
    self.assertTrue(req('/api/session')['setup'])
    req('/api/setup',{'name':'Administradora','username':'admin','password':'prueba-temporal-123'})
    req('/api/login',{'username':'admin','password':'prueba-temporal-123'})
    req('/api/sales',{'mode':'Contado','items':[{'product_id':1,'quantity':1}]})
    d=req('/api/data');self.assertEqual(d['products'][0]['stock'],17);self.assertEqual(len(d['sales']),1)
    req('/api/users',{'name':'Vendedora','username':'ventas','password':'prueba-temporal-456','role':'ventas'})
    req('/api/logout',{});req('/api/login',{'username':'ventas','password':'prueba-temporal-456'})
    d=req('/api/data');self.assertNotIn('users',d);self.assertNotIn('purchases',d);self.assertNotIn('services',d)
    with self.assertRaises(urllib.error.HTTPError) as e:req('/api/users',{'name':'intruso'})
    self.assertEqual(e.exception.code,403)
   finally:server.shutdown();server.server_close();thread.join();app.DB=old
if __name__=='__main__':unittest.main()
