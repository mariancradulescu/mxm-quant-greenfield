"""Shared existing native git transaction for keyless evidence-plane writers."""
import base64,json,os,subprocess,tempfile
from pathlib import Path
from .common import *

def atomic_publish(route,parent,files,message):
    from .runtime import EVIDENCE_BRANCH,read_state
    need(not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM') and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'WRITER_NO_KEYS')
    env={k:v for k,v in os.environ.items() if k not in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY')}
    auth=base64.b64encode(('x-access-token:'+os.environ['GH_TOKEN']).encode()).decode();env.update(GIT_TERMINAL_PROMPT='0',GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+auth)
    def git(directory,*args):
        v=subprocess.run(['git',*args],cwd=directory,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120);need(v.returncode==0,'ATOMIC_GIT_'+args[0].upper().replace('-','_'));return v.stdout.decode().strip()
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
        d=Path(td);git(d,'init','-q');git(d,'remote','add','origin','https://github.com/mariancradulescu/mxm-quant-greenfield.git');git(d,'fetch','--depth=1','origin',parent);git(d,'checkout','--detach','FETCH_HEAD')
        for path,content in files.items():
            need(path=='program-state.json' or (not path.startswith('/') and '..' not in path.split('/')),'EVIDENCE_PATH')
            p=d/path
            if path!='program-state.json':need(not p.exists(),'DUPLICATE_EVIDENCE_WRITE')
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
        git(d,'config','user.name','github-actions[bot]');git(d,'config','user.email','41898282+github-actions[bot]@users.noreply.github.com');git(d,'add',*files)
        git(d,'commit','-m',message);commit=git(d,'rev-parse','HEAD')
        git(d,'push','--force-with-lease=refs/heads/'+EVIDENCE_BRANCH+':'+parent,'origin','HEAD:refs/heads/'+EVIDENCE_BRANCH)
    need(route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']==commit,'ATOMIC_ACK_AMBIGUOUS')
    return commit

def chunk_ciphertext(blob,prefix,part_size=256000):
    need(0<len(blob)<=16*1024*1024,'CHECKPOINT_TECHNICAL_SIZE')
    files={};parts=[]
    for i,offset in enumerate(range(0,len(blob),part_size)):
        part=blob[offset:offset+part_size];path=prefix+'/ciphertext.parts/part'+str(i).zfill(4)+'.b64'
        files[path]=base64.b64encode(part)+b'\n';parts.append({'index':i,'offset':offset,'length':len(part),'sha256':bytes_digest(part),'path':path})
    manifest={'schema':'mxm.encrypted-checkpoint-parts.v1','sha256':bytes_digest(blob),'size':len(blob),'parts':parts}
    return files,manifest

def restore_ciphertext(manifest,fetch):
    need(manifest['schema']=='mxm.encrypted-checkpoint-parts.v1' and 0<manifest['size']<=16*1024*1024,'CIPHER_PART_MANIFEST')
    value=bytearray()
    for i,p in enumerate(manifest['parts']):
        need(p['index']==i and p['offset']==len(value) and 0<p['length']<=256000,'CIPHER_PART_ORDER')
        b=base64.b64decode(fetch(p['path']),validate=False);need(len(b)==p['length'] and bytes_digest(b)==p['sha256'],'CIPHER_PART_CHANGED');value.extend(b)
    need(len(value)==manifest['size'] and bytes_digest(value)==manifest['sha256'],'CIPHER_PARTS_AGGREGATE')
    return bytes(value)
