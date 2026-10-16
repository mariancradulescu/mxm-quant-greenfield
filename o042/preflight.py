"""Protected preflight: no installation token endpoint or Git mutation capability."""
import base64, copy, hashlib, json, os, pathlib, subprocess, tempfile, time
from . import identity as i

NEW_FINGERPRINT='SHA256:if9s0/vBUMyiKrKc5p6RJoXtcI2sL6HGIWRjNhpRKpk='
OLD_FINGERPRINT='SHA256:SwoXRrvOz1/KtsJiDjEvHD9R7dSP431kk5KyuMEOaYU='
CANARY_HASH='5abe544f417f242049b2c28f67b308a6583b5e2c137322fd1d131641fcb18ffa'
APP_SLUG='mxm-o04-staging-acceptor-20261016'
APP_NAME='MXM O04 Staging Acceptor 20261016'

def openssl(args, data):
 r=subprocess.run(['openssl',*args],input=data,capture_output=True,env={'PATH':os.environ['PATH']})
 i.need(r.returncode==0,'KEY_CRYPTO_FAILED')
 return r.stdout

def jwt(key, issuer, message_path):
 now=int(time.time())
 message=(i.b64(i.canonical({'alg':'RS256','typ':'JWT'}))+'.'+i.b64(i.canonical({'iss':str(issuer),'iat':now-30,'exp':now+180}))).encode()
 message_path.write_bytes(message)
 sig=openssl(['dgst','-sha256','-sign','/dev/stdin',str(message_path)],key)
 return message.decode()+'.'+i.b64(sig)

def main():
 workload=i.authenticated_workload()
 i.need(os.environ.get('GITHUB_JOB')=='acceptor','WORKLOAD_JOB')
 i.need(i.sha(os.environ.get('CUSTODY_CANARY','').encode())==CANARY_HASH,'CUSTODY_CANARY')
 key=os.environ.pop('APP_PRIVATE_KEY','').encode()
 i.need(bool(key),'APP_KEY_MISSING')
 # Private bytes stay in process memory and stdin; never in argv or files.
 public_der=openssl(['pkey','-pubout','-outform','DER'],key)
 fingerprint='SHA256:'+base64.b64encode(hashlib.sha256(public_der).digest()).decode()
 i.need(fingerprint==NEW_FINGERPRINT and fingerprint!=OLD_FINGERPRINT,'NEW_KEY_FINGERPRINT_MISMATCH')
 # Restrict the App-authenticated transport to exactly GET /app.
 calls=[]
 def get_app(token, category):
  status,body=i.http('https://api.github.com/app',token,'GET')
  calls.append({'method':'GET','path':'/app','category':category,'server_HTTP':status})
  return status,body
 with tempfile.TemporaryDirectory() as tmp:
  message=pathlib.Path(tmp)/'public-jwt-message'
  token=jwt(key,i.APP_ID,message)
  status,app=get_app(token,'AUTHORIZED_NEW_KEY')
  del token
  i.need(status==200 and app.get('id')==i.APP_ID and app.get('slug')==APP_SLUG and app.get('name')==APP_NAME,'APP_IDENTITY')
  app_identity={k:app[k] for k in ['id','slug','name']}
  status,_=get_app(jwt(key,i.APP_ID+1,message),'WRONG_APP_IDENTITY')
  i.need(status==401,'WRONG_APP_IDENTITY_NOT_REJECTED')
  synthetic=openssl(['genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048'],b'')
  status,_=get_app(jwt(synthetic,i.APP_ID,message),'SYNTHETIC_UNREGISTERED_KEY')
  del synthetic
  i.need(status==401,'INVALID_KEY_NOT_REJECTED')
  status,_=get_app(None,'UNAUTHENTICATED')
  i.need(status==401,'UNAUTHENTICATED_NOT_REJECTED')
 del key
 # Verify authenticated public claims are rejected when the claimed job source changes.
 bad=copy.deepcopy(workload);bad['ref']='refs/heads/unauthorized'
 try:i.validate_workload(bad,workload['sha'],workload['run_attempt'])
 except i.Refused:claim_negative='REJECTED_AFTER_VERIFIED_OIDC'
 else:raise i.Refused('WRONG_WORKLOAD_NOT_REJECTED')
 receipt={'schema':'mxm.o042.preflight.v1','workload':workload,'app':app_identity,
  'public_key_fingerprint':fingerprint,'matches_new_key':True,'matches_old_key':False,
  'calls':calls,'workload_claim_negative':claim_negative,
  'installation_tokens_issued':0,'authority_ref_mutations':0,'OWNER_checkpoint_mutations':0,
  'private_key_written_to_file':False,'private_key_exported':False,
  'OWNER_ACCEPTS_NEW_CHECKPOINTS':False,'CAMPAIGN_RESTART_ALLOWED':False,'PRODUCTION_GO':False}
 out=pathlib.Path('verification');out.mkdir(exist_ok=True)
 (out/'o042-preflight.json').write_bytes(i.canonical(receipt)+b'\n')
 print(i.canonical(receipt).decode())

if __name__=='__main__':main()
