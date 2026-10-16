"""Pinned source GET + AST only. Historical code is never imported or executed."""
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
from .authority import Denied, need, digest

INVENTORY_PATH = 'docs/p0-failclosed/20261016/HISTORICAL_CONSUMERS.json'
INVENTORY_SHA256 = '35edb86e2653e3cb56fb65163a2446e8eaff68bac4b0a3f017e14c4dafe6d27e'
REPO = 'mariancradulescu/mxm-quant-greenfield'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Denied('SOURCE_REDIRECT_DENIED')


def fetch_pinned(source):
    url = ('https://api.github.com/repos/'+REPO+'/contents/'+
           urllib.parse.quote(source['path'],safe='/')+'?ref='+source['ref'])
    req = urllib.request.Request(url, method='GET', headers={
        'Authorization':'Bearer '+os.environ['GH_TOKEN'], 'Accept':'application/vnd.github+json',
        'X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.build_opener(NoRedirect).open(req,timeout=30) as response:
        need(response.status == 200,'SOURCE_GET_FAILED')
        meta = json.loads(response.read(4*1024*1024))
    raw = base64.b64decode(meta['content'])
    need(meta['sha'] == source['blob_oid'] and digest(raw) == source['sha256'], 'PINNED_SOURCE_DIGEST')
    need(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == source['blob_oid'], 'GIT_BLOB_DIGEST')
    return raw


def adapter_for(row):
    name = row['function']
    if row['path'].endswith('/owner.py'):
        return 'archive'
    if name in ('worker','handoff','economic'):
        return name
    if name == 'main' or name == 'gate':
        return 'dispatcher_boundary'
    if name == 'dry_run':
        return 'staging_adapter_not_migration'
    return 'restore'


def analyze(inventory, fetcher):
    need(len(inventory['sources']) == 10 and len(inventory['consumers']) == 29, 'INVENTORY_COUNTS')
    sources = {}; versions = []
    for source in inventory['sources']:
        raw = fetcher(source)
        need(digest(raw) == source['sha256'], 'SOURCE_INTEGRITY')
        tree = ast.parse(raw.decode('utf-8'))
        found = {}
        for item in tree.body:
            if isinstance(item,ast.FunctionDef):
                found[item.name] = item
            elif isinstance(item,ast.ClassDef):
                found.update({item.name+'.'+m.name:m for m in item.body if isinstance(m,ast.FunctionDef)})
        sources[(source['path'],source['ref'])] = (found,raw)
        versions.append({**source,'readback_sha256':digest(raw),'method':'GET_THEN_AST_PARSE_ONLY','executed':False})
    rows = []
    for row in inventory['consumers']:
        found,raw = sources[(row['path'],row['source_ref'])]
        need(row['function'] in found, 'HISTORICAL_FUNCTION_MISSING')
        function = found[row['function']]
        need((function.lineno,function.end_lineno) == (row['first_line'],row['last_line']), 'SOURCE_LINES_DRIFT')
        lines = raw.decode('utf-8').splitlines()
        for route in row['route_evidence']:
            need(lines[route['line']-1].strip() == route['text'], 'ROUTE_EVIDENCE_DRIFT')
        rows.append({**row,'adapter_boundary':adapter_for(row),
            'positional_arguments':[a.arg for a in function.args.posonlyargs+function.args.args],
            'keyword_only_arguments':[a.arg for a in function.args.kwonlyargs],
            'migration_status':'NOT_MIGRATED_NOT_EXECUTED',
            'new_boundary':'archive bytes only' if adapter_for(row)=='archive' else
                'explicit synthetic active selection + scoped dual receipt + durable intent; no execution',
            'eliminated_as_authority_in_new_code':['release body','legacy manifest','side ref','automatic fallback'],
            'compatibility_scope':'pinned function identity/signature/route AST and synthetic input envelope; no behavioral equivalence claim'})
    return {'schema':'mxm.p0.supersession.compatibility.v1','source_versions':versions,
            'consumer_matrix':rows,'historical_imports':0,'historical_executions':0,
            'source_gets':10,'authority_writes':0,'operational_migrations':0}


def main():
    raw = Path(INVENTORY_PATH).read_bytes()
    need(digest(raw) == INVENTORY_SHA256, 'ACCEPTED_INVENTORY_DRIFT')
    inventory = json.loads(raw)
    result = analyze(inventory,fetch_pinned)
    output = Path('verification/p0-supersession'); output.mkdir(parents=True,exist_ok=True)
    (output/'compatibility.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'pinned_source_versions':10,'function_versions':29,'historical_executions':0,'method':'GET_AST_ONLY'}))


if __name__ == '__main__': main()
