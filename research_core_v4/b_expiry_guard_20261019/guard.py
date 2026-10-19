"""Cancel only the expired, unreviewed bootstrap. Never renew or dispatch it.

No App credential, OWNER key, broker route, source mutation or ref writer.
Cancellation after the immutable admission deadline is safe even if an approval
races the final GET: native.execute rejects the expired initial manifest before
loading the App key. Reviewed or ambiguous histories are otherwise left alone.
"""
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

REPO = 'mariancradulescu/mxm-quant-greenfield'
RUN = 39147483523
SOURCE = '95fc312a84f803276a408ca4f821a09b007e56b0'
BRANCH = 'mxm-o04-successor-code-b-v1'
WORKFLOW = '.github/workflows/mxm-p0-successor-runtime-b.yml'
ENVIRONMENT = 24553414129
MANIFEST = 'e9bcc6dcdfdff505bd4759319be896aeb03a44d4c24597e66f8344cbfdcb8a06'
BUNDLE = '37234f128cc59452bfe237dfbc8ffeac2fda65ae1fe3d9935056900461b7d17e'
ROOT = Path(__file__).resolve().parents[2]
SELF = 'mxm-b-expiry-guard.yml'

def need(condition, code):
    if not condition:
        raise ValueError(code)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def validate_bundle(bundle):
    need(hashlib.sha256(canonical(bundle)).hexdigest() == BUNDLE, 'EXPIRY_BUNDLE_DRIFT')
    manifest = bundle['manifest']
    need(hashlib.sha256(canonical(manifest)).hexdigest() == MANIFEST, 'EXPIRY_MANIFEST_DRIFT')
    need(bundle['binding']['run_id'] == RUN and manifest['source_sha'] == SOURCE,
         'EXPIRY_BINDING')
    return manifest['expires_at']

def decision(bundle, run, reviews, now):
    deadline = validate_bundle(bundle)
    need(type(now) is int, 'EXPIRY_CLOCK')
    need(run.get('id') == RUN and run.get('head_sha') == SOURCE and
         run.get('head_branch') == BRANCH and run.get('path') == WORKFLOW and
         run.get('run_attempt') == 1 and run.get('event') == 'workflow_dispatch' and
         run.get('repository', {}).get('full_name') == REPO, 'EXPIRY_RUN_IDENTITY')
    need(type(reviews) is list, 'EXPIRY_REVIEW_FORMAT')
    matching = []
    for review in reviews:
        need(type(review) is dict and type(review.get('environments')) is list,
             'EXPIRY_REVIEW_FORMAT')
        need(all(type(e) is dict and type(e.get('id')) is int for e in review['environments']),
             'EXPIRY_REVIEW_FORMAT')
        if any(e['id'] == ENVIRONMENT for e in review['environments']):
            matching.append(review)
    need(len(matching) <= 1, 'EXPIRY_AMBIGUOUS_REVIEW')
    if run['status'] == 'completed':
        return 'TERMINAL_NO_ACTION'
    if matching:
        return 'REVIEW_PRESENT_NO_ACTION'
    if run['status'] != 'waiting':
        return 'NOT_WAITING_NO_ACTION'
    return 'CANCEL_EXPIRED_UNREVIEWED' if now >= deadline else 'VALID_WAITING_NO_ACTION'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('EXPIRY_REDIRECT_DENIED')

def api(suffix, method='GET'):
    # Write surface is fixed to cancel this run or disable this guard itself.
    allowed = {('POST', 'actions/runs/'+str(RUN)+'/cancel'),
               ('PUT', 'actions/workflows/'+SELF+'/disable')}
    need(method == 'GET' or (method, suffix) in allowed, 'EXPIRY_WRITE_SCOPE')
    need(suffix in ('actions/runs/'+str(RUN), 'actions/runs/'+str(RUN)+'/approvals') or
         (method, suffix) in allowed, 'EXPIRY_READ_SCOPE')
    request = urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+suffix,
        method=method, data=None if method == 'GET' else b'', headers={
            'Authorization':'Bearer '+os.environ['GH_TOKEN'],
            'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
        raw = response.read(4*1024*1024+1)
        need(len(raw) <= 4*1024*1024, 'EXPIRY_RESPONSE_BUDGET')
        return response.status, json.loads(raw) if raw else None

def main():
    need(os.environ.get('GITHUB_REPOSITORY') == REPO and
         os.environ.get('GITHUB_RUN_ATTEMPT') == '1' and
         os.environ.get('GITHUB_JOB') == 'expiry-guard', 'EXPIRY_WORKLOAD')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY',
         'O04_ACCEPTOR_APP_PRIVATE_KEY','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM')),
         'EXPIRY_UNEXPECTED_SECRET')
    bundle = json.loads((ROOT/'docs/p0-successor-b/20261018/NATIVE_BUNDLE_39147483523.json').read_bytes())
    _, run = api('actions/runs/'+str(RUN))
    _, reviews = api('actions/runs/'+str(RUN)+'/approvals')
    action = decision(bundle, run, reviews, int(time.time()))
    cancelled = False
    if action == 'CANCEL_EXPIRED_UNREVIEWED':
        # Re-read immediately before cancellation; never POST a retry.
        _, run = api('actions/runs/'+str(RUN))
        _, reviews = api('actions/runs/'+str(RUN)+'/approvals')
        action = decision(bundle, run, reviews, int(time.time()))
        if action == 'CANCEL_EXPIRED_UNREVIEWED':
            status, _ = api('actions/runs/'+str(RUN)+'/cancel', 'POST')
            need(status == 202, 'EXPIRY_CANCEL_NOT_ACKNOWLEDGED')
            cancelled = True  # Request accepted, not a claim of terminal state.
    disabled = False
    if action == 'TERMINAL_NO_ACTION':
        status, _ = api('actions/workflows/'+SELF+'/disable', 'PUT')
        need(status == 204, 'EXPIRY_SELF_DISABLE_NOT_ACKNOWLEDGED')
        disabled = True
    receipt = {'schema':'mxm.b-expiry-guard.v1','target_run_id':RUN,
               'guard_run_id':int(os.environ['GITHUB_RUN_ID']), 'action':action,
               'deadline':validate_bundle(bundle), 'cancellation_requested':cancelled,
               'self_disabled':disabled,'bootstrap_dispatches':0,'authority_writes':0,
               'app_key_used':False,'owner_key_used':False}
    out = ROOT/'verification/b-expiry-guard';out.mkdir(parents=True, exist_ok=True)
    (out/'receipt.json').write_bytes(canonical(receipt))
    print(canonical(receipt).decode())

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not print response bodies, headers, token or exception locals.
        code = str(error) if isinstance(error, ValueError) and str(error).startswith('EXPIRY_') else type(error).__name__
        print(json.dumps({'state':'EXPIRY_GUARD_STOP','safe_code':code}))
        raise SystemExit(1) from None
