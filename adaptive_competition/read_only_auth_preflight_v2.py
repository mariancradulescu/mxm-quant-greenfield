"""One bounded authentication-only V2 attempt. No refresh or market-data capability.
Account identity derives exclusively from the frozen historical fingerprint.
No credential, raw protocol response, raw account ID or login is published.
"""
import argparse,hashlib,json,os,struct
from pathlib import Path
EXPECTED_FINGERPRINT='b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636'
REQUIRED=('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')
ALLOWED=frozenset(('ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq','ProtoOAAccountAuthReq','ProtoOATraderReq','ProtoOAAssetListReq'))
GATES=('application_auth_pass','account_list_retrieved','explicit_view_only_scope_pass','unique_historical_account_fingerprint_match','matched_account_live','account_auth_pass','broker_region_pass','hedged_account_pass','max_margin_mode_pass','non_swap_free_pass','eur_deposit_asset_pass')
FORBIDDEN_FLAGS=('orders_placed','account_mutation','market_history_acquired','subscriptions_created','refresh_attempted')
REASONS=frozenset(('NONE','REQUIRED_RUNTIME_SECRET_MISSING','APPLICATION_AUTH_FAILED','ACCESS_TOKEN_INVALID_OR_EXPIRED','ACCOUNT_LIST_FAILED','TOKEN_SCOPE_NOT_EXPLICIT_VIEW_ONLY','HISTORICAL_ACCOUNT_FINGERPRINT_NOT_FOUND','MULTIPLE_HISTORICAL_ACCOUNT_FINGERPRINT_MATCHES','MATCHED_ACCOUNT_NOT_LIVE','ACCOUNT_AUTH_FAILED','TRADER_REQUEST_FAILED','BROKER_REGION_NOT_VERIFIED','ACCOUNT_NOT_EXPLICIT_HEDGED','MARGIN_MODE_NOT_MAX','SWAP_FREE_STATE_MISMATCH','ASSET_LIST_REQUEST_FAILED','ACCOUNT_CURRENCY_NOT_EUR','TRANSPORT_FAILURE','DISALLOWED_MESSAGE','SAFE_SCHEMA_VALIDATION_FAILED'))
class Rejected(Exception):
 def __init__(self,code):
  self.code=code if code in REASONS else 'SAFE_SCHEMA_VALIDATION_FAILED'
  super().__init__(self.code)
def fingerprint(account_id):return hashlib.sha256(f'ctrader-account:{int(account_id)}'.encode('ascii')).hexdigest()
def require_message(message):
 if type(message).__name__ not in ALLOWED:raise Rejected('DISALLOWED_MESSAGE')
def autodiscover(accounts,expected=EXPECTED_FINGERPRINT):
 from m6.ctrader_proto.OpenApiModelMessages_pb2 import SCOPE_VIEW
 if not accounts.HasField('permissionScope') or accounts.permissionScope!=SCOPE_VIEW:raise Rejected('TOKEN_SCOPE_NOT_EXPLICIT_VIEW_ONLY')
 matches=[a for a in accounts.ctidTraderAccount if fingerprint(a.ctidTraderAccountId)==expected]
 if not matches:raise Rejected('HISTORICAL_ACCOUNT_FINGERPRINT_NOT_FOUND')
 if len(matches)!=1:raise Rejected('MULTIPLE_HISTORICAL_ACCOUNT_FINGERPRINT_MATCHES')
 if not matches[0].HasField('isLive') or not matches[0].isLive:raise Rejected('MATCHED_ACCOUNT_NOT_LIVE')
 return int(matches[0].ctidTraderAccountId)
def make_transport():
 from m6.ctrader_transport import StdlibCTraderTransport,decode_envelope,PROTO_REGISTRY
 class AuthOnlyTransport(StdlibCTraderTransport):
  def request(self,message,**kwargs):require_message(message);return super().request(message,**kwargs)
  def _send_bytes(self,payload):
   if len(payload)<5 or struct.unpack('!I',payload[:4])[0]!=len(payload)-4:raise Rejected('DISALLOWED_MESSAGE')
   envelope=decode_envelope(payload[4:]);klass=PROTO_REGISTRY.get(envelope.payloadType)
   if klass is None or klass.__name__ not in ALLOWED:raise Rejected('DISALLOWED_MESSAGE')
   return super()._send_bytes(payload)
  def send_heartbeat(self):
   # Strict five-message contract: a delayed/heartbeat-demanding attempt fails.
   raise Rejected('TRANSPORT_FAILURE')
 return AuthOnlyTransport(connect_timeout=10,response_timeout=15)
def blank_result():
 return {**{g:False for g in GATES},**{k:False for k in FORBIDDEN_FLAGS},'status':'PREFLIGHT_FAILED_CLOSED','safe_reason':'NONE','auth_proven':False,'broker_contact_attempted':False,'transport_closed':False,'expected_account_fingerprint_sha256':EXPECTED_FINGERPRINT,'request_contact_flags':{k:False for k in sorted(ALLOWED)}}
def run(client_id,client_secret,access_token,transport=None,expected=EXPECTED_FINGERPRINT):
 from m6.ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
 result=blank_result();result['expected_account_fingerprint_sha256']=expected;tr=transport or make_transport()
 def send(msg,expected_type,failure):
  require_message(msg);result['request_contact_flags'][type(msg).__name__]=True;result['broker_contact_attempted']=True
  response=tr.request(msg,timeout=15)
  if isinstance(response,m.ProtoOAErrorRes):
   if response.errorCode in ('OA_AUTH_TOKEN_EXPIRED','OA_AUTH_TOKEN_INVALID','CH_ACCESS_TOKEN_INVALID','CH_ACCESS_TOKEN_EXPIRED'):raise Rejected('ACCESS_TOKEN_INVALID_OR_EXPIRED')
   raise Rejected(failure)
  if not isinstance(response,expected_type):raise Rejected(failure)
  return response
 try:
  send(m.ProtoOAApplicationAuthReq(clientId=client_id,clientSecret=client_secret),m.ProtoOAApplicationAuthRes,'APPLICATION_AUTH_FAILED');result['application_auth_pass']=True
  accounts=send(m.ProtoOAGetAccountListByAccessTokenReq(accessToken=access_token),m.ProtoOAGetAccountListByAccessTokenRes,'ACCOUNT_LIST_FAILED');result['account_list_retrieved']=True
  if not accounts.HasField('permissionScope') or accounts.permissionScope!=e.SCOPE_VIEW:raise Rejected('TOKEN_SCOPE_NOT_EXPLICIT_VIEW_ONLY')
  result['explicit_view_only_scope_pass']=True
  # Uniqueness is checked before LIVE, retaining the exact reason in safe gates.
  matches=[a for a in accounts.ctidTraderAccount if fingerprint(a.ctidTraderAccountId)==expected]
  if not matches:raise Rejected('HISTORICAL_ACCOUNT_FINGERPRINT_NOT_FOUND')
  if len(matches)!=1:raise Rejected('MULTIPLE_HISTORICAL_ACCOUNT_FINGERPRINT_MATCHES')
  result['unique_historical_account_fingerprint_match']=True
  account_id=autodiscover(accounts,expected);result['matched_account_live']=True
  auth=send(m.ProtoOAAccountAuthReq(ctidTraderAccountId=account_id,accessToken=access_token),m.ProtoOAAccountAuthRes,'ACCOUNT_AUTH_FAILED')
  if auth.ctidTraderAccountId!=account_id:raise Rejected('ACCOUNT_AUTH_FAILED')
  result['account_auth_pass']=True
  trader=send(m.ProtoOATraderReq(ctidTraderAccountId=account_id),m.ProtoOATraderRes,'TRADER_REQUEST_FAILED').trader
  if trader.ctidTraderAccountId!=account_id:raise Rejected('TRADER_REQUEST_FAILED')
  if not trader.HasField('brokerName') or 'pepperstone' not in trader.brokerName.lower() or 'europe' not in trader.brokerName.lower():raise Rejected('BROKER_REGION_NOT_VERIFIED')
  result['broker_region_pass']=True
  if not trader.HasField('accountType') or trader.accountType!=e.HEDGED:raise Rejected('ACCOUNT_NOT_EXPLICIT_HEDGED')
  result['hedged_account_pass']=True
  if not trader.HasField('totalMarginCalculationType') or trader.totalMarginCalculationType!=e.MAX:raise Rejected('MARGIN_MODE_NOT_MAX')
  result['max_margin_mode_pass']=True
  if not trader.HasField('swapFree') or trader.swapFree:raise Rejected('SWAP_FREE_STATE_MISMATCH')
  result['non_swap_free_pass']=True
  assets=send(m.ProtoOAAssetListReq(ctidTraderAccountId=account_id),m.ProtoOAAssetListRes,'ASSET_LIST_REQUEST_FAILED')
  if assets.ctidTraderAccountId!=account_id:raise Rejected('ASSET_LIST_REQUEST_FAILED')
  matches=[a for a in assets.asset if a.assetId==trader.depositAssetId and a.name=='EUR']
  if len(matches)!=1:raise Rejected('ACCOUNT_CURRENCY_NOT_EUR')
  result['eur_deposit_asset_pass']=True;result['status']='PROVEN_MACHINE_SIDE_READ_ONLY_AUTH_ONLY';result['auth_proven']=True
 except Rejected as exc:result['safe_reason']=exc.code
 except Exception:result['safe_reason']='TRANSPORT_FAILURE'
 finally:
  try:tr.close();result['transport_closed']=True
  except Exception:result['safe_reason']='TRANSPORT_FAILURE';result['auth_proven']=False;result['status']='PREFLIGHT_FAILED_CLOSED'
 return result

def presence():return {'required_runtime_secret_presence':{n:bool(os.environ.get(n)) for n in REQUIRED},'refresh_token_present':bool(os.environ.get('CTRADER_REFRESH_TOKEN')),'refresh_token_used':False}
def validate_safe(result):
 base=blank_result();optional={'required_runtime_secret_presence','refresh_token_present','refresh_token_used','exact_source_head','execution_head','arm_sha256','implementation_sha256','workflow_sha256'}
 if not set(result)<=set(base)|optional:raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
 for k in GATES+FORBIDDEN_FLAGS+('auth_proven','broker_contact_attempted','transport_closed'):
  if type(result.get(k)) is not bool:raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
 if any(result[k] for k in FORBIDDEN_FLAGS):raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
 if result.get('safe_reason') not in REASONS or result.get('status') not in ('PREFLIGHT_FAILED_CLOSED','PROVEN_MACHINE_SIDE_READ_ONLY_AUTH_ONLY'):raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
 if result['auth_proven']!= (result['status']=='PROVEN_MACHINE_SIDE_READ_ONLY_AUTH_ONLY'):raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
 if result['auth_proven'] and (not all(result[k] for k in GATES) or not result['transport_closed']):raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
 if result['expected_account_fingerprint_sha256']!=EXPECTED_FINGERPRINT:raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
 if set(result['request_contact_flags'])!=ALLOWED or not all(type(v) is bool for v in result['request_contact_flags'].values()):raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
 for k in ('required_runtime_secret_presence',):
  if k in result and (set(result[k])!=set(REQUIRED) or not all(type(v) is bool for v in result[k].values())):raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
 for k in ('refresh_token_present','refresh_token_used'):
  if k in result and (type(result[k]) is not bool or (k=='refresh_token_used' and result[k])):raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
 for k in optional-{'required_runtime_secret_presence','refresh_token_present','refresh_token_used'}:
  if k in result:
   v=result[k];size=40 if k in ('exact_source_head','execution_head') else 64
   if not isinstance(v,str) or len(v)!=size or any(c not in '0123456789abcdef' for c in v):raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
 return True

def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['presence','auth']);p.add_argument('--out',type=Path,required=True);p.add_argument('--presence-file',type=Path);a=p.parse_args()
 if a.phase=='presence':result=presence()
 else:
  from .validate_auth_arm_v2 import verify_arm
  arm=verify_arm();observed=json.loads(a.presence_file.read_text())
  # This process MUST NOT inherit refresh-token material.
  if 'CTRADER_REFRESH_TOKEN' in os.environ:raise Rejected('SAFE_SCHEMA_VALIDATION_FAILED')
  available={n:bool(os.environ.get(n)) for n in REQUIRED}
  if not all(available.values()):result=blank_result();result['safe_reason']='REQUIRED_RUNTIME_SECRET_MISSING';result['transport_closed']=True
  else:result=run(*(os.environ[n] for n in REQUIRED))
  result.update({'required_runtime_secret_presence':available,'refresh_token_present':observed['refresh_token_present'],'refresh_token_used':False,'exact_source_head':arm['exact_source_head'],'execution_head':os.environ['GITHUB_SHA'],'arm_sha256':hashlib.sha256(Path('adaptive_competition/state/READ_ONLY_AUTH_PREFLIGHT_ARM_V2.json').read_bytes()).hexdigest(),'implementation_sha256':arm['implementation_sha256'],'workflow_sha256':arm['workflow_sha256']});validate_safe(result)
 a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
