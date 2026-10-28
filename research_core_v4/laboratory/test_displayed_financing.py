import json,os,shutil,subprocess,tempfile,unittest
from decimal import Decimal
from pathlib import Path
from .displayed_financing_reference import reference
ROOT=Path(__file__).resolve().parents[2]
PROJECT='research_core_v4/laboratory/csharp/displayed_financing/MxmDisplayedFinancing.csproj'
def row(rate='-1.234567890123456789',kind=0,exp=4):return {'symbol_id':42,'quote_asset':'USD','source_sha256':'a'*64,'full':{'minVolume':'100000','stepVolume':'100000','maxVolume':'1000000','swapCalculationType':kind,'pipPosition':exp,'digits':exp,'swapLong':rate,'swapShort':rate}}
class Compiled(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('dotnet'):
   if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Actual CSharp required')
   raise unittest.SkipTest('CSharp compilation in required CI')
 def check(self,rows):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'in').write_text(json.dumps(rows))
   subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--',str(p/'in'),str(p/'out')],capture_output=True,check=True)
   a=json.loads((p/'out').read_bytes(),parse_float=Decimal);self.assertEqual(a,reference(rows));return a
 def test_signed_pips_points_quantum_and_extreme_nonzero_debit(self):
  for kind in (0,2):
   for rate in ('-1.234567890123456789','1.234567890123456789','0','-0','-1e-300','1e-300','-0.00000000000000001','1e2'):
    self.check([row(rate,kind)])
 def test_missing_fields_never_zero_and_percentage_cash_basis_not_guessed(self):
  for key in ('minVolume','stepVolume','maxVolume','pipPosition','swapLong','swapCalculationType'):
   r=row();del r['full'][key];self.check([r])
  self.check([row('5',1),row('5',99)])
 def test_currency_identity_lattice_and_zero_debit_boundary(self):
  rows=[]
  for asset in (None,'EUR','JPY',''):
   r=row();r['quote_asset']=asset;rows.append(r)
  r=row();r['full']['minVolume']='1';rows.append(r)
  self.check(rows)
 def test_continuous_account_scenario_funding_and_cold_os_processes(self):
  p=subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build'],capture_output=True,check=True)
  a=json.loads(p.stdout);self.assertEqual(a['cold_processes'],3);self.assertFalse(a['market_account_replay']);self.assertEqual(a['orders'],0)
  self.assertEqual(Decimal(str(a['account']['InitialCapitalEur'])),200)
class Scope(unittest.TestCase):
 def test_one_custody_only_no_broker_source_no_closed_screen_or_default_costs(self):
  from . import displayed_financing_reception as n
  self.assertEqual(json.loads((ROOT/n.PATH).read_bytes()),n.workflow())
  self.assertEqual(n.POLICY['new_broker_requests'],0);self.assertEqual(n.POLICY['new_directional_trials'],0)
  self.assertFalse(n.POLICY['closed_screen_reexecuted']);self.assertNotIn('workflow_dispatch',n.workflow()['on'])
  text=json.dumps(n.workflow());self.assertNotIn('R3_CTRADER_',text);self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',text)
  self.assertEqual(n.workflow()['jobs'][n.JOB]['environment'],'mxm-r3-custody-v1')
 def test_wrong_native_context_fails_before_key_or_git(self):
  from . import displayed_financing_reception as n
  from unittest.mock import patch
  with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
   with self.assertRaises(ValueError):n.context(custody=True,native=True)
   git.assert_not_called()
