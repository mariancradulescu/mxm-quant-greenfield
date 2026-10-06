"""Verify one exact parent/head-bound auth-only arm BEFORE any credential use."""
import hashlib,json,subprocess
from pathlib import Path
ARM=Path('adaptive_competition/state/READ_ONLY_AUTH_PREFLIGHT_ARM_V3.json')
def git(*args):return subprocess.check_output(['git',*args]).decode().strip()
def verify_arm():
 from .read_only_auth_preflight_v3 import EXPECTED_FINGERPRINT,ALLOWED
 a=json.loads(ARM.read_text());assert a['accounts_only'] and all(a[k] is False for k in ('orders','market_history','refresh','subscriptions','account_mutation'))
 assert a['expected_account_fingerprint_sha256']==EXPECTED_FINGERPRINT
 assert set(a['allowed_broker_messages'])==ALLOWED
 assert a['broker_text_used_as_identity_or_region_gate'] is False
 from .read_only_auth_preflight_v3 import require_identity_authority
 require_identity_authority(EXPECTED_FINGERPRINT)
 assert git('rev-parse','HEAD^')==a['exact_source_head']
 assert git('diff','--name-only',a['exact_source_head'],'HEAD').splitlines()==[str(ARM)]
 for p,h in a['implementation_hashes'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
 assert a['implementation_sha256']==a['implementation_hashes']['adaptive_competition/read_only_auth_preflight_v3.py']
 assert a['workflow_sha256']==a['implementation_hashes']['.github/workflows/adaptive-read-only-auth-preflight-v2.yml']
 print('PASS_EXACT_AUTH_ONLY_V3_ARM_WITHOUT_CREDENTIALS')
 return a
if __name__=='__main__':verify_arm()
