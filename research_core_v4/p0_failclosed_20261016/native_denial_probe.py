"""One POST, only to the pre-protected isolated SYNTHETIC ref. No retries.

No App/environment/OWNER credentials. Normal workflow GITHUB_TOKEN only.
Never attempts a write to active, staging, accepted OWNER or historic refs.
"""
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import urllib.error

REPO = 'mariancradulescu/mxm-quant-greenfield'
SYNTH = 'refs/heads/mxm-o04-synthetic-deny-20261016-v1'
ACTIVE = 'refs/heads/mxm-o04-active-v1'
CANDIDATE = 'a13d7b0d9005ec175e3c2851ee06c956e58a9e63'
OWNER = 'a830c132521bd4348454653f713e04f6107484fe'
STAGE = 'c6644174244cd92b8e41b17f241b8f5e545fddd9'
IDS = [25222248,25222426,25231211,25231653,25231978,25232285,25236611,25236786,25268790,25268949]
OUT = Path('failclosed-verification'); OUT.mkdir(exist_ok=True)
CALLS = []


def need(value, code):
    if not value: raise RuntimeError(code)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): raise RuntimeError('REDIRECT_DENIED')


def request(path, method='GET', payload=None):
    need(method == 'GET' or (method == 'POST' and path == 'git/refs' and
         payload == {'ref': SYNTH, 'sha': CANDIDATE} and
         not any(c['method'] != 'GET' for c in CALLS)), 'WRITE_NAMESPACE_DENIED')
    req = urllib.request.Request('https://api.github.com/repos/' + REPO + '/' + path,
        data=None if payload is None else json.dumps(payload).encode(), method=method,
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json',
                 'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28'})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as response:
            status=response.status; raw=response.read(4*1024*1024)
    except urllib.error.HTTPError as error:
        status=error.code; raw=error.read(1024*1024)
    data=json.loads(raw)
    CALLS.append({'method':method,'path':path,'status':status})
    return status,data


def get(path):
    status,data=request(path); need(status == 200, 'GET_FAILED_' + str(status)); return data


def snapshot():
    owner=get('git/ref/heads/mxm-o04-accepted-owner-1807-v1')['object']['sha']
    stage=get('git/ref/heads/mxm-o04-stage-authority-v1')['object']['sha']
    need(owner == OWNER and stage == STAGE, 'ACCEPTED_REF_DRIFT')
    for ref in (SYNTH, ACTIVE):
        status,_=request('git/ref/' + ref.removeprefix('refs/'))
        need(status == 404, 'REF_MUST_REMAIN_ABSENT')
    body=get('releases/412686323')['body']
    need(hashlib.sha256(body.encode()).hexdigest() == '01a6d82498c033131302b272ee4ba2f83c4e445f40585f76dfee1a91466679b9', 'OWNER_BODY_DRIFT')
    rules=[get('rulesets/' + str(i)) for i in IDS]
    fields=('id','name','target','source','enforcement','conditions','rules')
    expected=json.loads(Path('docs/p0-failclosed/20261016/NATIVE_RULESETS_BEFORE_PROBE.json').read_text())
    need([{k:r[k] for k in fields} for r in rules] == [{k:r[k] for k in fields} for r in expected], 'RULESET_DRIFT')
    return {'owner_oid':owner,'staging_oid':stage,'owner_release_body_sha256':hashlib.sha256(body.encode()).hexdigest(),
            'active_absent':True,'synthetic_absent':True,'rulesets':rules}


def main():
    need(os.environ['GITHUB_REPOSITORY']==REPO and os.environ['GITHUB_REF']=='refs/heads/mxm-remediation-p0-p4-20261015-v1'
         and os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1', 'EXECUTION_SCOPE')
    before=snapshot()
    candidate=get('git/commits/' + CANDIDATE)
    tree=get('git/trees/' + candidate['tree']['sha'])['tree']
    need(len(tree)==1 and tree[0]['path']=='SYNTHETIC_ONLY.json' and tree[0]['type']=='blob', 'SYNTHETIC_CANDIDATE_TREE')
    status,rejection=request('git/refs','POST',{'ref':SYNTH,'sha':CANDIDATE})
    # Always obtain post-observation before interpreting the rejection.
    after=snapshot()
    (OUT/'native-receipt.json').write_text(json.dumps({'schema':'mxm.p0.native-denial.v1',
        'source_head':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],
        'attempt':1,'candidate_oid':CANDIDATE,'tested_ref':SYNTH,'before':before,'after':after,
        'post_status':status,'rejection':rejection,'calls':CALLS,
        'native_update_tested':False,'active_write_attempts':0,'owner_write_attempts':0,
        'app_tokens_issued':0,'broker_requests':0},indent=2)+'\n')
    text=json.dumps(rejection).lower()
    need(status in (403,422) and 'creat' in text and ('restrict' in text or 'rule' in text), 'RULE_REJECTION_NOT_PROVEN')
    need(before == after, 'BEFORE_AFTER_DRIFT')
    print(json.dumps({'state':'SYNTHETIC_CREATION_REJECTED','http_status':status,'active_absent':True,
                      'native_update_tested':False,'owner_1807_preserved':True,'real_go':False}))


if __name__ == '__main__': main()
