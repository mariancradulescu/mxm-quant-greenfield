"""Finite GET-only preservation checks; no write API or historical execution."""
import json
import os
from pathlib import Path
import urllib.request
import urllib.error
from .authority import OWNER_ROOT, ACTIVE_REF, digest, need

REPO='mariancradulescu/mxm-quant-greenfield'
RULES=(25222248,25222426,25231211,25231653,25231978,25232285,25236611,25236786,25268790,25268949)
CALLS=[]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise RuntimeError('READONLY_REDIRECT_DENIED')


def get(path):
    allowed={'rulesets','releases/412686323','git/ref/heads/mxm-o04-active-v1',
             'git/ref/heads/mxm-o04-accepted-owner-1807-v1','git/ref/heads/mxm-o04-stage-authority-v1'}
    allowed.update('rulesets/'+str(i) for i in RULES)
    need(path in allowed,'GET_ALLOWLIST')
    request=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,method='GET',
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=30) as response:
            status=response.status;raw=response.read(4*1024*1024)
    except urllib.error.HTTPError as error:
        status=error.code;raw=error.read(1024*1024)
    CALLS.append({'method':'GET','path':path,'status':status})
    return status,json.loads(raw)


def main():
    need(os.environ['GITHUB_REPOSITORY']==REPO and
         os.environ['GITHUB_REF']=='refs/heads/mxm-remediation-p0-p4-20261015-v1' and
         os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1','WORKFLOW_SCOPE')
    output=Path('verification/p0-supersession');output.mkdir(parents=True,exist_ok=True)
    status,listing=get('rulesets');need(status==200 and {r['id'] for r in listing}==set(RULES),'TEN_RULESETS_ONLY')
    expected=json.loads(Path('docs/p0-failclosed/20261016/NATIVE_RULESETS_AFTER_PROBE.json').read_text())
    details=[];fields=('id','name','target','source','enforcement','conditions','rules')
    for rule in expected:
        status,actual=get('rulesets/'+str(rule['id']));need(status==200,'RULESET_GET')
        need({k:actual[k] for k in fields}=={k:rule[k] for k in fields},'PROTECTION_DRIFT')
        if 'bypass_actors' in actual:need(actual['bypass_actors']==rule['bypass_actors'],'BYPASS_DRIFT')
        details.append(actual)
    status,owner=get('git/ref/heads/mxm-o04-accepted-owner-1807-v1')
    need(status==200 and owner['object']['sha']==OWNER_ROOT[1],'OWNER_REF_DRIFT')
    status,stage=get('git/ref/heads/mxm-o04-stage-authority-v1')
    need(status==200 and stage['object']['sha']=='c6644174244cd92b8e41b17f241b8f5e545fddd9','STAGING_REF_DRIFT')
    status,absent=get('git/ref/heads/mxm-o04-active-v1');need(status==404,'ACTIVE_MUST_REMAIN_ABSENT')
    status,release=get('releases/412686323')
    body_hash=digest(release['body'].encode())
    need(status==200 and body_hash=='01a6d82498c033131302b272ee4ba2f83c4e445f40585f76dfee1a91466679b9','OWNER_BODY_DRIFT')
    files=[p for p in sorted(Path('research_core_v4/p0_supersession_20261016').glob('*.py'))]
    files.append(Path('.github/workflows/mxm-p0-supersession-20261016.yml'))
    value={'schema':'mxm.p0.supersession.live-preservation.v1','source_head':os.environ['GITHUB_SHA'],
        'run_id':os.environ['GITHUB_RUN_ID'],'attempt':1,'calls':CALLS,'writes':0,'rulesets':details,
        'bypass_visibility':'Native runner may omit bypass_actors; complete connector definitions are archived separately.',
        'owner_oid':owner['object']['sha'],'staging_oid':stage['object']['sha'],'active_absent':True,
        'owner_body_sha256':body_hash,'source_sha256':{str(p):digest(p.read_bytes()) for p in files}}
    (output/'live-readonly.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'GET_count':len(CALLS),'writes':0,'owner_1807_unchanged':True,'ten_rulesets_unchanged':True,'active_absent':True}))


if __name__=='__main__':main()
