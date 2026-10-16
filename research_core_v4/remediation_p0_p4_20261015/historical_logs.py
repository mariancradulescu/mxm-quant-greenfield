"""GET-only verification of exact preserved historical job receipts.

Raw log bodies and URLs stay in memory. Missing logs remain UNKNOWN; this is
receipt recovery, never a re-run of a historical workflow or scientific test.
"""
import base64
import concurrent.futures
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from .safety import require, sha, BRANCH, CANONICAL, JOURNAL

REPO = 'mariancradulescu/mxm-quant-greenfield'

class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require(urllib.parse.urlsplit(newurl).scheme == 'https', 'NON_HTTPS_LOG_REDIRECT')
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if urllib.parse.urlsplit(newurl).hostname != 'api.github.com':
            new.remove_header('Authorization')
        return new

def request(path, kind='json'):
    require(path.startswith(('actions/', 'contents/', 'git/ref/heads/', 'releases/')), 'HISTORICAL_READER_NAMESPACE')
    req = urllib.request.Request('https://api.github.com/repos/' + REPO + '/' + path, method='GET', headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json'})
    with urllib.request.build_opener(Redirect()).open(req, timeout=45) as r:
        raw = r.read(16 * 1024 * 1024 + 1)
    require(len(raw) <= 16 * 1024 * 1024, 'HISTORICAL_RECEIPT_SIZE_UNKNOWN')
    return json.loads(raw) if kind == 'json' else raw

def verify_job(item, api=request):
    try:
        job = api('actions/jobs/' + str(item['job_id']))
        run = api('actions/runs/' + str(item['run_id']) + '/attempts/' + str(item['attempt']))
        require(job['run_id'] == item['run_id'] and job['run_attempt'] == item['attempt'] and run['head_sha'] == item['head'] and job['head_sha'] == item['head'], 'HISTORICAL_JOB_HEAD_OR_ATTEMPT_MISMATCH')
        blob = api('actions/jobs/' + str(item['job_id']) + '/logs', 'bytes')
        # Match exactly the earlier decoded UTF-8 hashing convention.
        digest = sha(blob.decode('utf-8', errors='replace').encode('utf-8'))
        require(digest == item['log_sha256'], 'HISTORICAL_LOG_DIGEST_MISMATCH')
        workflow = api('contents/' + item['workflow'] + '?ref=' + item['head'])
        raw = base64.b64decode(workflow['content'], validate=False)
        require(sha(raw) == item['workflow_sha256'], 'HISTORICAL_WORKFLOW_DIGEST_MISMATCH')
        guards = []
        for guard in item['guard_paths']:
            path = guard['path']
            try:
                api('contents/' + path + '?ref=' + item['head']); exists = True
            except urllib.error.HTTPError as exc:
                if exc.code != 404: raise
                exists = False
            require(exists == guard['existed_at_execution'], 'HISTORICAL_GUARD_EXISTENCE_MISMATCH')
            guards.append({'path': path, 'existed_at_execution': exists, 'absence_check_in_workflow': ('test ! -e ' + path) in raw.decode('utf-8')})
        if item['historical_class'] == 'ARM absence guard':
            require(any(g['existed_at_execution'] and g['absence_check_in_workflow'] for g in guards), 'HISTORICAL_ARM_GUARD_UNVERIFIED')
        return {**item, 'state': 'HISTORICAL_RECEIPT_VERIFIED', 'log_sha256_live': digest, 'workflow_sha256_live': sha(raw), 'guard_readback': guards, 'conclusion_historical': job['conclusion'], 'broker_root_cause_proved': False, 'scientific_rerun': False, 'independent_acceptance': False}
    except Exception as exc:
        # No exception body, redirect URLs or raw log text in evidence output.
        code = str(exc) if isinstance(exc, ValueError) and str(exc).startswith('HISTORICAL_') else 'HTTP_' + str(exc.code) if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
        return {**item, 'state': 'UNKNOWN_RECEIPT_NOT_VERIFIED', 'safe_code': code, 'broker_root_cause_proved': False, 'scientific_rerun': False}

def verify_missing(item, api=request):
    try:
        job = api('actions/jobs/' + str(item['job_id']))
        require(job['run_id'] == item['run_id'] and job['head_sha'] == item['head'] and job['run_attempt'] == item['attempt'], 'HISTORICAL_JOB_HEAD_OR_ATTEMPT_MISMATCH')
        raw = api('actions/jobs/' + str(item['job_id']) + '/logs', 'bytes')
        return {**item, 'state': 'NOW_AVAILABLE_UNADJUDICATED', 'log_sha256': sha(raw), 'cause': 'UNKNOWN_NO_AUTOMATIC_SUCCESS'}
    except urllib.error.HTTPError as exc:
        return {**item, 'state': 'UNAVAILABLE_404' if exc.code == 404 else 'UNAVAILABLE_HTTP_' + str(exc.code), 'cause': 'UNKNOWN_NO_SUCCESS_OR_BROKER_FAILURE_INFERRED'}
    except Exception as exc:
        return {**item, 'state': 'UNKNOWN_' + type(exc).__name__, 'cause': 'UNKNOWN_NO_SUCCESS_OR_BROKER_FAILURE_INFERRED'}

def verify_zero_job(item, api=request):
    try:
        run = api('actions/runs/' + str(item['run_id']) + '/attempts/' + str(item['attempt']))
        jobs = api('actions/runs/' + str(item['run_id']) + '/attempts/' + str(item['attempt']) + '/jobs?per_page=100')
        require(run['head_sha'] == item['head'] and run['conclusion'] == 'cancelled', 'HISTORICAL_CANCELLED_RUN_DRIFT')
        require(jobs['total_count'] == 0 and not jobs['jobs'], 'HISTORICAL_ZERO_JOB_DRIFT')
        return {**item, 'state': 'CANCELLED_ZERO_JOB_VERIFIED', 'cause': 'UNKNOWN_NO_JOB_LOG_EXISTS'}
    except Exception as exc:
        return {**item, 'state': 'UNKNOWN_' + type(exc).__name__, 'cause': 'UNKNOWN_NO_SUCCESS_OR_BROKER_FAILURE_INFERRED'}

def validate_catalog(catalog):
    for key, number, identity in (('records', 44, 'job_id'), ('unavailable_logs', 74, 'job_id'), ('zero_job_cancelled_runs', 79, 'run_id')):
        rows = catalog[key]
        require(len(rows) == number and len({r[identity] for r in rows}) == number, 'HISTORICAL_TARGET_SET_NOT_EXACT')
    require(not ({r['job_id'] for r in catalog['records']} & {r['job_id'] for r in catalog['unavailable_logs']}), 'HISTORICAL_TARGET_SET_OVERLAP')

def main():
    require(os.environ['GITHUB_REF_NAME'] == BRANCH and os.environ['GITHUB_RUN_ATTEMPT'] == '1', 'HISTORICAL_SCOPE')
    require(request('git/ref/heads/' + BRANCH)['object']['sha'] == os.environ['GITHUB_SHA'], 'HEAD_DRIFT')
    require(request('git/ref/heads/performance-research-v3-20260922')['object']['sha'] == CANONICAL, 'CANONICAL_DRIFT')
    before = request('releases/412686323')['body']; anchor = json.loads(before)
    require(anchor['generation'] == 1807 and anchor['state'] == 'STOP_FAIL_CLOSED' and anchor['current_journal']['canonical_sha256'] == JOURNAL, 'ANCHOR_DRIFT')
    root = pathlib.Path(__file__).resolve().parents[2]
    catalog = json.loads((pathlib.Path(__file__).parent / 'historical_log_catalog.json').read_text()); validate_catalog(catalog)
    result = {'schema': 'mxm.remediation.historical.log.recovery.v1', 'source_head': os.environ['GITHUB_SHA'], 'run_id': os.environ['GITHUB_RUN_ID'], 'source_catalog_sha256': sha((pathlib.Path(__file__).parent / 'historical_log_catalog.json').read_bytes()), 'scope': catalog['scope']}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for key, fn in (('records', verify_job), ('unavailable_logs', verify_missing), ('zero_job_cancelled_runs', verify_zero_job)):
            result[key] = list(pool.map(fn, catalog[key]))
            print(json.dumps({'phase': 'HISTORICAL_RECEIPT_RECOVERY', 'group': key, 'targets': len(result[key])}), flush=True)
    require(request('releases/412686323')['body'] == before, 'ORIGINAL_ANCHOR_CHANGED')
    summary = {'targets': 44, 'verified_targets': sum(r['state'] == 'HISTORICAL_RECEIPT_VERIFIED' for r in result['records']), 'ARM_absence_guards_verified': sum(r['state'] == 'HISTORICAL_RECEIPT_VERIFIED' and r['historical_class'] == 'ARM absence guard' for r in result['records']), 'missing_log_targets': 74, 'missing_logs_still_unavailable': sum(r['state'] == 'UNAVAILABLE_404' for r in result['unavailable_logs']), 'zero_job_targets': 79, 'zero_job_runs_verified': sum(r['state'] == 'CANCELLED_ZERO_JOB_VERIFIED' for r in result['zero_job_cancelled_runs']), 'root_causes_extrapolated': False, 'independent_acceptance': False, 'broker_requests': 0, 'workflow_reruns': 0, 'anchor_unchanged': True}
    result['summary'] = summary
    out = root / 'verification'; out.mkdir(exist_ok=True)
    (out / 'historical-log-receipts.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    (out / 'historical-log-summary.json').write_text(json.dumps(summary, sort_keys=True) + '\n')
    print(json.dumps(summary, sort_keys=True))

if __name__ == '__main__':
    main()
