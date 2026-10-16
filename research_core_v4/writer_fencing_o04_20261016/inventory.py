"""Read Git objects, never import or execute historical code. No network calls.

Inventory of all advertised heads/tags and executable history. Static findings
are candidates, not a claim of complete visibility into credentials or dynamic IO.
"""
import collections
import hashlib
import json
import pathlib
import re
import subprocess
import sys

CODE = {'.py', '.sh', '.bash', '.js', '.ts', '.mjs', '.yml', '.yaml', '.ps1', '.cs'}
RULES = {
    'release_mutation': r"(?:releases|upload_asset|upload_url|gh release|uploads\.github\.com)",
    'git_ref_or_content_mutation': r"(?:git/refs|git/ref|git/commits|git/trees|git/blobs|update_ref|update-ref|git push|push_files|create_commit|/contents/)",
    'authority_or_checkpoint_local_write': r"(?:write_text|write_bytes|json\.dump|INSERT|UPDATE|open\(.{0,100}['\"](?:w|a|wb)['\"])",
    'dispatch_or_control_mutation': r"(?:dispatches|/cancel|/rerun|/disable|/enable|rulesets|/protection)",
    'dynamic_execution': r"(?:\bexec\(|\beval\(|import_module|__import__|curl |wget |subprocess\.)",
}
MUTATION = re.compile(r"\b(?:POST|PATCH|PUT|DELETE)\b|method\s*=|git push|gh release|upload_asset|update-ref|write_text|write_bytes|json\.dump")

def git(*args):
    return subprocess.check_output(['git', *args])

def scan(output):
    refs = []
    occurrences = collections.defaultdict(list)
    paths = collections.defaultdict(set)
    advertised = {}
    for row in git('for-each-ref', '--format=%(refname) %(objectname) %(symref)', 'refs/heads', 'refs/remotes/origin', 'refs/tags').decode().splitlines():
        fields = row.split()
        if len(fields) != 2:  # Skip symbolic origin/HEAD.
            continue
        ref, oid = fields
        if ref.startswith('refs/remotes/origin/'):
            ref = 'refs/heads/'+ref.removeprefix('refs/remotes/origin/')
        if ref in advertised and advertised[ref] != oid:
            raise ValueError('LOCAL_REMOTE_REF_DRIFT')
        advertised[ref] = oid
    for ref, oid in sorted(advertised.items()):
        refs.append({'ref': ref, 'oid': oid})
        for record in git('ls-tree', '-rz', '--full-tree', oid).split(b'\0'):
            if not record:
                continue
            meta, rawpath = record.split(b'\t', 1)
            mode, typ, blob = meta.decode().split()
            path = rawpath.decode()
            if typ == 'blob' and pathlib.PurePosixPath(path).suffix in CODE:
                paths[blob].add(path)
                occurrences[(blob, path)].append(ref)
    # Include former versions reachable through commit history (rerun exposure).
    for record in git('rev-list', '--objects', '--all').decode().splitlines():
        oid, _, path = record.partition(' ')
        if pathlib.PurePosixPath(path).suffix in CODE:
            paths[oid].add(path)
    proc = subprocess.Popen(['git', 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    findings = []
    workflows = []
    compiled = {k: re.compile(v, re.I) for k, v in RULES.items()}
    for oid in sorted(paths):
        proc.stdin.write((oid+'\n').encode()); proc.stdin.flush()
        header = proc.stdout.readline().decode().split()
        if len(header) != 3:
            raise ValueError('OBJECT_MISSING')
        raw = proc.stdout.read(int(header[2])); proc.stdout.read(1)
        if header[1] != 'blob':
            continue
        try:
            text = raw.decode()
        except UnicodeDecodeError:
            continue
        lines = text.splitlines()
        cats = {k: [i+1 for i, line in enumerate(lines) if pat.search(line)] for k, pat in compiled.items()}
        cats = {k: v for k, v in cats.items() if v}
        for path in sorted(paths[oid]):
            common = {'path': path, 'blob': oid, 'sha256': hashlib.sha256(raw).hexdigest(), 'refs': occurrences.get((oid, path), []), 'historical_only': not bool(occurrences.get((oid, path)))}
            if path.startswith('.github/workflows/'):
                # Store exact workflow source for independently reproducible review.
                workflows.append({**common, 'source': text,
                    'contents_write': bool(re.search(r'contents:\s*write|write-all', text)),
                    'actions_write': bool(re.search(r'actions:\s*write|write-all', text)),
                    'secrets': sorted(set(re.findall(r'secrets\.([A-Za-z_0-9]+)', text))),
                    'uses': sorted(set(re.findall(r'uses:\s*([^\s]+)', text)))})
            if cats and (MUTATION.search(text) or 'dynamic_execution' in cats):
                findings.append({**common, 'categories_and_lines': cats,
                    'review': 'STATIC_CANDIDATE_NOT_PROOF_OF_EFFECTIVE_CREDENTIALS'})
    proc.stdin.close(); proc.wait()
    assert proc.returncode == 0
    result = {'schema': 'mxm.o04.writer_inventory.v1', 'refs': refs, 'sources': findings, 'workflow_versions': workflows,
        'summary': {'heads': sum(r['ref'].startswith('refs/heads/') for r in refs),
            'tags': sum(r['ref'].startswith('refs/tags/') for r in refs), 'code_blobs_examined': len(paths),
            'source_candidates': len(findings), 'workflow_versions': len(workflows),
            'write_workflow_versions': sum(w['contents_write'] for w in workflows)},
        'limits': ['Static search cannot prove absence of dynamic or externally supplied writers.',
            'Credential inventory, installations, deploy keys, PAT grants, Actions policy and admin bypasses require administrative evidence.',
            'Old workflow reruns use historical code; changing only branch heads cannot revoke that authority.',
            'History-only object paths use Git rev-list first-reported path; current heads/tags include every matching path.']}
    output.write_text(json.dumps(result, sort_keys=True, separators=(',', ':'))+'\n')
    print(json.dumps(result['summary'], sort_keys=True))

if __name__ == '__main__':
    scan(pathlib.Path(sys.argv[1]))
