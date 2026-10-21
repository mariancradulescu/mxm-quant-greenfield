"""Finite native access check using the existing isolated Pepperstone role.

Three existing VIEW authentication requests only. No historical collection,
economic work, credential update, custody key or evidence-plane publisher.
"""
import json,os,re,subprocess
from pathlib import Path
from .common import need,encoded
from .runtime import module_digest,SOURCE_BRANCH
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json

ENGINE='dbd0a42bf73f9ae5847a90a4ed159d21e0d7197a'
ENGINE_MODULE='1ae2c01634358007de8d079941022533980c47d9b55b1285854c9d3ef841be10'
REPO='mariancradulescu/mxm-quant-greenfield'
BRANCH='mxm-remediation-p0-p4-20261015-v1'
PATH='.github/workflows/mxm-r3-pepperstone-access-reception.yml'
AUTH_TYPES=('ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq','ProtoOAAccountAuthReq')
SECRET_NAMES=('R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_ACCESS_TOKEN')

def build_workflow(source):
    need(type(source) is str and re.fullmatch('[a-f0-9]{40}',source),'BROKER_ACCESS_SOURCE')
    return {'name':'MXM R3 Pepperstone access reception','on':{'workflow_dispatch':{}},
        'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},
        'jobs':{'pepperstone-access':{'if':"github.repository == '"+REPO+"' && github.ref == 'refs/heads/"+BRANCH+"' && github.run_attempt == 1",
            'runs-on':'ubuntu-24.04','timeout-minutes':5,'environment':'mxm-r3-pepperstone-v1',
            'permissions':{'contents':'read'},'steps':[
                {'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
                 'with':{'ref':source,'persist-credentials':False}},
                {'run':'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock'},
                {'name':'Existing isolated Pepperstone VIEW authentication only',
                 'run':'python3 -m research_core_v4.laboratory.broker_access_reception',
                 'env':{'GH_TOKEN':'${{ github.token }}','LAB_BROKER_ACCESS_SOURCE':source,
                        **{key:'${{ secrets.'+key+' }}' for key in SECRET_NAMES}}},
                {'uses':'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02',
                 'if':'always()','with':{'name':'r3-pepperstone-access-${{ github.run_id }}',
                    'path':'verification/r3-pepperstone-access/report.json','if-no-files-found':'error'}}]}}}

def context(route):
    source=os.environ.get('LAB_BROKER_ACCESS_SOURCE','');trigger=os.environ.get('GITHUB_SHA','')
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
         os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
         os.environ.get('GITHUB_JOB')=='pepperstone-access' and os.environ.get('GITHUB_WORKFLOW_SHA')==trigger and
         os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH and
         re.fullmatch('[a-f0-9]{40}',source) and re.fullmatch('[a-f0-9]{40}',trigger),'BROKER_ACCESS_NATIVE_CONTEXT')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CUSTODY_PRIVATE_KEY_PEM',
         'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN',
         'R3_CTRADER_REFRESH_TOKEN')),'BROKER_ACCESS_CREDENTIAL_SEPARATION')
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==source and
         subprocess.run(['git','diff','--quiet','HEAD','--'],capture_output=True).returncode==0 and
         module_digest()==ENGINE_MODULE,'BROKER_ACCESS_UNMODIFIED_SOURCE')
    need(route.json('git/ref/heads/'+SOURCE_BRANCH)['object']['sha']==ENGINE and
         route.json('git/ref/heads/'+BRANCH)['object']['sha']==trigger,'BROKER_ACCESS_REF_MOVED')
    from .runtime import file_at
    need(strict_json(file_at(route,PATH,trigger))==build_workflow(source),'BROKER_ACCESS_WORKFLOW')
    return {'source_sha':source,'engine_source_sha':ENGINE,'trigger_sha':trigger,
            'run_id':int(os.environ['GITHUB_RUN_ID']),'attempt':1}

def authenticate_only(transport,values):
    """Wrap the existing authentication, denying every other wire request."""
    from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,_fingerprint,ACCOUNT_FINGERPRINT_SHA256
    requests=[]
    class AuthOnly:
        def request(self,request,**kw):
            name=type(request).__name__
            need(len(requests)<len(AUTH_TYPES) and name==AUTH_TYPES[len(requests)],'BROKER_ACCESS_AUTH_REQUEST_ONLY')
            requests.append(name)
            return transport.request(request,**kw)
    try:
        transport.connect()
        account=authenticate_segment(AuthOnly(),*values)
        need(tuple(requests)==AUTH_TYPES and _fingerprint(account)==ACCOUNT_FINGERPRINT_SHA256,'BROKER_ACCESS_AUTH_INCOMPLETE')
        return {'authenticated':True,'explicit_scope':'VIEW','expected_account_fingerprint_verified':True,
                'live_account_verified':True,'wire_requests':requests,'historical_requests':0,'orders':0,
                'new_economic_outcomes':0,'research_capability_accepted':False}
    finally:transport.close()

def main():
    report={'schema':'mxm.pepperstone-native-access-reception.v1','accepted':False,
            'historical_requests':0,'orders':0,'new_economic_outcomes':0,'research_capability_accepted':False}
    output=Path('verification/r3-pepperstone-access/report.json');output.parent.mkdir(parents=True,exist_ok=True)
    stage='NATIVE_CONTEXT'
    try:
        report.update(context(GetOnly()));stage='CREDENTIAL_PRESENCE'
        need(all(os.environ.get(k) for k in SECRET_NAMES),'BROKER_ACCESS_EXISTING_CREDENTIAL_REQUIRED')
        values=tuple(os.environ.pop(k) for k in SECRET_NAMES);stage='NATIVE_VIEW_AUTHENTICATION'
        from m6.ctrader_transport import StdlibCTraderTransport
        report.update(authenticate_only(StdlibCTraderTransport(),values));values=None
        report['accepted']=True
    except Exception as error:
        # Do not serialize arbitrary provider responses, account IDs or secrets.
        report.update(failure_stage=stage,failure_class=type(error).__name__)
        if type(error).__name__ in ('SystemicFailure','LabError'):
            code=str(error)
            if re.fullmatch('[A-Z][A-Z0-9_]{2,100}',code):report['failure_code']=code
    finally:
        values=None
        for key in SECRET_NAMES:os.environ.pop(key,None)
        output.write_bytes(encoded(report));print('MXM_PEPPERSTONE_ACCESS '+json.dumps(report,sort_keys=True),flush=True)
    return 0 if report['accepted'] else 1

if __name__=='__main__':raise SystemExit(main())
