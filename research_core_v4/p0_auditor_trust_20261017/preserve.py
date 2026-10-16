"""Five GET preservation observations only. No private material or admin writes."""
import json
import os
from pathlib import Path
import urllib.request
import urllib.error
from .public_verifier import need,sha,ROOT_OID


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise RuntimeError('REDIRECT_DENIED')


def main():
    paths=('rulesets','rulesets/25268790','git/ref/heads/mxm-o04-accepted-owner-1807-v1',
           'git/ref/heads/mxm-o04-stage-authority-v1','git/ref/heads/mxm-o04-active-v1')
    observations={};calls=[]
    for path in paths:
        req=urllib.request.Request('https://api.github.com/repos/mariancradulescu/mxm-quant-greenfield/'+path,
            method='GET',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
        try:
            with urllib.request.build_opener(NoRedirect).open(req,timeout=30) as res:status=res.status;raw=res.read(2*1024*1024)
        except urllib.error.HTTPError as err:status=err.code;raw=err.read(1024*1024)
        observations[path]=json.loads(raw);calls.append({'method':'GET','path':path,'status':status})
        need(status==(404 if path.endswith('mxm-o04-active-v1') else 200),'PRESERVATION_GET')
    expected=json.loads(Path('docs/p0-failclosed/20261016/NATIVE_RULESETS_AFTER_PROBE.json').read_text())
    need({r['id'] for r in observations['rulesets']}=={r['id'] for r in expected},'TEN_RULESETS')
    rule=observations['rulesets/25268790'];old=next(r for r in expected if r['id']==25268790)
    for field in ('id','enforcement','conditions','rules'):need(rule[field]==old[field],'RULE_DRIFT')
    if 'bypass_actors' in rule:need(rule['bypass_actors']==[],'BYPASS_DRIFT')
    need(observations['git/ref/heads/mxm-o04-accepted-owner-1807-v1']['object']['sha']==ROOT_OID,'OWNER_DRIFT')
    need(observations['git/ref/heads/mxm-o04-stage-authority-v1']['object']['sha']=='c6644174244cd92b8e41b17f241b8f5e545fddd9','STAGING_DRIFT')
    registry=Path('docs/continuity/20261016/P0_P4_REGISTRY.json').read_bytes()
    need(sha(registry)=='17eebd55b50bd8f4b935e2eb2532ee34ee4fd7dd6f2f2de2c9f1ef54b89b84ad','REGISTRY_DRIFT')
    files=list(sorted(Path('research_core_v4/p0_auditor_trust_20261017').glob('*.py')))+[
        Path('research_core_v4/p0_auditor_trust_20261017/real.disabled.json'),
        Path('.github/workflows/mxm-p0-auditor-trust-20261017.yml')]
    out=Path('verification/p0-auditor-trust');out.mkdir(parents=True,exist_ok=True)
    (out/'preservation.json').write_text(json.dumps({'schema':'mxm.auditor-trust.preservation.v1',
        'source_sha':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],'calls':calls,
        'observations':observations,'writes':0,'registry_sha256':sha(registry),
        'source_sha256':{str(p):sha(p.read_bytes()) for p in files},
        'scope':'Five narrow GETs, not a repeat administrative audit; full25268790 bypass is corroborated by connector.'},indent=2)+'\n')
    print(json.dumps({'GETs':5,'writes':0,'owner_staging_preserved':True,'active_absent':True,'registry_163_PASS_28_BLOCKED':True}))


if __name__=='__main__':main()
