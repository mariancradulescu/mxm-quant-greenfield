"""Full1575x224 Boolean-domain to unchanged Stage7 power; no market IO."""
import hashlib,json,pathlib,sys,socket,time,shutil
import numpy as np
R=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'research_core_v4/operational_v2'))
from bank import canonical,sha
from preflight import software
from research_core_v4.operational_v2.masks_calendar224_v1 import derive,ROSTER
from research_core_v4.operational_v2 import masks as historical
from research_core_v4.operational_v2_extended.power_stage7 import run_power
S='research_core_v4/state/';PLAN=S+'STRICT_PREOUTCOME_OPERATIONAL_V2_STAGE7_RECOVERY224_PREFLIGHT_PLAN_V1.json'
def main():
 p=json.loads((R/PLAN).read_bytes())
 for path,h in p['files_sha256'].items():assert sha(R/path)==h,path
 old=(R/'research_core_v4/operational_v2/masks.py').read_bytes();new=(R/'research_core_v4/operational_v2/masks_calendar224_v1.py').read_bytes();assert new==old.replace(b'28<=days<=196',b'28<=days<=224') and old.count(b'28<=days<=196')==1
 roster=json.loads((R/ROSTER).read_bytes())['entries'];assert len(roster)==1575
 def deny(*a,**k):raise RuntimeError('OFFLINE_PREFLIGHT_NO_NETWORK_OR_BROKER')
 socket.socket=deny;socket.create_connection=deny;socket.getaddrinfo=deny
 begin=time.monotonic();checks=software();out=R/'recovery224_preflight_output';out.mkdir(exist_ok=True);start=1760572800
 for days in [231,252]:
  try:derive(np.broadcast_to(np.zeros((1575,1),np.uint8),(1575,days*288)),roster,start,out/'negative')
  except AssertionError:pass
  else:raise AssertionError('DOMAIN_ABOVE224_ACCEPTED')
 # Differential existing28-day fixture with actual roster/context inventory.
 fixture=np.full((1575,8064),31,np.uint8);fixture[:,::97]=0
 d0,g0=historical.derive(fixture,roster,start,out/'old28');d1,g1=derive(fixture,roster,start,out/'new28');assert np.array_equal(d0,d1) and g0==g1
 for name in ['event_masks.npz','support_counts.npz']:
  with np.load(out/'old28'/name) as a,np.load(out/'new28'/name) as b:
   assert a.files==b.files
   for key in a.files:assert np.array_equal(a[key],b[key]),key
 print('EARLIER_FIXTURES_AND_28_DAY_DIFFERENTIAL_PASS',flush=True);fixture=None
 bits=np.full((1575,64512),31,np.uint8);fixture_hash=hashlib.sha256(bits.tobytes()).hexdigest();print('BEGIN_FULL224_MASK_DERIVE',flush=True)
 daily,geometry=derive(bits,roster,start,out/'full224');assert daily.shape==(168,261) and daily.dtype==bool and geometry['calendar_days']==224 and geometry['identities']==1575;bits=None
 print('FULL224_MASK_SHAPE168x261_PASS_BEGIN_UNCHANGED_POWER',flush=True);gh=sha(out/'full224/geometry.json');power=run_power(daily,gh)
 assert power['score_calendar_days']==168 and power['paid_leaves']==261 and power['selected_k']==15 and power['alpha_V2']==15/1024 and power['real_inputs']==0 and all(c['trials_executed']==16384 for c in power['cases'].values())
 (out/'synthetic_fixture_power.json').write_bytes(canonical(power))
 result={'schema':'mxm.operational-v2.stage7-full224-preflight-result.v1','status':'PASS','plan_sha256':sha(R/PLAN),'mask_successor_sha256':sha(R/'research_core_v4/operational_v2/masks_calendar224_v1.py'),'unchanged_power_stage7_sha256':sha(R/'research_core_v4/operational_v2_extended/power_stage7.py'),'fixture_law':'ALL31_BOOLEAN_FLAGS_FULL1575_ROSTER; deterministic isolated gaps only in28day differential','fixture_shape':[1575,64512],'fixture_sha256':fixture_hash,'daily_score_mask_shape':list(daily.shape),'daily_score_mask_sha256':hashlib.sha256(daily.tobytes()).hexdigest(),'geometry_sha256':gh,'power_fixture_result_sha256':sha(out/'synthetic_fixture_power.json'),'power_trials_per_stress':16384,'power_trials_total':49152,'power_result_not_market_certificate':True,'fixture_result_has_no_decision_authority':True,'no_power_pass_required_for_preflight':'Only successful exact full route execution and dimensions; synthetic sharedready does not authorize broker or alter schedule.','old_software_checks':checks,'all_earlier_software_fixtures_pass':True,'mask28_differential_all_arrays_equal':True,'mask_algorithm_only_guard_diff':True,'negative231_rejected':True,'negative252_rejected':True,'broker_requests':0,'real_inputs':0,'orders':0,'protected_forward_opened':False,'confirmation_opened':False,'seconds':time.monotonic()-begin}
 path=R/S/'STRICT_PREOUTCOME_OPERATIONAL_V2_STAGE7_RECOVERY224_END_TO_END_PREFLIGHT_RESULT_V1.json';path.write_bytes(canonical(result));print('RECOVERY224_PREFLIGHT_RESULT='+json.dumps(result,sort_keys=True),flush=True)
if __name__=='__main__':main()
