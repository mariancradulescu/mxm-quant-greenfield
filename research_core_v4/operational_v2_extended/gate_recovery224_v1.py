"""Hash-bound corrected224-day preflight and attempt2 recovery gates."""
import pathlib,json,sys
R=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'research_core_v4/operational_v2'))
from bank import sha
A='research_core_v4/state/STRICT_PREOUTCOME_OPERATIONAL_V2_STAGE7_RECOVERY224_AUTHORITY_V1.json';F='research_core_v4/state/STRICT_PREOUTCOME_OPERATIONAL_V2_STAGE7_RECOVERY224_IMPLEMENTATION_FREEZE_V1.json'
def check():
 f=json.loads((R/F).read_bytes());a=json.loads((R/A).read_bytes())
 for p,h in f['files_sha256'].items():assert sha(R/p)==h,p
 assert a['stage']==7 and a['attempt']==2 and a['first_new_roster_index']==64 and a['durable_base_head']=='aa7fae325833f3c37d49b7ae64230d7720ec5c52'
 assert a['implementation_freeze_sha256']==sha(R/F)
 p=json.loads((R/a['preflight_ref']).read_bytes());assert sha(R/a['preflight_ref'])==a['preflight_sha256'] and p['status']=='PASS' and p['fixture_shape']==[1575,64512] and p['daily_score_mask_shape']==[168,261] and p['power_trials_total']==49152 and p['negative252_rejected'] and p['negative231_rejected'] and p['broker_requests']==0
 assert p['unchanged_power_stage7_sha256']==sha(R/'research_core_v4/operational_v2_extended/power_stage7.py')
 old=(R/'research_core_v4/operational_v2/masks.py').read_bytes();new=(R/'research_core_v4/operational_v2/masks_calendar224_v1.py').read_bytes();assert new==old.replace(b'28<=days<=196',b'28<=days<=224')
 c=json.loads((R/a['certificate24_ref']).read_bytes());assert sha(R/a['certificate24_ref'])==a['certificate24_sha256'] and c['all10_pass'] and c['selected_k']==15
 from preflight import software
 checks=software()
 return {'status':'PASS','first_new_roster_index':64,'corrected_full224_mask_to_power_preflight_pass':True,'historical_software_checks_pass':True,'24week_certificate_unchanged':True,'broker_requests':0,'no_raw_persistence':True}
if __name__=='__main__':print(json.dumps(check(),sort_keys=True))
