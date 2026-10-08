"""Stage7 offline certified-domain software gates; no broker IO."""
import pathlib,sys,json,hashlib
import numpy as np
R=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(R/'research_core_v4/operational_v2'))
from bank import sha
F='research_core_v4/state/STRICT_PREOUTCOME_OPERATIONAL_V2_EXTENDED_STAGE7_IMPLEMENTATION_FREEZE_V1.json';A='research_core_v4/state/STRICT_PREOUTCOME_OPERATIONAL_V2_EXTENDED_STAGE7_AUTHORITY_V1.json'
def check():
 f=json.loads((R/F).read_bytes());a=json.loads((R/A).read_bytes())
 for p,h in f['files_sha256'].items():assert sha(R/p)==h,p
 assert a['stage']==7 and a['extension_implementation_freeze_sha256']==sha(R/F) and a['previous_shared_ready'] is False
 c=json.loads((R/'research_core_v4/state/STRICT_PREOUTCOME_OPERATIONAL_V2_EXTENDED_24_WEEK_CERTIFICATE_V1.json').read_bytes());assert c['all10_pass'] and len(c['cells'])==10 and c['profile']==24 and all(x['pass'] and x['simultaneous_wilson_upper']<=.05 and x['trials']==16384 for x in c['cells'])
 assert c['selected_k']==15 and c['alpha_V2']==15/1024
 from research_core_v4.operational_v2_extended.power_stage7 import run_power
 result=run_power(np.zeros((168,261),bool),'UNSUPPORTED_SOFTWARE_FIXTURE');assert result['score_calendar_days']==168 and not result['shared_ready'] and all(v['trials_executed']==0 for v in result['cases'].values())
 try:run_power(np.zeros((175,261),bool),'OUTSIDE_STAGE7_DOMAIN')
 except AssertionError:pass
 else:raise AssertionError('OUTSIDE_DOMAIN_ACCEPTED')
 old=(R/'research_core_v4/operational_v2/power.py').read_text();new=(R/'research_core_v4/operational_v2_extended/power_stage7.py').read_text();expected=old.replace('D<=140','D<=168').replace("z=p['precision']['wilson_z']","z=4.669289888046892").replace('import numpy as np\n',"import numpy as np\nimport sys\nsys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'research_core_v4/operational_v2'))\n");assert new==expected
 return {'status':'PASS','all_historical_bytes_unchanged':True,'certificate24_frozen_and_all10_pass':True,'exact_only_power_diff':'DOMAIN_GUARD_168_AND_AUTHORIZED_EXPANDED_CONFIDENCE_Z_IMPORT_LOCATION','unsupported168_no_trials':True,'outside175_rejected':True,'no_refinement_authorized':True,'broker_requests':0,'orders':0}
if __name__=='__main__':print(json.dumps(check(),sort_keys=True))
