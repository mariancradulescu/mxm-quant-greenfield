"""One complete batch interpretation of frozen gross DEVELOPMENT response cells."""
from __future__ import annotations
import collections,gzip,hashlib,json,statistics
from pathlib import Path

def canonical(o):return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def load(root,name):
 m=json.loads((root/name).read_text());out=[]
 for sh in m['shards']:
  blob=(root/sh['path']).read_bytes()
  if hashlib.sha256(blob).hexdigest()!=sh['sha256']:raise ValueError('shard hash')
  for s in json.loads(gzip.decompress(blob))['symbols']:out.extend(s['cells'])
 return m,out

def main():
 root=Path(__file__).resolve().parents[1]/'research_core_v3/state'
 base,a=load(root,'BROAD_145_DEVELOPMENT_SURFACE_MANIFEST_V1.json')
 lag,b=load(root,'NEXT_OPEN_GROSS_SENSITIVITY_MANIFEST_V1.json')
 if len(a)!=7975 or len(b)!=7975 or lag['source_surface_sha256']!=base['sha256']:raise ValueError('incomplete linked surface')
 status=[];families=collections.defaultdict(list);strict_symbols=collections.defaultdict(lambda:collections.Counter())
 for i,(o,n) in enumerate(zip(a,b)):
  if (o['symbol_id'],o['mechanism'],o['context'],o['params'])!=(n['symbol_id'],n['mechanism'],n['context'],n['params']):raise ValueError('cell alignment')
  h=o['horizons']['6'];v=n['horizons']['6'];lo=h['uncertainty']['low'];hi=h['uncertainty']['high'];nextlo=v['date_cluster_uncertainty']['low'];nexthi=v['date_cluster_uncertainty']['high']
  gap=o['missingness_sensitivity']['response_sensitivity_by_horizon']['6']['sign_stable'] is True
  thirds=h['chronological_thirds_mean'];neighbors=o['parameter_neighbor_consistency']==1 and o['robust_plateau_width_neighbors']>=2
  positive=(lo is not None and lo>0 and nextlo is not None and nextlo>0 and (h['robust_effect_estimate'] or 0)>0 and gap and len(thirds)==3 and all(x is not None and x>0 for x in thirds) and neighbors)
  negative=(hi is not None and hi<0 and nexthi is not None and nexthi<0 and gap and len(thirds)==3 and all(x is not None and x<0 for x in thirds) and neighbors)
  cls='CONCORDANT_POSITIVE_GROSS_DIAGNOSTIC' if positive else 'CONCORDANT_NONPOSITIVE_GROSS_LOCAL' if negative else 'INCONCLUSIVE_OR_UNSTABLE_GROSS'
  entry={'symbol_id':o['symbol_id'],'symbol':o['symbol'],'mechanism':o['mechanism'],'context':o['context'],'params':o['params'],'class':cls,'event_count':o['event_count'],'date_clusters':o['independent_date_clusters'],'baseline_mean_6':h['mean_response'],'next_open_mean_6':v['mean_response'],'baseline_date_ci_6':h['uncertainty'],'next_open_date_ci_6':v['date_cluster_uncertainty'],'gap_sign_stable':gap,'neighbor_consistency':o['parameter_neighbor_consistency'],'plateau_width_neighbors':o['robust_plateau_width_neighbors']}
  status.append(entry);families[o['mechanism']].append(entry)
  if positive:strict_symbols[o['mechanism']][o['symbol']]+=1
 aggregates={}
 for mech,entries in sorted(families.items()):
  original=[x['baseline_mean_6'] for x in entries if x['baseline_mean_6'] is not None]
  later=[x['next_open_mean_6'] for x in entries if x['next_open_mean_6'] is not None]
  aggregates[mech]={'cells':len(entries),'symbols':len({x['symbol_id'] for x in entries}),'zero_event_cells':sum(x['event_count']==0 for x in entries),'median_baseline_gross_response_6_bps':statistics.median(original)*10000 if original else None,'median_next_open_gross_response_6_bps':statistics.median(later)*10000 if later else None,'unadjusted_date_CI_positive_baseline':sum(x['baseline_date_ci_6']['low'] is not None and x['baseline_date_ci_6']['low']>0 for x in entries),'unadjusted_date_CI_positive_next_open':sum(x['next_open_date_ci_6']['low'] is not None and x['next_open_date_ci_6']['low']>0 for x in entries),'class_counts':dict(collections.Counter(x['class'] for x in entries)),'symbols_with_concordant_positive_gross_diagnostic':len(strict_symbols[mech])}
 full={'schema':'mxm.research-core-v3.complete-batch-development-interpretation.v1','source_surface_sha256':base['sha256'],'next_open_sensitivity_sha256':lag['sha256'],'input_primary_count':145,'cells_classified':7975,'role':'EXPLORATORY_DEVELOPMENT_ONLY','positive_diagnostic_law':'both unadjusted date-cluster 95% intervals above zero; positive baseline median date effect; three positive chronological thirds; 12-bar boundary exclusion preserves sign; every parameter neighbor shares sign and at least two positive neighbors','negative_diagnostic_law':'both unadjusted date-cluster 95% intervals below zero; three negative chronological thirds; 12-bar boundary exclusion preserves sign; every parameter neighbor shares sign and at least two negative neighbors','statistical_limits':['many dependent parameter cells; no familywise multiplicity certification','date-cluster intervals do not prove independent dates','bar-close and next-open calculations lack executable bid/ask spread, commission, slippage and account replay','causal lookback may cross authentic gaps; mechanism-independent gap robustness needs full-lookback boundary check'],'mechanisms':aggregates,'all_cell_diagnostics':status,'next_research_action':'RECHECK_FULL_CAUSAL_LOOKBACK_CONTINUITY_AND_OBTAIN_BROKER_NATIVE_EVENT_TIME_FRICTION_FOR_CONCORDANT_GROSS_REGIONS_BEFORE_FREEZING_ANY_CONFIRMATION_CANDIDATE','protected_forward_opened':False,'final_pnl_certification':False}
 full['sha256']=hashlib.sha256(canonical(full)).hexdigest();blob=gzip.compress(canonical(full),compresslevel=9,mtime=0)
 parts=[]
 for i,chunk in enumerate((blob[:len(blob)//2],blob[len(blob)//2:])):
  path=root/f'BROAD_145_DEVELOPMENT_INTERPRETATION_V1.json.gz.part{i}';path.write_bytes(chunk)
  parts.append({'path':path.name,'sha256':hashlib.sha256(chunk).hexdigest(),'bytes':len(chunk)})
 index={'schema':full['schema'],'source_surface_sha256':base['sha256'],'next_open_sensitivity_sha256':lag['sha256'],'interpretation_uncompressed_sha256':full['sha256'],'interpretation_parts':parts,'interpretation_gzip_sha256':hashlib.sha256(blob).hexdigest(),'primary_count':145,'cells_classified':7975,'mechanisms':aggregates,'next_research_action':full['next_research_action'],'protected_forward_opened':False,'final_pnl_certification':False}
 (root/'BROAD_145_DEVELOPMENT_INTERPRETATION_INDEX_V1.json').write_text(json.dumps(index,sort_keys=True,indent=2)+'\n')
 print('INTERPRETED',full['sha256']);print(json.dumps(aggregates,indent=2))
if __name__=='__main__':main()
