"""GitHub OIDC verification; no token, key, or JWT payload logging."""
import base64,hashlib,json,os,pathlib,subprocess,tempfile,time,urllib.request,urllib.error
REPO='mariancradulescu/mxm-quant-greenfield'
REPO_ID=1374181010
OWNER_ID=322088485
APP_ID=5343530
INSTALLATION_ID=172030470
CODE_BRANCH='mxm-o04-issuer-code-v1'
ENVIRONMENT='mxm-o04-staging-issuer'
AUTH_REF='refs/heads/mxm-o04-stage-authority-v1'
AUD='mxm-o04-acceptor:1374181010:5343530:staging'
ISS='https://token.actions.githubusercontent.com'
class Refused(ValueError):pass
def need(ok,reason):
 if not ok:raise Refused(reason)
def b64(b):return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def un64(s):return base64.urlsafe_b64decode(s+'='*(-len(s)%4))
def canonical(o):return json.dumps(o,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def http(url,token=None,method='GET',data=None):
 headers={'Accept':'application/vnd.github+json','User-Agent':'MXM-O04-staging-only'}
 if token:headers['Authorization']='Bearer '+token
 if data is not None:headers['Content-Type']='application/json'
 req=urllib.request.Request(url,headers=headers,method=method,data=canonical(data) if data is not None else None)
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.load(r) if r.status!=204 else None
 except urllib.error.HTTPError as e:return e.code,None

def api(path,token=None,method='GET',data=None):return http('https://api.github.com/repos/'+REPO+'/'+path,token,method,data)
def der(tag,data):
 n=len(data);length=bytes([n]) if n<128 else bytes([128+(n.bit_length()+7)//8])+n.to_bytes((n.bit_length()+7)//8,'big')
 return bytes([tag])+length+data

def rsa_pem(jwk):
 def integer(s):
  raw=un64(s).lstrip(b'\0') or b'\0'
  if raw[0]&128:raw=b'\0'+raw
  return der(2,raw)
 rsa=der(48,integer(jwk['n'])+integer(jwk['e']))
 spki=der(48,bytes.fromhex('300d06092a864886f70d0101010500')+der(3,b'\0'+rsa))
 return b'-----BEGIN PUBLIC KEY-----\n'+base64.encodebytes(spki)+b'-----END PUBLIC KEY-----\n'

def openssl_verify(public,message,signature):
 with tempfile.TemporaryDirectory() as d:
  d=pathlib.Path(d);(d/'public').write_bytes(public);(d/'msg').write_bytes(message);(d/'sig').write_bytes(signature)
  return subprocess.run(['openssl','dgst','-sha256','-verify',str(d/'public'),'-signature',str(d/'sig'),str(d/'msg')],capture_output=True).returncode==0

def verify_jwt(token,now=None):
 need(isinstance(token,str) and len(token)<24000,'OIDC_FORMAT')
 parts=token.split('.');need(len(parts)==3,'OIDC_FORMAT');header=json.loads(un64(parts[0]));claims=json.loads(un64(parts[1]))
 need(header.get('alg')=='RS256' and isinstance(header.get('kid'),str),'OIDC_ALGORITHM')
 # Trust ONLY the fixed issuer JWKS, never a caller-controlled jku/x5u.
 status,config=http(ISS+'/.well-known/openid-configuration');need(status==200 and config['issuer']==ISS,'OIDC_DISCOVERY')
 need(config['jwks_uri'].startswith(ISS+'/'),'OIDC_JWKS_ORIGIN')
 status,jwks=http(config['jwks_uri']);need(status==200,'OIDC_JWKS')
 keys=[k for k in jwks['keys'] if k.get('kid')==header['kid'] and k.get('kty')=='RSA'];need(len(keys)==1,'OIDC_KEY')
 need(openssl_verify(rsa_pem(keys[0]),(parts[0]+'.'+parts[1]).encode(),un64(parts[2])),'OIDC_SIGNATURE')
 now=int(time.time()) if now is None else now
 need(claims.get('iss')==ISS and claims.get('aud')==AUD,'OIDC_ISSUER_AUDIENCE')
 need(type(claims.get('exp')) is int and type(claims.get('nbf')) is int and type(claims.get('iat')) is int and claims['nbf']<=now<claims['exp'] and 0<=now-claims['iat']<=600,'OIDC_TIME')
 return claims

def validate_workload(claims,expected_sha,expected_attempt):
 checks={'repository':REPO,'repository_id':str(REPO_ID),'repository_owner_id':str(OWNER_ID),
  'actor_id':str(OWNER_ID),'ref':'refs/heads/'+CODE_BRANCH,'sha':expected_sha,
  'event_name':'push','environment':ENVIRONMENT,'runner_environment':'github-hosted',
  'workflow_ref':REPO+'/.github/workflows/mxm-o042-entry.yml@refs/heads/'+CODE_BRANCH,
  'workflow_sha':expected_sha,'job_workflow_ref':REPO+'/.github/workflows/mxm-o042-issuer.yml@refs/heads/'+CODE_BRANCH,
  'job_workflow_sha':expected_sha,'run_attempt':str(expected_attempt)}
 for k,v in checks.items():need(str(claims.get(k,''))==v,'WORKLOAD_'+k.upper())
 need(str(claims.get('run_id','')).isdigit(),'WORKLOAD_RUN_ID')
 return {k:claims[k] for k in list(checks)+['run_id']}

def authenticated_workload():
 native=os.environ['GH_TOKEN'];status,ref=api('git/ref/heads/'+CODE_BRANCH,native);need(status==200,'CODE_REF')
 source=ref['object']['sha'];status,run=api('actions/runs/'+os.environ['GITHUB_RUN_ID'],native)
 need(status==200 and run['head_sha']==source and run['head_branch']==CODE_BRANCH and run['event']=='push','RUN_SOURCE')
 rule_id=os.environ.get('CODE_FREEZE_RULE_ID','')
 need(rule_id.isdigit(),'CODE_FREEZE_NOT_CONFIGURED')
 status,rule=api('rulesets/'+rule_id,native)
 need(status==200 and rule['enforcement']=='active' and rule['conditions']['ref_name']=={'include':['refs/heads/'+CODE_BRANCH],'exclude':[]} and {'creation','update'}<={r['type'] for r in rule['rules']},'CODE_FREEZE')
 status,acl=api('rulesets/25231211',native)
 need(status==200 and acl['enforcement']=='active' and acl['conditions']['ref_name']=={'include':[AUTH_REF],'exclude':[]} and {r['type'] for r in acl['rules']}=={'creation','update'},'AUTHORITY_ACL')
 requrl=os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']
 parsed=urllib.parse.urlsplit(requrl)
 need(parsed.scheme=='https' and parsed.hostname and parsed.hostname.endswith('.actions.githubusercontent.com') and parsed.username is None and parsed.password is None,'OIDC_REQUEST_ORIGIN')
 request=urllib.request.Request(requrl+('&' if '?' in requrl else '?')+'audience='+urllib.parse.quote(AUD,safe=''),headers={'Authorization':'Bearer '+os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
 with urllib.request.urlopen(request,timeout=30) as r:token=json.load(r)['value']
 claims=verify_jwt(token);public=validate_workload(claims,source,os.environ['GITHUB_RUN_ATTEMPT'])
 need(public['run_id']==os.environ['GITHUB_RUN_ID'],'WORKLOAD_RUN_MISMATCH')
 need(run['run_attempt']==int(public['run_attempt']) and run['actor']['id']==OWNER_ID,'RUN_ATTEMPT_ACTOR')
 public['oidc_token_sha256']=sha(token.encode());public['code_freeze_ruleset']=int(rule_id)
 del token
 return public
