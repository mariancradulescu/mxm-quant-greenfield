"""Read-only live authority evidence. No private key or broker access."""
import hashlib
import json
import os
import pathlib
import urllib.error
import urllib.request

REPO='mariancradulescu/mxm-quant-greenfield'
PATHS=(
    'branches/performance-research-v3-20260922/protection',
    'branches/mxm-autonomous-native-20261015-v1/protection',
    'branches/mxm-remediation-p0-p4-20261015-v1/protection',
    'rulesets?includes_parents=true',
    'actions/permissions', 'actions/permissions/workflow', 'keys',
    'installation', 'collaborators?affiliation=all&per_page=100',
    'releases/412686323',
    'git/ref/heads/performance-research-v3-20260922',
    'git/ref/heads/mxm-autonomous-native-20261015-v1',
)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):
        return None

def probe():
    opener=urllib.request.build_opener(NoRedirect())
    result=[]
    for path in PATHS:
        req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
            headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],
                'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},method='GET')
        try:
            with opener.open(req,timeout=20) as response:
                raw=response.read(4*1024*1024+1)
                if len(raw)>4*1024*1024:raise ValueError('PROBE_RESPONSE_LIMIT')
                data=json.loads(raw);status=response.status
            row={'path':path,'status':status,'response_sha256':hashlib.sha256(raw).hexdigest()}
            if path=='releases/412686323':
                body=json.loads(data['body'])
                row.update(body_sha256=hashlib.sha256(data['body'].encode()).hexdigest(),generation=body['generation'],state=body['state'],journal_sha256=body['current_journal']['canonical_sha256'])
                assert row['generation']==1807 and row['state']=='STOP_FAIL_CLOSED'
                assert row['journal_sha256']=='ea93f6c38768824521d4ad3e316c0cd507c837e5c089c5e3b6f63d20d79e7470'
            elif path.startswith('git/ref/'):
                row['oid']=data['object']['sha']
            elif path.startswith('actions/permissions'):
                row['policy']=data
            elif path.startswith('rulesets'):
                row['count']=len(data)
            # Never emit deploy key material, collaborator identities or tokens.
        except urllib.error.HTTPError as exc:
            row={'path':path,'status':exc.code,'state':'ACCESS_UNVERIFIED' if exc.code in (403,404) else 'HTTP_READ_FAILED'}
        result.append(row)
    out=pathlib.Path('verification');out.mkdir(exist_ok=True)
    summary={'schema':'mxm.o04.readonly-rights.v1','head':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),
        'HTTP_methods':['GET'],'results':result,'production_mutations':0,'O04.1':'NO_GO_GLOBAL_AUTHORITY_UNVERIFIED'}
    (out/'o04-rights.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,sort_keys=True))

if __name__=='__main__':probe()
