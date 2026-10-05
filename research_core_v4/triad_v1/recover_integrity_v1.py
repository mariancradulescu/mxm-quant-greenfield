"""Accepted archive byte recovery; no price parsing or response calculation."""
import json,pathlib,hashlib,zipfile,sys
R=pathlib.Path('.');B=R/'research_core_v4/triad_v1';A=pathlib.Path(sys.argv[1]);O=pathlib.Path(sys.argv[2]);O.mkdir(parents=True,exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads((R/p).read_bytes())
m=read('research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json');c=read('research_core_v3/state/INCLUSIVE_FULL_DEPTH_DISCOVERY_CORE_V1.json');fx=[x for x in c['primary_core'] if x['asset_class']=='Forex (Spot)'];assert len(fx)==75
ids={x['symbol_id'] for x in fx};rows=[x for x in m['primary_series'] if x['symbol_id'] in ids];assert len(rows)==75
names={'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip':m['original_capture_sha256'],'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip':m['delta_capture_sha256']}
archives=[];sources={};results=[]
for name,want in names.items():
 p=A/name;have=sha(p.read_bytes()) if p.exists() else None;ok=have==want;archives.append({'filename':name,'expected_sha256':want,'observed_sha256':have,'size_bytes':p.stat().st_size if p.exists() else None,'status':'HASH_VERIFIED' if ok else 'UNAVAILABLE_OR_HASH_MISMATCH'})
 if ok:
  z=zipfile.ZipFile(p);nn=z.namelist();assert len(nn)==len(set(nn)), 'duplicate archive entries';sources[want]=z
for x in rows:
 z=sources.get(x['source_archive_sha256']);data=z.read(x['file']) if z and x['file'] in z.namelist() else None;have=sha(data) if data else None;ok=have==x['series_sha256'];res={**x,'observed_series_sha256':have,'recovered':ok,'status':'ACCEPTED_BYTES_VERIFIED' if ok else 'UNAVAILABLE_OR_HASH_MISMATCH'}
 if ok:(O/(str(x['symbol_id'])+'_M5.csv')).write_bytes(data)
 results.append(res)
for z in sources.values():z.close()
bind={p:sha((R/p).read_bytes()) for p in ['research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json','research_core_v3/state/INCLUSIVE_FULL_DEPTH_DISCOVERY_CORE_V1.json','research_core_v4/state/V4_DISCOVERY_PROTOCOL_V2.json','research_core_v4/state/NEXT_INFORMATION_SOURCE_SELECTION_V6.json']}
out={'schema':'mxm.v4.triad.accepted-archive-integrity.v1','starting_head':'d118b4f836abb8f7a76c85149d95a696d446f828','archives':archives,'series':results,'expected_FX_series':75,'verified_recovered_series':sum(x['recovered'] for x in results),'all75_recovered':all(x['recovered'] for x in results),'bindings':bind,'price_fields_parsed':False,'future_signed_response_computations':0,'broker_contacts':0,'historical_requests':0,'new_data_acquisition':0,'development_not_confirmation':True,'unavailable_is_infrastructure_not_economic_null':True}
(B/'ACCEPTED_FX_ARCHIVE_RECOVERY_LEDGER_V1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'archives':archives,'verified':out['verified_recovered_series'],'all75':out['all75_recovered']}))
