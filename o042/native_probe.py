"""Real server negative using only the job's native token. Never App token."""
import json,os,pathlib
from . import identity as i

def negative(ref,candidate,create=False):
 native=os.environ['GH_TOKEN'];status,before=i.api('git/ref/'+ref.removeprefix('refs/'),native)
 i.need(status in (200,404),'BEFORE_READ');old=before['object']['sha'] if status==200 else None
 if create:
  status,_=i.api('git/refs',native,'POST',{'ref':ref,'sha':candidate})
 else:
  i.need(old is not None,'UPDATE_REQUIRES_EXISTING_REF')
  status,_=i.api('git/refs/'+ref.removeprefix('refs/'),native,'PATCH',{'sha':candidate,'force':False})
 after_status,after=i.api('git/ref/'+ref.removeprefix('refs/'),native)
 new=after['object']['sha'] if after_status==200 else None
 i.need(status in (403,422) and old==new,'SERVER_DID_NOT_REJECT_GENERIC_WRITE')
 return {'ref':ref,'server_HTTP':status,'before':old,'after':new,'readback_HTTP':after_status,'credential':os.environ.get('PROBE_ROLE','NATIVE_TOKEN')}

def main():
 native=os.environ['GH_TOKEN'];results=[]
 # Known preexisting QUARANTINED synthetic tree, no workflows.
 status,ref=i.api('git/ref/'+i.AUTH_REF.removeprefix('refs/'),native)
 if status==404:results.append(negative(i.AUTH_REF,'b3831d31f05a60413a2ae086c4e6dc2f9a125cd6',True))
 else:
  i.need(status==200,'AUTH_READ');old=ref['object']['sha'];status,c=i.api('git/commits/'+old,native);i.need(status==200,'COMMIT_READ')
  status,candidate=i.api('git/commits',native,'POST',{'message':'SYNTHETIC_ONLY unauthorized native token forward candidate','tree':c['tree']['sha'],'parents':[old]})
  if status==201:results.append(negative(i.AUTH_REF,candidate['sha']))
  else:
   i.need(os.environ.get('PROBE_ROLE')=='CONTENTS_READ' and status==403,'READONLY_OBJECT_CREATE')
   # A valid forward child is not necessary to prove read-only cannot create Git objects.
   results.append({'server_HTTP':403,'operation':'CREATE_COMMIT','credential':'CONTENTS_READ','before':old,'after':i.api('git/ref/'+i.AUTH_REF.removeprefix('refs/'),native)[1]['object']['sha']})
 if os.environ.get('PROBE_ROLE')=='CONTENTS_WRITE':
  status,ref=i.api('git/ref/heads/'+i.CODE_BRANCH,native);old=ref['object']['sha'];status,c=i.api('git/commits/'+old,native)
  status,candidate=i.api('git/commits',native,'POST',{'message':'SYNTHETIC_ONLY immutable issuer code write denial candidate','tree':c['tree']['sha'],'parents':[old]});i.need(status==201,'CODE_CANDIDATE')
  results.append(negative('refs/heads/'+i.CODE_BRANCH,candidate['sha']))
 out={'schema':'mxm.o042.native-negative.v1','run':os.environ['GITHUB_RUN_ID'],'attempt':os.environ['GITHUB_RUN_ATTEMPT'],'job':os.environ['GITHUB_JOB'],'source_SHA':os.environ['GITHUB_SHA'],'results':results,'OWNER_ACCEPTS_NEW_CHECKPOINTS':False}
 pathlib.Path('verification').mkdir(exist_ok=True);pathlib.Path('verification/o042-'+os.environ['GITHUB_JOB']+'.json').write_bytes(i.canonical(out)+b'\n');print(i.canonical(out).decode())
if __name__=='__main__':main()
