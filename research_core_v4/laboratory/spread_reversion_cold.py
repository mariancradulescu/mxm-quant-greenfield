"""Pinned native result-only custody readback, never a model execution."""
import base64,json,os,subprocess,tempfile
from pathlib import Path
from .common import need,encoded,bytes_digest
NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd'
def cold():
    root=Path(__file__).resolve().parents[2];main=root.parent
    need(os.environ.get('GITHUB_REPOSITORY')=='mariancradulescu/mxm-quant-greenfield' and
      os.environ.get('GITHUB_REF_NAME')=='mxm-remediation-p0-p4-20261015-v1' and os.environ.get('GITHUB_JOB')=='spread-reversion-development' and
      os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_EVENT_NAME')=='push' and
      os.environ.get('GITHUB_WORKFLOW_REF')=='mariancradulescu/mxm-quant-greenfield/.github/workflows/mxm-spread-reversion-development.yml@refs/heads/mxm-remediation-p0-p4-20261015-v1','SPREAD_COLD_CONTEXT')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN','R3_CUSTODY_PRIVATE_KEY_PEM')),'SPREAD_COLD_ROLE_SEPARATION')
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      subprocess.check_output(['git','-C',str(main),'rev-parse','HEAD'],text=True).strip()==os.environ['GITHUB_SHA']==os.environ['GITHUB_WORKFLOW_SHA'] and
      subprocess.run(['git','-C',str(main),'diff','--quiet','HEAD','--']).returncode==0 and
      (root/'research_core_v4/laboratory/spread_reversion_cold.py').read_bytes()==(main/'research_core_v4/laboratory/spread_reversion_cold.py').read_bytes(),'SPREAD_COLD_EXACT_PINNED_CODE')
    folder=main/'verification/spread-reversion-development';r=json.loads((folder/'receipt.json').read_bytes());cipher=(folder/'full-result.mxmenc').read_bytes()
    need(bytes_digest((main/'research_core_v4/laboratory/SPREAD_REVERSION_DEVELOPMENT_V1.json').read_bytes())==r['spec_sha256'] and r['run_id']==int(os.environ['GITHUB_RUN_ID']) and r['source_sha']==os.environ['GITHUB_SHA'] and bytes_digest(cipher)==r['ciphertext_sha256'],'SPREAD_COLD_CIPHER_IDENTITY')
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    with tempfile.TemporaryDirectory() as tmp:
        key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'SPREAD_COLD_EXISTING_CUSTODY')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(tmp)),max_bytes=30000000)
        need(bytes_digest(raw)==r['private_sha256'],'SPREAD_COLD_EXACT_PRIVATE')
        p=strict_json(raw,max_elements=1000000)
        need(p['schema']=='mxm.spread-reversion-development-private.v1' and p['source_sha']==r['source_sha'] and p['spec_sha256']==r['spec_sha256'] and
          p['disposition']==r['disposition'] and p['gates']==r['gates'] and p['every_decision_episode_and_censor_reconciled'] is True and
          p['new_hypotheses']==p['model_trials']==1,'SPREAD_COLD_PRIVATE_PROVENANCE')
        original=base64.b64decode(p['original_csharp_json_b64'],validate=True)
        need(bytes_digest(original)==r['csharp_output_sha256'] and bytes_digest((folder/'evaluator.dll').read_bytes())==r['evaluator_sha256'],'SPREAD_COLD_ORIGINAL_EVALUATOR_AND_OUTPUT')
        for k in ('capital_replay','net_edge_proven','historical_costs_proven','hard21_proven','native_robot_operational_reception_proven'):need(p[k] is False and r[k] is False,'SPREAD_COLD_NO_PROMOTION')
    result={'schema':'mxm.spread-reversion-development-cold.v1','run_id':r['run_id'],'source_sha':r['source_sha'],'spec_sha256':r['spec_sha256'],
      'ciphertext_sha256':r['ciphertext_sha256'],'private_sha256':r['private_sha256'],'evaluator_sha256':r['evaluator_sha256'],
      'separate_custody_process_readback_verified':True,'readback_is_not_independent_algorithm_or_confirmation':True,'orders':0,'new_broker_requests':0,'net_edge_proven':False}
    (folder/'cold.json').write_bytes(encoded(result)+b'\n');print('MXM_SPREAD_COLD '+encoded(result).decode(),flush=True)
if __name__=='__main__':cold()
