"""Private OWNER readback. GET-only; no release constructor and no broker imports."""
import base64
import json
import os
import pathlib
import struct
import subprocess
import tempfile
import urllib.request
from .safety import require, sha, unpack, strict_json, JOURNAL, CANONICAL, BRANCH, clean_tree
from research_core_v4 import master1576_screen_v2 as crypto
from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret

FP='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11'
CIPHER='4c4380f9de060d4bd7c8b7fb9be61916285ab581be2bdd8ba72e17909a83adac'
PACKED='a0168de6be0817b192f154f128514da32bc1f0c2b9d14db9a9f63ff055ccf628'
REPO='mariancradulescu/mxm-quant-greenfield'

def get(path):
    # Endpoint allowlist; no redirects to authenticated mutation paths.
    require(path.startswith(('releases/','git/ref/heads/','actions/runs')),'GET_NAMESPACE')
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=45) as r:return strict_json(r.read(16*1024*1024))

def bounded_decrypt(blob,key,tmp):
    # Existing envelope format and key route; cap the OpenPGP decoded output too.
    require(blob.startswith(crypto.MAGIC),'ENVELOPE_FORMAT')
    pos=len(crypto.MAGIC);n=struct.unpack('>I',blob[pos:pos+4])[0];pos+=4
    require(0<n<=16384 and pos+n<len(blob),'ENVELOPE_LENGTH')
    pub=crypto.command(['openssl','pkey','-in',str(key),'-pubout','-outform','DER'])
    require(sha(pub)==FP,'OWNER_KEY_MISMATCH')
    with tempfile.TemporaryDirectory(dir=tmp) as d:
        d=pathlib.Path(d);home=d/'gnupg';home.mkdir(mode=0o700)
        wrapped=d/'wrapped';cipher=d/'cipher';password=d/'pass';plain=d/'plain'
        wrapped.write_bytes(blob[pos:pos+n]);cipher.write_bytes(blob[pos+n:])
        try:
            crypto.command(['openssl','pkeyutl','-decrypt','-inkey',str(key),'-in',str(wrapped),'-out',str(password),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'])
            password.chmod(0o600)
            crypto.command(['gpg','--homedir',str(home),'--batch','--yes','--max-output','134217728','--no-symkey-cache','--pinentry-mode','loopback','--passphrase-file',str(password),'--output',str(plain),'--decrypt',str(cipher)])
            require(plain.stat().st_size<=128*1024*1024,'PACKED_SIZE_LIMIT')
            return plain.read_bytes()
        finally:
            subprocess.run(['gpgconf','--homedir',str(home),'--kill','gpg-agent'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,check=False)

INVENTORY_CACHE={}

def read_asset(meta,key,tmp):
    asset=get('releases/assets/'+str(meta['id']))
    require(asset['size']==meta['size'] and asset['name']==meta['name'] and asset['digest']=='sha256:'+meta['ciphertext_sha256'],'ASSET_METADATA_DRIFT')
    # Verify membership by full pagination. A filename is never sufficient.
    rid=meta['release_id']
    if rid not in INVENTORY_CACHE:
        inventory=[];page=1
        while True:
            rows=get('releases/'+str(rid)+'/assets?per_page=100&page='+str(page));inventory+=rows
            if len(rows)<100:break
            page+=1;require(page<=100,'INVENTORY_LIMIT_UNKNOWN')
        INVENTORY_CACHE[rid]=inventory
    inventory=INVENTORY_CACHE[rid]
    require(len([a for a in inventory if a['id']==meta['id'] and a['digest']==asset['digest']])==1,'ASSET_RELEASE_BINDING')
    url=asset['browser_download_url'];require(url.startswith('https://github.com/'+REPO+'/releases/download/'),'ASSET_URL_SCOPE')
    with urllib.request.urlopen(url,timeout=90) as r:blob=r.read(meta['size']+1)
    require(len(blob)==meta['size'] and sha(blob)==meta['ciphertext_sha256'],'CIPHER_DIGEST')
    packed=bounded_decrypt(blob,key,tmp);require(sha(packed)==meta['gzip_sha256'],'PACKED_DIGEST_MISMATCH')
    raw=unpack(packed);require(sha(raw)==meta['canonical_sha256'],'CANONICAL_DIGEST')
    return strict_json(raw)

def main():
    root=pathlib.Path(__file__).resolve().parents[2];clean_tree(root)
    require(os.environ['GITHUB_REF_NAME']==BRANCH and os.environ['GITHUB_RUN_ATTEMPT']=='1','REMEDIATION_SCOPE')
    require(get('git/ref/heads/'+BRANCH)['object']['sha']==os.environ['GITHUB_SHA'],'HEAD_DRIFT')
    require(get('git/ref/heads/performance-research-v3-20260922')['object']['sha']==CANONICAL,'CANONICAL_DRIFT')
    before=get('releases/412686323');body=strict_json(before['body']);m=body['current_journal']
    require(body['generation']==1807 and body['state']=='STOP_FAIL_CLOSED' and body['pending_request_count']==0 and m['id']==642889915 and m['canonical_sha256']==JOURNAL and m['ciphertext_sha256']==CIPHER and m['gzip_sha256']==PACKED,'ANCHOR_DRIFT')
    os.umask(0o077)
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as t:
        tmp=pathlib.Path(t);key,fp=_private_key_from_secret(tmp);require(fp==FP,'OWNER_KEY')
        journal=read_asset(m,key,tmp)
        require(journal['generation']==1807 and not journal.get('pending_requests'),'OWNER_JOURNAL_STATE')
        # Second cold interpreter independently decrypts same immutable object.
        # Only digest-only proof crosses process boundary; plaintext stays private.
        env=dict(os.environ,MXM_READBACK_KEY_PATH=str(key),MXM_READBACK_TMP=str(tmp))
        result=subprocess.run([os.environ.get('MXM_COLD_PYTHON','python3'),'-m',__package__+'.owner','--cold-child'],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=180,check=False)
        require(result.returncode==0 and strict_json(result.stdout)['canonical_sha256']==JOURNAL,'COLD_PROCESS_READBACK')
        from .impact import inspect
        impact=inspect(journal,read_asset,key,tmp,root)
        from .economics import EconomicReader
        checkpoint={'generation':1807,'journal_sha256':JOURNAL}
        receipt={**checkpoint,'state':'COMMITTED','owner_readback':True,'writer_active':False,'sequence':journal['autonomy']['sequence']}
        state=EconomicReader(tmp/'economic-reader.sqlite').evaluate(checkpoint,receipt)
        state.update(source_run_id=body['run_id'],source_head=body['execution_source_head'],current_authority='REMEDIATION_READ_ONLY;NO_RESEARCH')
        pathlib.Path('verification/economic-state.json').write_text(json.dumps(state,sort_keys=True)+'\n')
        lineage=[]
        historical_run=get('actions/runs/38679002289')
        for rid in (413405151,413406302):
            rel=get('releases/'+str(rid));b=strict_json(rel['body']);value=read_asset(b['primary'],key,tmp)
            cp=value.get('checkpoint')
            if cp is None:
                old=read_asset(value['snapshots']['after'],key,tmp)
                generation=old['generation'];jhash=value['snapshots']['after']['canonical_sha256']
            else:
                generation=cp['generation'];jhash=cp['current_journal']['canonical_sha256']
            lineage.append({'release_id':rid,'asset_id':b['primary']['id'],'run_id':historical_run['id'],'head':historical_run['head_sha'],'generation':generation,'journal_sha256':jhash,'canonical_sha256':b['primary']['canonical_sha256'],'OWNER_readback':True,'outcome_recomputed':False,'NET':None})
        pathlib.Path('verification/historical-economic-lineage.json').write_text(json.dumps({'scope':'TWO_PINNED_RELEASES_ONLY','rows':lineage,'independent_signoff':False},sort_keys=True)+'\n')

    after=get('releases/412686323');require(after['body']==before['body'],'ORIGINAL_ANCHOR_CHANGED')
    proof={'state':'OWNER_VERIFIED_JOURNAL_ONLY','generation':1807,'journal_asset_id':m['id'],'canonical_sha256':JOURNAL,'ciphertext_sha256':CIPHER,'gzip_sha256':PACKED,'cold_process_readback':True,'parent_python':__import__('sys').version.split()[0],'child_python':strict_json(result.stdout).get('python_version'),'original_anchor_unchanged':True,'broker_requests':0,'orders':0,'collection_writes':0,'scope':'MANIFEST_1807_PLUS_DIRECT_REFERENCES_NOT_ALL_HISTORICAL_IMPORT_INPUTS','impact':impact,'alpha_certified':False,'HARD21':False,'source_head':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID']}
    pathlib.Path('verification').mkdir(exist_ok=True);pathlib.Path('verification/owner.json').write_text(json.dumps(proof,sort_keys=True)+'\n')
    print(json.dumps(proof,sort_keys=True))

def child():
    m=strict_json(get('releases/412686323')['body'])['current_journal']
    require(m['id']==642889915 and m['canonical_sha256']==JOURNAL,'CHILD_PIN')
    obj=read_asset(m,pathlib.Path(os.environ['MXM_READBACK_KEY_PATH']),pathlib.Path(os.environ['MXM_READBACK_TMP']))
    require(obj['generation']==1807,'CHILD_GENERATION')
    print(json.dumps({'canonical_sha256':m['canonical_sha256'],'python_version':__import__('sys').version.split()[0]}))

if __name__=='__main__':
    import sys
    try:
        if '--cold-child' in sys.argv:child()
        else:main()
    except Exception as ex:
        from .safety import safe_error
        print(json.dumps({'state':'OWNER_READBACK_BLOCKED',**safe_error(ex)}));raise SystemExit(1) from None
