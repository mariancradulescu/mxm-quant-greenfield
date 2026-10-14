"""Authenticated corpus reconciliation adapters. SQLite, cropped DEVELOPMENT only."""
import os,json,gzip,base64,hashlib,sqlite3,datetime,io,csv,zipfile,re
from pathlib import Path
from m6.cost_evidence import decode_ctrader_tick_page
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
E=rt.e
START=1787529600;END=1789344000;LOW=START-5*86400;CUT=1789603200
# 2026-08-24 through 2026-09-14, before the protected boundary.
def ts(v):
 if isinstance(v,(float,int)):return int(v)
 return int(datetime.datetime.fromisoformat(v.replace('Z','+00:00')).timestamp())
def dbopen(path):
 db=sqlite3.connect(path);db.executescript('CREATE TABLE IF NOT EXISTS bar(s INTEGER,t INTEGER,o REAL,h REAL,l REAL,c REAL,v REAL,PRIMARY KEY(s,t));CREATE TABLE IF NOT EXISTS tick(s INTEGER,k TEXT,t INTEGER,p INTEGER,PRIMARY KEY(s,k,t,p));CREATE TABLE IF NOT EXISTS span(s INTEGER,k TEXT,a INTEGER,b INTEGER,z TEXT,PRIMARY KEY(s,k,a,b));CREATE INDEX IF NOT EXISTS ticks_lookup ON tick(s,k,t);CREATE INDEX IF NOT EXISTS bar_group ON bar(s%64);CREATE INDEX IF NOT EXISTS tick_group ON tick(s%64);CREATE INDEX IF NOT EXISTS span_group ON span(s%64);');return db

def putbar(db,s,t,values):
 t=ts(t)
 if not LOW<=t<END:return
 vals=[float(x) for x in values]
 if len(vals)!=5 or t%300 or not 0<vals[2]<=min(vals[0],vals[3])<=max(vals[0],vals[3])<=vals[1]:raise ValueError('BAR_INTEGRITY')
 old=db.execute('SELECT o,h,l,c,v FROM bar WHERE s=? AND t=?',(s,t)).fetchone()
 if old and any(abs(a-b)>1e-9*max(1,abs(a),abs(b)) for a,b in zip(old,vals)):raise ValueError('CONFLICTING_AUTHENTIC_BAR')
 db.execute('INSERT OR IGNORE INTO bar VALUES(?,?,?,?,?,?,?)',(s,t,*vals))
def tickrows(db,s,k,encoded,a,b):
 if not LOW*1000<=b<END*1000:return
 dec=decode_ctrader_tick_page(encoded)
 if any(not a<=r.timestamp_ms<=b for r in dec):raise ValueError('TICK_WINDOW_BINDING')
 db.executemany('INSERT OR IGNORE INTO tick VALUES(?,?,?,?)',[(s,k,r.timestamp_ms,r.raw_tick) for r in dec]);return len(dec)
def span(db,s,k,a,b,z):
 if a<=b:db.execute('INSERT OR REPLACE INTO span VALUES(?,?,?,?,?)',(int(s),k,int(a),int(b),z))
def qadd(db,q):
 if 'symbol_id' not in q or 'boundary_ms' not in q:return 0
 sid=int(q['symbol_id']);b=int(q['boundary_ms']);n=0
 for p in q.get('pages',q.get('raw_pages',[])):
  k=p.get('side');enc=p.get('encoded',p.get('encoded_tick_rows',p.get('encoded_ticks')))
  if k not in ('bid','ask') or enc is None:continue
  decoded=decode_ctrader_tick_page(enc);earliest=min([r.timestamp_ms for r in decoded] or [b-60000]);a=int(p.get('request_from_ms',p.get('from_ms',min(b-60000,earliest))));hi=int(p.get('request_to_ms',p.get('to_ms',b)))
  n+=tickrows(db,sid,k,enc,a,hi) or 0
  # Never repeat even a previously requested truncated/empty source window.
  span(db,sid,k,a,hi,'ARCHIVED_REQUEST_PARTIAL' if p.get('hasMore') else 'ARCHIVED_COMPLETE_RESPONSE')
 return n

def extract(db,obj):
 n={'quotes':0,'bars':0,'recognized':False}
 def rec(v,context=None,kind=None):
  if isinstance(v,list):
   for x in v:rec(x,context,kind)
   return
  if not isinstance(v,dict):return
  if 'symbol_id' in v and 'boundary_ms' in v and ('pages' in v or 'raw_pages' in v):n['quotes']+=qadd(db,v);n['recognized']=True;return
  if 'member_bytes_b64' in v and 'sid' in v:
   raw=base64.b64decode(v['member_bytes_b64'])
   if v.get('member_sha256') and hashlib.sha256(raw).hexdigest()!=v['member_sha256']:raise ValueError('CSV_MEMBER_SHA')
   for row in csv.DictReader(io.StringIO(raw.decode())):
    if 'time_utc' in row and all(k in row for k in ('open','high','low','close','tick_volume')):putbar(db,int(v['sid']),row['time_utc'],[row[k] for k in ('open','high','low','close','tick_volume')]);n['bars']+=1;n['recognized']=True
   return
  if 'items' in v and 'segment_index' in v and 'shard_index' in v:
   seg=int(v['segment_index']);a=1787184000+(seg-1)*604800;b=a+604800
   for item in v['items']:
    sid=int(item['symbol_id'])
    for row in item['rows']:putbar(db,sid,row['time_utc'],[row[k] for k in ('open','high','low','close','tick_volume')]);n['bars']+=1
    span(db,sid,'M5',a*1000,b*1000-1,'ACCEPTED_EXACT_M5_INTERVAL')
   n['recognized']=True;return
  if 'sid' in v and 'start' in v and 'bars' in v and isinstance(v['bars'],dict):
   for t,row in v['bars'].items():putbar(db,int(v['sid']),int(t),row);n['bars']+=1
   if v.get('status') in ('COMPLETE_EXACT_WINDOW','REUSED_AUTHENTIC_NATIVE_M5_INTERVAL'):span(db,int(v['sid']),'M5',(int(v['start'])-5*86400)*1000,(int(v['start'])+7*86400)*1000-1,'ACCEPTED_EXACT_M5_INTERVAL')
   n['recognized']=True
  for key in ('bars','private_m5_rows'):
   vv=v.get(key)
   if isinstance(vv,dict):
    for s,rr in vv.items():
     try:sid=int(s)
     except (ValueError,TypeError):continue
     if isinstance(rr,dict):
      for t,row in rr.items():
       if isinstance(row,list) and len(row)==5:putbar(db,sid,int(t),row);n['bars']+=1;n['recognized']=True
     elif isinstance(rr,list):
      for row in rr:
       if isinstance(row,dict) and 'time_utc' in row and all(k in row for k in ('open','high','low','close','tick_volume')):putbar(db,sid,row['time_utc'],[row[k] for k in ('open','high','low','close','tick_volume')]);n['bars']+=1;n['recognized']=True
  for key,x in v.items():
   if key not in ('bars','private_m5_rows','items','pages','raw_pages','encoded','encoded_tick_rows','encoded_ticks','records','events','summary','proposed_records'):rec(x)
 rec(obj);db.commit();return n

def all_locators(root):
 bindings={};unresolved=[];release_ids=set()
 def rec(v,path):
  if isinstance(v,list):
   for x in v:rec(x,path)
  elif isinstance(v,dict):
   rid=v.get('release_id');aid=v.get('asset_id',v.get('id'));digest=v.get('ciphertext_sha256')
   if isinstance(rid,int) and rid>0:release_ids.add(rid)
   if isinstance(rid,int) and isinstance(aid,int) and isinstance(digest,str) and re.fullmatch('[a-f0-9]{64}',digest):bindings[(rid,aid)]={'release_id':rid,'asset_id':aid,'ciphertext_sha256':digest,'acceptance_path':path}
   for x in v.values():rec(x,path)
 for p in root.rglob('*.json'):
  name=str(p.relative_to(root))
  if any(x in name.lower() for x in ('synthetic','fabricated','fixture','/test','full_native_frontier_20261014_v1')):continue
  try:rec(json.loads(p.read_text()),name)
  except (ValueError,UnicodeError):continue
 return bindings,release_ids

def read_raw(key,fp,tmp,asset,digest=None):
 if digest and asset.get('digest')!='sha256:'+digest:raise ValueError('ASSET_PIN_DRIFT')
 blob=E.w.old.download(asset['browser_download_url'],asset['size'])
 if asset.get('digest')!='sha256:'+hashlib.sha256(blob).hexdigest():raise ValueError('CIPHER_DIGEST')
 raw=E.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
 if raw.startswith(b'\x1f\x8b'):raw=gzip.decompress(raw)
 return raw

def global_reconcile(db,key,fp,tmp,root):
 bindings,ids=all_locators(root);receipts=[];seen=set();queue=list(sorted(ids));meta_by_id={}
 # Full legacy shallow campaign is identified by the accepted durable tag.
 shallow=json.loads((root/E.w.old.MANIFEST).read_text());tag=shallow['entries'][0]['DURABLE_RELEASE_IDENTITY'];rel=E.w.old.api('releases/tags/'+tag);queue.append(rel['id'])
 pin_names={v['ENCRYPTED_ASSET_NAME']:v for v in shallow['entries']}
 # Accepted historical field sources may expose checkpoint releases only inside
 # encrypted primary manifests. Those references are recursively reconciled.
 while queue:
  rid=queue.pop(0)
  if rid in seen:continue
  seen.add(rid)
  try:rel=E.w.old.api('releases/'+str(rid))
  except Exception as ex:receipts.append({'release_id':rid,'state':'UNKNOWN_WITH_EXACT_CAUSE','cause':'REFERENCED_RELEASE_UNREADABLE_IN_EXISTING_SCOPE','exception_class':type(ex).__name__});continue
  label=(rel.get('tag_name','')+' '+rel.get('name','')).lower()
  if any(x in label for x in ('synthetic','fabricated','mxm-dom','dom-information','dom-probe','demo')):receipts.append({'release_id':rid,'state':'SKIPPED_SYNTHETIC_OR_LIVE_TECHNICAL_OR_PROTECTED_SCOPE'});continue
  assets=[]
  for page in range(1,6):
   batch=E.w.old.api('releases/'+str(rid)+'/assets?per_page=100&page='+str(page));assets+=batch
   if len(batch)<100:break
  for a in assets:
   name=a['name'].lower();binding=bindings.get((rid,a['id']));pin=pin_names.get(a['name'])
   if not name.endswith('.mxmenc') or any(x in name for x in ('recipient','relay','delivery','attestation','summary','signed','journal','factor','pilot','drift','financing','locators','calibration','geometry','synthetic','fabricated')):continue
   if a['size']>128*1024*1024:receipts.append({'release_id':rid,'asset_id':a['id'],'state':'OWNER_ASSET_SIZE_GT128M_EXISTING_DECODER_LIMIT'});continue
   digest=pin['ENCRYPTED_ASSET_SHA256'] if pin else binding['ciphertext_sha256'] if binding else a.get('digest','').removeprefix('sha256:')
   try:
    raw=read_raw(key,fp,tmp,a,digest)
    if pin and hashlib.sha256(raw).hexdigest()!=pin['PLAINTEXT_CANONICAL_SHA256']:raise ValueError('SHALLOW_PLAINTEXT_PIN')
    obj=E.w.old.crypto.strict_json(raw);n=extract(db,obj);receipts.append({'release_id':rid,'asset_id':a['id'],'ciphertext_sha256':digest,'raw_sha256':hashlib.sha256(raw).hexdigest(),'state':'RECONCILED_NATIVE_FIELDS' if n['recognized'] else 'NO_RECOGNIZED_NATIVE_MARKET_FIELDS','counts':n})
    def refs(v):
     if isinstance(v,list):
      for x in v:refs(x)
     elif isinstance(v,dict):
      rr=v.get('release_id');aa=v.get('id',v.get('asset_id'));dd=v.get('ciphertext_sha256')
      if isinstance(rr,int) and isinstance(aa,int) and isinstance(dd,str):bindings[rr,aa]={'release_id':rr,'asset_id':aa,'ciphertext_sha256':dd};queue.append(rr)
      for x in v.values():refs(x)
    refs(obj)
   except Exception as ex:
    if str(ex) in ('CONFLICTING_AUTHENTIC_BAR','TICK_WINDOW_BINDING','SHALLOW_PLAINTEXT_PIN','ASSET_PIN_DRIFT','CIPHER_DIGEST'):raise
    receipts.append({'release_id':rid,'asset_id':a['id'],'ciphertext_sha256':digest,'state':'UNKNOWN_WITH_EXACT_CAUSE','exception_class':type(ex).__name__,'cause':'NOT_RECOGNIZED_OWNER_JSON_ENVELOPE_OR_NO_SUPPORTED_SCHEMA_ADAPTER'})
  print(json.dumps({'phase':'GLOBAL_NATIVE_ARCHIVE_RECONCILIATION','releases_processed':len(seen),'assets_classified':len(receipts)}),flush=True)
 # Inline accepted packages and plaintext historical CSVs are explicitly inventoried.
 inline=[]
 for p in root.rglob('*'):
  if not p.is_file():continue
  name=str(p.relative_to(root));low=name.lower()
  if any(x in low for x in ('synthetic','fabricated','fixture','/test','full_native_frontier_20261014_v1')):continue
  if low.endswith('.mxmenc.b64'):
   try:
    blob=base64.b64decode(p.read_bytes());raw=E.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
    if raw.startswith(b'\x1f\x8b'):raw=gzip.decompress(raw)
    n=extract(db,E.w.old.crypto.strict_json(raw));inline.append({'path':name,'state':'INLINE_OWNER_FIELDS_RECONCILED','counts':n})
   except Exception as ex:inline.append({'path':name,'state':'UNKNOWN_WITH_EXACT_CAUSE','cause':'INLINE_MULTI_PART_OR_UNSUPPORTED_OWNER_SCHEMA','exception_class':type(ex).__name__})
 for p in root.rglob('*ARCHIVE*MANIFEST*.json'):
  try:
   manifest=json.loads(p.read_text());parts=manifest.get('parts')
   if not parts or not all(isinstance(x,str) and (root/x).is_file() for x in parts):continue
   blob=base64.b64decode(''.join((root/x).read_text().strip() for x in parts));raw=E.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
   if raw.startswith(b'\x1f\x8b'):raw=gzip.decompress(raw)
   n=extract(db,E.w.old.crypto.strict_json(raw));inline.append({'path':str(p.relative_to(root)),'state':'MULTIPART_ACCEPTED_OWNER_FIELDS_RECONCILED','counts':n})
  except Exception as ex:inline.append({'path':str(p.relative_to(root)),'state':'UNKNOWN_WITH_EXACT_CAUSE','cause':'MULTIPART_SCHEMA_OR_OWNER_ROUTE_UNSUPPORTED','exception_class':type(ex).__name__})
 return {'releases_inspected':len(seen),'asset_receipts':receipts,'inline_receipts':inline,'scope':'ALL_REPOSITORY_PINNED_RELEASE_REFERENCES_AND_RECURSIVE_PRIMARY_CHECKPOINT_LOCATORS;NON_NATIVE_UNPARSED_SOURCES_EXPLICIT','bars_in_relevant_domain':db.execute('SELECT count(*) FROM bar').fetchone()[0],'ticks_in_relevant_domain':db.execute('SELECT count(*) FROM tick').fetchone()[0]}

def missing(db,s,k,a,b):
 ranges=db.execute('SELECT a,b FROM span WHERE s=? AND k=? AND b>=? AND a<=? ORDER BY a',(s,k,a,b)).fetchall();out=[];cur=a
 for lo,hi in ranges:
  if lo>cur:out.append((cur,min(b,lo-1)))
  cur=max(cur,hi+1)
  if cur>b:break
 if cur<=b:out.append((cur,b))
 return out
