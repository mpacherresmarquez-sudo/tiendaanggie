import os, json, sqlite3, secrets, hashlib, hmac, datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path

ROOT=Path(__file__).parent
DB=os.environ.get('ANGGIE_DB',str(ROOT/'data/anggie.db'))
SESSIONS={}
PERMS={'admin':{'products','customers','suppliers','sales','purchases','payments','services','companies','users','funds'},'ventas':{'sales','customers','payments'},'compras':{'purchases','suppliers','products'},'servicios':{'services','companies','funds'}}
def password(value,salt=None):
 salt=salt or secrets.token_hex(16)
 return salt+':'+hashlib.scrypt(value.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
def connect():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
def init():
 Path(DB).parent.mkdir(parents=True,exist_ok=True)
 with connect() as c:
  c.executescript('''
 CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL,active INTEGER DEFAULT 1);
 CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,name TEXT NOT NULL,category TEXT,presentation TEXT,price INTEGER NOT NULL,cost INTEGER NOT NULL,stock REAL DEFAULT 0,minimum REAL DEFAULT 5);
 CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,document TEXT,phone TEXT,address TEXT);
 CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,document TEXT,phone TEXT,address TEXT);
 CREATE TABLE IF NOT EXISTS companies(id INTEGER PRIMARY KEY,name TEXT NOT NULL,type TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY,date TEXT,user_id INTEGER,customer_id INTEGER REFERENCES customers(id),mode TEXT,total INTEGER,cost INTEGER);
 CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY,date TEXT,user_id INTEGER,supplier_id INTEGER REFERENCES suppliers(id),total INTEGER);
 CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,kind TEXT,document_id INTEGER,product_id INTEGER REFERENCES products(id),quantity REAL,price INTEGER,cost INTEGER);
 CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY,date TEXT,product_id INTEGER,quantity REAL,reference TEXT,user_id INTEGER);
 CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY,date TEXT,sale_id INTEGER REFERENCES sales(id),amount INTEGER,user_id INTEGER);
 CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY,date TEXT,user_id INTEGER,company_id INTEGER REFERENCES companies(id),destination TEXT,period TEXT,amount INTEGER,charge INTEGER,commission INTEGER,state TEXT DEFAULT 'PENDIENTE',code TEXT,reason TEXT,UNIQUE(company_id,code));
 CREATE TABLE IF NOT EXISTS funds(id INTEGER PRIMARY KEY,date TEXT,amount INTEGER,reference TEXT,user_id INTEGER);
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,date TEXT,user_id INTEGER,action TEXT,detail TEXT);
 ''')
  columns={r['name'] for r in c.execute('PRAGMA table_info(services)')}
  for column in ('payment_method','bank','payment_reference'):
   if column not in columns: c.execute(f'ALTER TABLE services ADD COLUMN {column} TEXT')
  item_columns={r['name'] for r in c.execute('PRAGMA table_info(items)')}
  for column,definition in [('purchase_unit',"TEXT DEFAULT ''"),('purchase_quantity','REAL'),('conversion_factor','REAL DEFAULT 1'),('purchase_price','INTEGER')]:
   if column not in item_columns: c.execute(f'ALTER TABLE items ADD COLUMN {column} {definition}')
  from catalog import load_catalog
  load_catalog(c)
  if not c.execute('SELECT 1 FROM companies').fetchone():
   c.executemany('INSERT INTO companies(name,type) VALUES(?,?)',[('Claro','RECARGA'),('Movistar','RECARGA'),('Entel','RECARGA'),('Bitel','RECARGA'),('Empresa de luz','LUZ'),('Empresa de agua','AGUA')])
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def money(v):
 from decimal import Decimal, InvalidOperation
 try:
  d=Decimal(str(v)); assert d.is_finite() and d>=0 and d.as_tuple().exponent>=-2
  return int(d*100)
 except (InvalidOperation,AssertionError,ValueError): raise ValueError('Importe inválido; usa hasta dos decimales.')
def positive(v):
 import math
 n=float(v)
 if not math.isfinite(n) or n<=0: raise ValueError('La cantidad debe ser positiva.')
 return n

def write(c,kind,d,u):
 uid=u['id']; role=u['role']
 if kind not in PERMS[role]: raise PermissionError('No tienes permiso para esta operación.')
 if kind in ('customers','suppliers'):
  if not d.get('name','').strip(): raise ValueError('El nombre es obligatorio.')
  c.execute(f'INSERT INTO {kind}(name,document,phone,address) VALUES(?,?,?,?)',[d.get(k,'') for k in ('name','document','phone','address')])
 elif kind=='companies':
  if not d.get('name'): raise ValueError('Indica la empresa.')
  c.execute('INSERT INTO companies(name,type) VALUES(?,?)',(d['name'],d['type']))
 elif kind=='products':
  if not d.get('name') or not d.get('presentation'): raise ValueError('Indica producto y presentación.')
  vals=[d['name'],d.get('category',''),d['presentation'],money(d['price']),money(d['cost']),float(d.get('minimum',5))]
  if not __import__('math').isfinite(vals[-1]) or vals[-1]<0: raise ValueError('Mínimo inválido.')
  if d.get('id'): c.execute('UPDATE products SET name=?,category=?,presentation=?,price=?,cost=?,minimum=? WHERE id=?',vals+[int(d['id'])])
  else: c.execute('INSERT INTO products(name,category,presentation,price,cost,minimum) VALUES(?,?,?,?,?,?)',vals)
 elif kind in ('sales','purchases'):
  lines=d.get('items',[])
  if not lines: raise ValueError('Agrega productos a la operación.')
  if kind=='sales' and d.get('mode') not in ('Contado','Fiado'): raise ValueError('Tipo de venta inválido.')
  if kind=='sales' and d['mode']=='Fiado' and not d.get('customer_id'): raise ValueError('Selecciona un cliente para el fiado.')
  if kind=='purchases' and not d.get('supplier_id'): raise ValueError('Selecciona un proveedor.')
  total=0; cost=0; details=[]; counts={}
  for line in lines:
   p=c.execute('SELECT * FROM products WHERE id=? AND archived=0',(int(line['product_id']),)).fetchone()
   if not p: raise ValueError('Producto no encontrado.')
   entered=positive(line['quantity']); factor=positive(line.get('conversion_factor',1)) if kind=='purchases' else 1
   q=entered*factor
   if not __import__('math').isfinite(q): raise ValueError('Cantidad convertida inválida.')
   counts[p['id']]=counts.get(p['id'],0)+q
   if kind=='sales' and counts[p['id']]>p['stock']: raise ValueError('Stock insuficiente: '+p['name'])
   price=p['price'] if kind=='sales' else money(line['price'])
   line_total=round((entered if kind=='purchases' else q)*price)
   total+=line_total; cost+=round(q*p['cost']); details.append((p,q,price,entered,factor,line_total,line.get('purchase_unit','Unidad de venta')))
  if kind=='sales': cur=c.execute('INSERT INTO sales(date,user_id,customer_id,mode,total,cost) VALUES(?,?,?,?,?,?)',(now(),uid,d.get('customer_id') or None,d['mode'],total,cost))
  else: cur=c.execute('INSERT INTO purchases(date,user_id,supplier_id,total) VALUES(?,?,?,?)',(now(),uid,int(d['supplier_id']),total))
  doc=cur.lastrowid
  for p,q,price,entered,factor,line_total,purchase_unit in details:
   delta=-q if kind=='sales' else q
   if kind=='purchases':
    current=c.execute('SELECT stock,cost FROM products WHERE id=?',(p['id'],)).fetchone()
    avg=round((current['stock']*current['cost']+line_total)/(current['stock']+q))
    c.execute('UPDATE products SET cost=? WHERE id=?',(avg,p['id']))
   c.execute('UPDATE products SET stock=stock+? WHERE id=?',(delta,p['id']))
   c.execute('INSERT INTO items(kind,document_id,product_id,quantity,price,cost,purchase_unit,purchase_quantity,conversion_factor,purchase_price) VALUES(?,?,?,?,?,?,?,?,?,?)',(kind,doc,p['id'],q,round(price/factor) if kind=='purchases' else price,p['cost'],purchase_unit if kind=='purchases' else '',entered if kind=='purchases' else None,factor,price if kind=='purchases' else None))
   c.execute('INSERT INTO movements(date,product_id,quantity,reference,user_id) VALUES(?,?,?,?,?)',(now(),p['id'],delta,f'{kind} #{doc}',uid))
 elif kind=='payments':
  s=c.execute("SELECT total-COALESCE((SELECT SUM(amount) FROM payments WHERE sale_id=sales.id),0) balance FROM sales WHERE id=? AND mode='Fiado'",(d['sale_id'],)).fetchone()
  amount=money(d['amount'])
  if not s or amount<=0 or amount>s['balance']: raise ValueError('El abono debe ser positivo y no superar la deuda.')
  c.execute('INSERT INTO payments(date,sale_id,amount,user_id) VALUES(?,?,?,?)',(now(),d['sale_id'],amount,uid))
 elif kind=='services':
  if d.get('id'):
   s=c.execute('SELECT * FROM services WHERE id=?',(d['id'],)).fetchone()
   if not s: raise ValueError('Operación inexistente.')
   state=d['state']; code=d.get('code','').strip()
   if state not in ('CONFIRMADO','FALLIDO','ANULADO'): raise ValueError('Estado inválido.')
   if s['state']!='PENDIENTE' and not (role=='admin' and state=='ANULADO'): raise ValueError('Esta operación ya fue procesada.')
   if state=='CONFIRMADO':
    if not code or not d.get('external_confirmation'): raise ValueError('Se requiere código y confirmación externa del proveedor.')
    balance=c.execute('SELECT COALESCE(SUM(amount),0) FROM funds').fetchone()[0]
    used=c.execute("SELECT COALESCE(SUM(amount),0) FROM services WHERE state='CONFIRMADO' AND payment_method IS NULL").fetchone()[0]
    if not s['payment_method'] and balance-used<s['amount']: raise ValueError('Saldo de plataforma insuficiente; registra una carga.')
   if state=='ANULADO' and (role!='admin' or not d.get('reason')): raise ValueError('Solo el administrador puede anular, con un motivo.')
   c.execute('UPDATE services SET state=?,code=?,reason=? WHERE id=?',(state,code or s['code'],d.get('reason',''),s['id']))
   # Anulación interna conserva el consumo; no equivale a reversión externa.
   if not s['payment_method'] and s['state']=='CONFIRMADO' and state=='ANULADO': c.execute('INSERT INTO funds(date,amount,reference,user_id) VALUES(?,?,?,?)',(now(),-s['amount'],'Consumo retenido por anulación interna #'+str(s['id']),uid))
  else:
   method=d.get('payment_method')
   if method not in ('Yape','Transferencia bancaria'): raise ValueError('Selecciona Yape o transferencia bancaria.')
   bank=d.get('bank','').strip() if method=='Transferencia bancaria' else ''
   if method=='Transferencia bancaria' and not bank: raise ValueError('Indica el banco de la transferencia.')
   reference=d.get('payment_reference','').strip()
   company=c.execute('SELECT * FROM companies WHERE id=?',(d['company_id'],)).fetchone()
   dest=d.get('destination','').strip()
   if not company or not dest or dest!=d.get('confirmation'): raise ValueError('La referencia y su confirmación deben coincidir.')
   if company['type']=='RECARGA' and (len(dest)!=9 or not dest.isdigit()): raise ValueError('El celular debe tener 9 dígitos.')
   amount=money(d['amount'])
   if not amount: raise ValueError('El importe debe ser positivo.')
   c.execute('INSERT INTO services(date,user_id,company_id,destination,period,amount,charge,commission,payment_method,bank,payment_reference) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(now(),uid,company['id'],dest,'' if company['type']=='RECARGA' else d.get('period',''),amount,money(d.get('charge',0)),0,method,bank,reference))
 elif kind=='funds':
  amount=money(d['amount'])
  if not amount or not d.get('reference'): raise ValueError('Indica monto positivo y referencia de la carga.')
  c.execute('INSERT INTO funds(date,amount,reference,user_id) VALUES(?,?,?,?)',(now(),amount,d['reference'],uid))
 elif kind=='users':
  if d.get('role') not in PERMS: raise ValueError('Rol inválido.')
  if d.get('id'):
   if int(d['id'])==uid: raise ValueError('No puedes desactivar o modificar tu propio acceso.')
   c.execute('UPDATE users SET name=?,role=?,active=? WHERE id=?',(d['name'],d['role'],int(d.get('active',1)),d['id']))
  else:
   if len(d.get('password',''))<10: raise ValueError('Usa una contraseña de al menos 10 caracteres.')
   c.execute('INSERT INTO users(name,username,password,role) VALUES(?,?,?,?)',(d['name'],d['username'],password(d['password']),d['role']))
 c.execute('INSERT INTO audit(date,user_id,action,detail) VALUES(?,?,?,?)',(now(),uid,kind,'Registro '+str(d.get('id','nuevo'))))

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def respond(self,status,data,headers=None):
  b=json.dumps(data,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store')
  for k,v in (headers or {}).items(): self.send_header(k,v)
  self.end_headers(); self.wfile.write(b)
 def user(self,c):
  cookie=SimpleCookie(self.headers.get('Cookie','')); token=cookie.get('session'); session=SESSIONS.get(token.value if token else '')
  if not session or session['expires']<datetime.datetime.now().timestamp(): return None
  return c.execute('SELECT id,name,username,role FROM users WHERE id=? AND active=1',(session['id'],)).fetchone()
 def do_GET(self):
  if self.path.startswith('/api/'):
   with connect() as c:
    if self.path=='/api/session':
     u=self.user(c); return self.respond(200,{'user':dict(u) if u else None,'setup':not bool(c.execute('SELECT 1 FROM users').fetchone())})
    u=self.user(c)
    if not u: return self.respond(401,{'error':'Inicia sesión.'})
    if self.path=='/api/data':
     role=u['role']; tables={'products','customers','companies'}
     if role in ('admin','ventas'): tables|={'sales','payments'}
     if role in ('admin','compras'): tables|={'suppliers','purchases','movements'}
     if role in ('admin','servicios'): tables|={'services','funds'}
     if role=='admin': tables|={'audit'}
     result={t:[dict(r) for r in c.execute('SELECT * FROM '+t+(' WHERE archived=0' if t=='products' else ''))] for t in tables}
     if role=='admin': result['users']=[dict(r) for r in c.execute('SELECT id,name,username,role,active FROM users')]
     return self.respond(200,result)
    return self.respond(404,{'error':'Ruta inexistente.'})
  name='index.html' if self.path=='/' else self.path.lstrip('/').split('?')[0]
  p=(ROOT/'static'/name).resolve()
  if not p.is_relative_to((ROOT/'static').resolve()) or not p.is_file(): return self.respond(404,{'error':'No encontrado.'})
  self.send_response(200); self.send_header('Content-Type',{'html':'text/html; charset=utf-8','css':'text/css','js':'application/javascript','svg':'image/svg+xml'}.get(p.suffix[1:],'text/plain')); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(p.read_bytes())
 def do_POST(self):
  if self.headers.get('X-Anggie')!='1': return self.respond(403,{'error':'Solicitud no autorizada.'})
  try:
   size=int(self.headers.get('Content-Length',0))
   if size>100000: raise ValueError('Solicitud demasiado grande.')
   d=json.loads(self.rfile.read(size))
   with connect() as c:
    c.execute('BEGIN IMMEDIATE')
    if self.path=='/api/setup':
     if c.execute('SELECT 1 FROM users').fetchone(): raise ValueError('El administrador ya está configurado.')
     if len(d.get('password',''))<10 or not d.get('username') or not d.get('name'): raise ValueError('Completa tus datos; contraseña mínima de 10 caracteres.')
     c.execute("INSERT INTO users(name,username,password,role) VALUES(?,?,?,'admin')",(d['name'],d['username'],password(d['password'])))
     return self.respond(200,{'ok':True})
    if self.path=='/api/login':
     u=c.execute('SELECT * FROM users WHERE username=? AND active=1',(d.get('username'),)).fetchone()
     if not u or not hmac.compare_digest(password(d.get('password',''),u['password'].split(':')[0]),u['password']): return self.respond(401,{'error':'Usuario o contraseña incorrectos.'})
     token=secrets.token_urlsafe(32); SESSIONS[token]={'id':u['id'],'expires':datetime.datetime.now().timestamp()+28800}
     return self.respond(200,{'ok':True},{'Set-Cookie':f'session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'})
    u=self.user(c)
    if not u: return self.respond(401,{'error':'Inicia sesión.'})
    if self.path=='/api/logout':
     cookie=SimpleCookie(self.headers.get('Cookie','')); SESSIONS.pop(cookie['session'].value,None)
     return self.respond(200,{'ok':True},{'Set-Cookie':'session=; Max-Age=0; Path=/'})
    write(c,self.path.removeprefix('/api/'),d,u)
   self.respond(200,{'ok':True})
  except PermissionError as e: self.respond(403,{'error':str(e)})
  except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e: self.respond(400,{'error':'Datos inválidos o referencia duplicada.' if isinstance(e,sqlite3.IntegrityError) else str(e)})
  except Exception: self.respond(500,{'error':'No se pudo guardar la operación.'})
if __name__=='__main__':
 init(); print('La Tienda de Don Pepe: servidor iniciado',flush=True); ThreadingHTTPServer((os.environ.get('HOST','127.0.0.1'),int(os.environ.get('PORT','8000'))),Handler).serve_forever()
