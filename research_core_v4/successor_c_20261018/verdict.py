"""Disclose only qualitative conclusions already computed in run39126863721.

Never re-runs fetch/cold workflows, science kernels, accounting or experiments.
All private counts, vectors, instruments, times and numerical results stay private.
"""
import base64
import io
import json
import math
import os
from pathlib import Path
import tempfile
import zipfile
from .readback import SUMMARY_SHA,FP,original_encoding,owner_unchanged
from .prepare import require,encoded
from research_core_v4.remediation_p0_p4_20261015.safety import sha,strict_json,unpack

DECISIONS = {'EXPLORATORY_POSITIVE_REQUIRES_UNEXPOSED_CONFIRMATION',
             'NO_ADVANCEMENT_INCOMPLETE_SUPPORT',
             'NO_ADVANCEMENT_NONPOSITIVE_NET_OR_INCREMENT'}
ZIP_SHA = '3d27c250b37e8cdd362e786c45b1874bd82ad519d59bd56054756df6661fe719'
CIPHER_SHA = '62c6711d7526dfdd1dd3052e036608386a02a58af260c1039231c24bc1cef104'
ROOT = Path(__file__).resolve().parents[2]
P = ROOT/'research_core_v4/successor_c_20261018'

def sign_label(value):
    require(value is None or (type(value) in (int,float) and math.isfinite(value)), 'C_VERDICT_NUMBER')
    return 'UNKNOWN' if value is None else 'POSITIVE' if value>0 else 'NEGATIVE' if value<0 else 'ZERO'

def project(a):
    require(a['schema']=='mxm.c-existing-economic-assessment.v1' and
            a['existing_summary_sha256']==SUMMARY_SHA and a['decision'] in DECISIONS,
            'C_VERDICT_IDENTITY')
    require(all(a[k] is False for k in ('campaign_armed','orders_allowed','alpha_certified','HARD21_demonstrated'))
            and a['scientific_recalculations']==0 and a['new_experiment'] is False,'C_VERDICT_SCOPE')
    # Exact allowlist projection: never copy arbitrary private fields into output.
    return {'schema':'mxm.qualitative-existing-economics.v1',
            'original_experiment_run':38288144447,'interpreted_result_run':39126863721,
            'summary_sha256':SUMMARY_SHA,'decision':a['decision'],
            'model_net_after_costs':sign_label(a['complete_net_eur']),
            'matched_increment':{k:sign_label(a['complete_matched_increment_eur'][k])
                                 for k in ('midpoint','quote_count')},
            'evidence_limit':'EXPLORATORY_CURRENT_TERMS_REFERENCE_NOT_HISTORICAL_FILLS_OR_INDEPENDENT_CONFIRMATION',
            'alpha_certified':False,'HARD21_demonstrated':False,'orders_allowed':False,
            'experiment_repeated':False,'private_numeric_values_disclosed':False}

def main():
    require(os.environ.get('GITHUB_REPOSITORY')=='mariancradulescu/mxm-quant-greenfield' and
            os.environ.get('GITHUB_REF_NAME')=='mxm-remediation-p0-p4-20261015-v1' and
            os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
            os.environ.get('GITHUB_JOB')=='qualitative-existing-verdict', 'C_VERDICT_WORKLOAD')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    from research_core_v4.remediation_p0_p4_20261015.owner import bounded_decrypt
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    route=GetOnly();owner_unchanged(route)
    archive=base64.b64decode((P/'READBACK_39126863721.zip.b64').read_text().strip(),validate=True)
    require(sha(archive)==ZIP_SHA,'C_VERDICT_ARCHIVE')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        require(set(z.namelist())=={'economic-readback.mxmenc','public-status.json'},'C_VERDICT_FILES')
        cipher=z.read('economic-readback.mxmenc')
    require(sha(cipher)==CIPHER_SHA,'C_VERDICT_CIPHER')
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as d:
        tmp=Path(d);key,fp=_private_key_from_secret(tmp);require(fp==FP,'C_VERDICT_KEY')
        private=strict_json(unpack(bounded_decrypt(cipher,key,tmp)))
        require(private['schema']=='mxm.c-private-readback.v1' and private['cold_run_id']==39126863721 and
                sha(original_encoding(private['original_summary']))==SUMMARY_SHA,'C_VERDICT_READBACK_BINDING')
        public=project(private['assessment'])
    owner_unchanged(route)
    out=ROOT/'verification/c-qualitative';out.mkdir(parents=True,exist_ok=True)
    (out/'verdict.json').write_bytes(encoded(public))
    print(encoded(public).decode())

if __name__=='__main__':
    try:main()
    except Exception as error:
        import re
        code=str(error) if re.fullmatch(r'C_[A-Z0-9_]+',str(error)) else type(error).__name__
        print(json.dumps({'state':'C_QUALITATIVE_STOP','safe_code':code}));raise SystemExit(1) from None
