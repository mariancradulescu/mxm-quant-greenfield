"""Accept two authentic Pepperstone captures and freeze exact primary input provenance.

No economic response is calculated here. Input ZIPs remain immutable, gap-preserving.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,math,zipfile
from datetime import datetime,timezone
from pathlib import Path

def canonical_hash(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def frozen_scope(root):
 document=json.loads((root/'research_core_v3/state/INCLUSIVE_FULL_DEPTH_DISCOVERY_CORE_V1.json').read_text())
 sha=document.pop('sha256')
 if canonical_hash(document)!=sha:raise ValueError('frozen core manifest')
 document['sha256']=sha
 quality=gzip.decompress((root/'research_core_v3/state/ACCEPTED_DATA_QUALITY_TABLE_V1.json.gz').read_bytes())
 if hashlib.sha256(quality).hexdigest()!=document['source_quality_table_sha256']:raise ValueError('frozen quality table')
 return document,quality,document['delta_ids']

EXPECTED_ORIGINAL='09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259'
EXPECTED_DELTA='37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e'
EXPECTED_ROWS=11406418

def digest(stream):
 h=hashlib.sha256()
 while block:=stream.read(1<<20):h.update(block)
 return h.hexdigest()
def timestamp(s):return datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(timezone.utc)
def check_archive(path,expected_sha,frozen,quality_sha):
 if digest(path.open('rb'))!=expected_sha:raise ValueError('outer ZIP SHA mismatch')
 with zipfile.ZipFile(path) as z:
  names=z.namelist();name_set=set(names)
  if len(names)!=len(name_set) or z.testzip() is not None:raise ValueError('ZIP CRC or duplicate name')
  def read(n):return z.read(n)
  manifest=json.loads(read('CAPTURE_MANIFEST.json'))
  payload_data=read('V3_CAPTURE_PAYLOAD.json');payload=json.loads(payload_data)
  selected=json.loads(read('SELECTED_IDENTITY_MANIFEST.json'));sha=selected.pop('sha256')
  if canonical_hash(selected)!=sha:raise ValueError('selected manifest hash')
  selected['sha256']=sha
  if payload['selected_identity_manifest_sha256']!=sha or payload['plan_sha256']!=selected['plan_sha256']:raise ValueError('payload selection binding')
  if hashlib.sha256(payload_data).hexdigest()!=manifest['sha256_per_canonical_payload']['V3_CAPTURE_PAYLOAD.json']:raise ValueError('canonical payload binding')
  if hashlib.sha256(read('DATA_QUALITY_TABLE.json')).hexdigest()!=quality_sha:raise ValueError('frontier table changed')
  if len(json.loads(read('DATA_QUALITY_TABLE.json'))['rows'])!=1576:raise ValueError('frontier count')
  if payload['source_environment']!='Pepperstone - Europe LIVE' or payload['account_fingerprint_sha256']!=frozen['source_account_fingerprint_sha256']:raise ValueError('account or broker')
  if any([payload['status']!='CAPTURE_COMPLETE',manifest['completion_state']!='COMPLETE',payload['economic_outcomes_opened'],payload['protected_forward_opened'],payload['orders_placed'],payload['account_mutation'],manifest['protected_evidence_opened']]):raise ValueError('protected or mutation assertion')
  if expected_sha==EXPECTED_DELTA and payload['frozen_primary_core_sha256']!=frozen['sha256']:raise ValueError('delta core binding')
  checksums={}
  for line in read('CHECKSUMS.sha256').decode().splitlines():
   h,n=line.split('  ',1)
   if n in checksums:raise ValueError('duplicate checksum path')
   checksums[n]=h
  required={x['file'] for x in payload['series']}|{'CAPTURE_MANIFEST.json','DATA_QUALITY_TABLE.json','SELECTED_IDENTITY_MANIFEST.json','V3_CAPTURE_PAYLOAD.json'}
  if not required<=checksums.keys():raise ValueError('checksum coverage')
  for n,h in checksums.items():
   with z.open(n) as stream:actual=digest(stream)
   if actual!=h:raise ValueError('internal checksum '+n)
   duplicates=[x for x in names if x.endswith('/'+n) and x!=n]
   if len(duplicates)!=1:raise ValueError('transport duplicate count '+n)
   with z.open(duplicates[0]) as stream:duplicate=digest(stream)
   if duplicate!=h:raise ValueError('conflicting transport duplicate '+n)
  ids={int(x['symbol_id']):x for x in selected['symbols']}
  if len(ids)!=len(selected['symbols']):raise ValueError('selected duplicate ID')
  entries={}
  for item in payload['series']:
   sid=int(item['symbol_id']);n=item['file']
   if sid not in ids or ids[sid]['broker_symbol']!=item['broker_symbol'] or sid in entries:raise ValueError('series identity')
   if checksums[n]!=item['sha256']:raise ValueError('series hash differs from checksums')
   count=0;gaps=0;first=last=None;prev=None
   with z.open(n) as raw:
    for row in csv.DictReader(io.TextIOWrapper(raw,encoding='utf-8-sig',newline='')):
     t=timestamp(row['time_utc']);v=[float(row[k]) for k in ('open','high','low','close','tick_volume')]
     o,h,l,c,vol=v
     if not all(map(math.isfinite,v)) or not 0<l<=o<=h or not l<=c<=h or vol<0:raise ValueError('OHLC/volume '+n)
     if t.minute%5 or t.second or t.microsecond or (prev is not None and (t<=prev or (t-prev).total_seconds()%300)):raise ValueError('M5 timestamp '+n)
     if t>=timestamp(frozen['protected_forward_start']):raise ValueError('protected forward '+n)
     if prev is not None and (t-prev).total_seconds()>300:gaps+=1
     if first is None:first=row['time_utc']
     last=row['time_utc'];prev=t;count+=1
   if count!=item['row_count'] or first!=item['first_timestamp_utc'] or last!=item['last_timestamp_utc'] or gaps!=item['gap_count_24x7_reference']:raise ValueError('series metadata '+n)
   entries[sid]={'symbol_id':sid,'symbol':item['broker_symbol'],'source_archive_sha256':expected_sha,'file':n,'series_sha256':item['sha256'],'row_count':count,'first_timestamp_utc':first,'last_timestamp_utc':last,'gap_count_24x7_reference':gaps}
  if len(entries)!=len(ids) or sum(e['row_count'] for e in entries.values())!=payload['total_m5_rows']:raise ValueError('payload total')
  return entries,payload

def main():
 p=argparse.ArgumentParser();p.add_argument('--original',type=Path,required=True);p.add_argument('--delta',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 root=Path(__file__).resolve().parents[1];f,quality,scope=frozen_scope(root);qhash=hashlib.sha256(quality).hexdigest()
 first,original=check_archive(a.original,EXPECTED_ORIGINAL,f,qhash)
 second,delta=check_archive(a.delta,EXPECTED_DELTA,f,qhash)
 primary={x['symbol_id']:x for x in f['primary_core']}; reused=set(first)&set(primary);missing=set(second)
 if reused&missing or reused|missing!=set(primary) or reused!=set(primary)-set(f['delta_ids']) or missing!=set(f['delta_ids']):raise ValueError('frozen 17+128 membership mismatch')
 if len(reused)!=17 or len(missing)!=128 or len(first)-len(reused)!=12:raise ValueError('provenance split')
 for sid in reused:
  if first[sid]['series_sha256']!=primary[sid]['reused_authentic_sha256']:raise ValueError('reused hash mismatch')
 rows=sum(first[sid]['row_count'] for sid in reused)+sum(second[sid]['row_count'] for sid in missing)
 if rows!=EXPECTED_ROWS:raise ValueError(f'primary row mismatch {rows} != {EXPECTED_ROWS}')
 doc={'schema':'mxm.research-core-v3.primary-input.v1','frozen_primary_core_sha256':f['sha256'],'economic_outcomes_opened':0,'protected_forward_opened':False,'source_quality_table_sha256':qhash,'original_capture_sha256':EXPECTED_ORIGINAL,'delta_capture_sha256':EXPECTED_DELTA,'primary_count':145,'reused_count':17,'delta_count':128,'total_primary_M5_rows':rows,'primary_series':[first[sid] if sid in reused else second[sid] for sid in sorted(primary)],'supplementary_original_series':[first[sid] for sid in sorted(set(first)-reused)],'supplementary_in_primary_inference':False}
 doc['sha256']=canonical_hash(doc);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n')
 print('ACCEPTED',len(doc['primary_series']),rows,'supplementary',len(doc['supplementary_original_series']),'manifest',doc['sha256'])
if __name__=='__main__':main()
