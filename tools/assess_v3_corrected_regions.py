"""Outcome-informed DEVELOPMENT screening and simultaneous block inference.

No selected region is independent confirmation. Gross cutoffs are operational
screening heuristics, recorded before the corrected results are summarized.
Shared UTC week signs preserve contemporaneous cross-market dependence.
Simultaneous all-cell max-T bounds conservatively cover selected region members;
region evidence is the worst constituent adjusted p, never the best cell.
"""
import gzip,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from research_core_v3.corrected_semantics import VARIANTS,adjacent
from tools.run_v3_broad_surface import sha,canonical
POLICY={'material_mean_response_bps':0.1,'minimum_event_retention':0.5,'minimum_date_support':60,'minimum_week_support':20,'maximum_top10_absolute_concentration':0.5,'chronological_thirds':'ALL_THREE_POSITIVE','minimum_numeric_connected_plateau_cells':3,'familywise_alpha':0.05,'wild_week_resamples':1999,'seed':20260929,'resampling_block_weeks':4,'all_cutoffs_are_outcome_informed_development_screening':True}

def gross(c):
 s=c['variants'][VARIANTS[3]]['horizons']['6']; t=c['variants'][VARIANTS[1]]['horizons']['6']
 checks={'material_corrected_next_open':(s['mean_response'] or 0)>POLICY['material_mean_response_bps']/1e4 and (t['mean_response'] or 0)>POLICY['material_mean_response_bps']/1e4,'positive_robust_effect':(s['robust_effect_estimate'] or 0)>0,'retention':(c['event_retention_fraction'] or 0)>=POLICY['minimum_event_retention'],'dates':s['independent_date_clusters']>=POLICY['minimum_date_support'],'weeks':s['independent_week_clusters']>=POLICY['minimum_week_support'],'chronology':len(s['chronological_thirds'])==3 and all((x or 0)>0 for x in s['chronological_thirds']),'concentration':s['response_concentration_top10_abs_share'] is not None and s['response_concentration_top10_abs_share']<=POLICY['maximum_top10_absolute_concentration']}
 return checks

def main():
 root=Path(__file__).resolve().parents[1];state=root/'research_core_v3/state'
 manifest=json.loads((state/'CORRECTED_145_DEVELOPMENT_MANIFEST_V2.json').read_text());digest=manifest.pop('sha256');assert sha(canonical(manifest))==digest
 spec=json.loads((state/'FROZEN_EXPERIMENT_SPEC_V1.json').read_text());cells=[]
 for shard in manifest['shards']:
  b=(state/shard['path']).read_bytes();assert sha(b)==shard['sha256']
  for s in json.loads(gzip.decompress(b))['symbols']:cells.extend(s['cells'])
 assert len(cells)==7975
 weeks=sorted({w for c in cells for w in c['variants'][VARIANTS[3]]['horizons']['6']['week_cluster_means']});wi={w:i for i,w in enumerate(weeks)}
 matrix=np.zeros((len(weeks),len(cells)));ts=np.full(len(cells),np.inf);valid=np.zeros(len(cells),bool)
 for k,c in enumerate(cells):
  w=c['variants'][VARIANTS[3]]['horizons']['6']['week_cluster_means'];v=np.array(list(w.values()));n=len(v)
  if n<8:continue
  centered=v-v.mean();norm=float(np.linalg.norm(centered))
  if norm<=1e-15:continue
  factor=math.sqrt((n-1)/n);ts[k]=float(v.sum()*factor/norm)
  for day,val in zip(w,centered):matrix[wi[day],k]=val*factor/norm
  valid[k]=True
 rng=np.random.default_rng(POLICY['seed']);maxima=[];counts=np.zeros(len(cells),dtype=int);B=POLICY['wild_week_resamples']
 for start in range(0,B,100):
  n=min(100,B-start);blocks=rng.choice([-1.,1.],size=(n,math.ceil(len(weeks)/4)));signs=np.repeat(blocks,4,axis=1)[:,:len(weeks)];boot=signs@matrix
  maxima.extend(np.maximum(0,boot[:,valid].max(axis=1)).tolist());counts+=(boot>=ts).sum(axis=0)
 maxima=np.array(maxima)
 for k,c in enumerate(cells):
  c['gross_screen']=gross(c)
  c['inference']={'method':'SHARED_4_UTC_WEEK_BLOCK_WILD_SIGN_ALL_CELL_MAX_T_REGION_INTERSECTION','t':float(ts[k]) if valid[k] else None,'p_unadjusted':float((1+counts[k])/(B+1)) if valid[k] else None,'p_familywise':float((1+np.count_nonzero(maxima>=ts[k]))/(B+1)) if valid[k] else None,'eligible':bool(valid[k]),'assumptions':'asymptotic 4-week block approximation; dependence beyond four weeks can remain; DEVELOPMENT only'}
 groups=defaultdict(list)
 for k,c in enumerate(cells):groups[(c['symbol_id'],c['mechanism'],json.dumps(c['context'],sort_keys=True))].append(k)
 regions=[]
 for key,ids in groups.items():
  grid=next(m['parameter_grid'] for m in spec['mechanisms'] if m['name']==key[1]);passing={i for i in ids if all(cells[i]['gross_screen'].values())}
  while passing:
   initial=min(passing);component={initial};stack=[initial];passing.remove(initial)
   while stack:
    i=stack.pop();neighbors=[j for j in sorted(passing) if adjacent(cells[i]['params'],cells[j]['params'],grid)]
    for j in neighbors:passing.remove(j);component.add(j);stack.append(j)
   if len(component)<POLICY['minimum_numeric_connected_plateau_cells']:continue
   members=[cells[i] for i in sorted(component)];identity={'symbol':members[0]['symbol'],'symbol_id':key[0],'mechanism':key[1],'context':members[0]['context'],'parameters':[c['params'] for c in members],'source_corrected_surface_sha256':digest,'timing':'signal close[i], entry open[i+1], exit close[i+h]','continuity':'EXACT_FULL_BACKWARD_UNION_AND_CONTIGUOUS_FORWARD'}
   adjusted=[c['inference']['p_familywise'] for c in members];unadjusted=[c['inference']['p_unadjusted'] for c in members]
   region={**identity,'region_sha256':sha(canonical(identity)),'plateau_cell_count':len(members),'parameter_plateau_axis_widths':{axis:len({json.dumps(c['params'][axis],sort_keys=True) for c in members}) for axis in grid},'constituent_cell_indices':sorted(component),'minimum_mean_response_bps':min(c['variants'][VARIANTS[3]]['horizons']['6']['mean_response']*1e4 for c in members),'p_unadjusted_region_intersection':max(unadjusted) if all(p is not None for p in unadjusted) else None,'p_familywise_region_intersection':max(adjusted) if all(p is not None for p in adjusted) else None,'friction_status':'COST_UNRESOLVED','net_margin_bps':None,'candidate_frozen':False}
   region['multiplicity_screen_pass']=region['p_familywise_region_intersection'] is not None and region['p_familywise_region_intersection']<=POLICY['familywise_alpha'];regions.append(region)
 summary={}
 for mech in [m['name'] for m in spec['mechanisms']]:
  group=[c for c in cells if c['mechanism']==mech];med=lambda xs:float(np.median(xs)) if xs else None
  summary[mech]={'cells':len(group),'median_event_retention':med([c['event_retention_fraction'] for c in group if c['event_retention_fraction'] is not None]),'original_events':sum(c['original_event_count'] for c in group),'strict_events':sum(c['strict_dependency_event_count'] for c in group),'event_counts_overlap_across_cells':True,'median_mean_response_6_bps_by_variant':{v:med([c['variants'][v]['horizons']['6']['mean_response']*1e4 for c in group if c['variants'][v]['horizons']['6']['mean_response'] is not None]) for v in VARIANTS},'median_timing_effect_delta_bps':med([c['effects']['6']['timing_effect_delta']*1e4 for c in group if c['effects']['6']['timing_effect_delta'] is not None]),'gross_screen_cells':sum(all(c['gross_screen'].values()) for c in group),'robust_regions':sum(r['mechanism']==mech for r in regions),'robust_region_symbols':len({r['symbol_id'] for r in regions if r['mechanism']==mech}),'multiplicity_pass_regions':sum(r['mechanism']==mech and r['multiplicity_screen_pass'] for r in regions)}
 assessment={'schema':'mxm.research-core-v3.corrected-region-assessment.v2','source_corrected_surface_sha256':digest,'screening_policy':POLICY,'inference_family':'ALL_7975_FROZEN_PRIMARY_HORIZON_CELLS;SIMULTANEOUS_BOUNDS_FOR_DATA_SELECTED_REGIONS','week_count':len(weeks),'adjacency':'IMMEDIATE_NUMERIC_GRID_NEIGHBOR_WITHIN_EXACT_SYMBOL_MECHANISM_CONTEXT;CATEGORICAL_AXES_DISCONNECTED','mechanisms':summary,'regions':regions,'robust_region_count':len(regions),'robust_symbol_count':len({r['symbol_id'] for r in regions}),'gross_survivor_counts_by_symbol':dict(Counter(r['symbol'] for r in regions)),'friction_resolved_regions':0,'COST_UNRESOLVED_regions':len(regions),'net_surviving_regions':0,'net_surviving_regions_interpretation':'NONE_CERTIFIED;UNRESOLVED_IS_NOT_NET_NULL','frozen_candidates':[],'disjoint_confirmation_ready':False,'protected_forward_opened':False,'sizing_scaling_optimization_opened':False,'next_stage':'AUTHENTIC_EVENT_TIME_FRICTION_FOR_GROSS_REGIONS_ONLY','continuous_account_requirements_preserved':{'starting_equity_eur':200,'one_continuous_account':True,'scale_up':True,'de_scale':True,'equity_dependent_executable_universe':True,'risk_min_volume_reject':True,'final_bot':'ONE_SELF_CONTAINED_CSHARP_CTRADER_CLOUD','production_optimization_stage':'AFTER_CONFIRMED_EDGE','live':'BLOCKED_PENDING_EXPLICIT_APPROVAL_AFTER_FINAL_DEMO'}}
 # Save every cell assessment, including all failures, before interpreting.
 blob=gzip.compress(canonical({'source_corrected_surface_sha256':digest,'cells':[{'symbol_id':c['symbol_id'],'mechanism':c['mechanism'],'params':c['params'],'context':c['context'],'gross_screen':c['gross_screen'],'inference':c['inference']} for c in cells]}),mtime=0);(state/'CORRECTED_ALL_CELL_ASSESSMENT_V2.json.gz').write_bytes(blob);assessment['all_cell_assessment_sha256']=sha(blob)
 assessment['sha256']=sha(canonical(assessment));(state/'CORRECTED_REGION_ASSESSMENT_V2.json').write_text(json.dumps(assessment,sort_keys=True,indent=2)+'\n');print(json.dumps({'sha256':assessment['sha256'],'mechanisms':summary,'regions':len(regions),'symbols':assessment['robust_symbol_count'],'multiplicity_pass':sum(r['multiplicity_screen_pass'] for r in regions)},indent=2))
if __name__=='__main__':main()
