"""Bounded broker auth only. The request allowlist excludes all market history/orders.
Hosted Actions may consume a separately supplied access token, NEVER refresh a token.
A durable private token checkpoint is required before enabling future refresh.
"""
import os,json,hashlib,argparse
from pathlib import Path
from .read_only_auth_presence_v1 import NAMES
EXPECTED_FINGERPRINT='b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636'
ALLOWED=frozenset(['ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq','ProtoOAAccountAuthReq','ProtoOATraderReq','ProtoOAAssetListReq'])
class PreflightRejected(Exception):pass

def fingerprint(account_id):return hashlib.sha256(f'ctrader-account:{int(account_id)}'.encode('ascii')).hexdigest()
def require_message(message):
 if type(message).__name__ not in ALLOWED:raise PreflightRejected('REQUEST_NOT_ON_AUTH_ONLY_ALLOWLIST')
def require_view(accounts):
 from m6.ctrader_proto.OpenApiModelMessages_pb2 import SCOPE_VIEW
 if not accounts.HasField('permissionScope') or accounts.permissionScope!=SCOPE_VIEW:raise PreflightRejected('TOKEN_SCOPE_NOT_EXPLICIT_VIEW_ONLY')
def run(client_id,client_secret,access_token,account_id,transport=None):
 from m6.ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
 from m6.ctrader_transport import StdlibCTraderTransport
 if fingerprint(account_id)!=EXPECTED_FINGERPRINT:raise PreflightRejected('EXPECTED_ACCOUNT_SECRET_FINGERPRINT_MISMATCH')
 tr=transport or StdlibCTraderTransport(response_timeout=15,connect_timeout=10)
 result={'application_auth_pass':False,'account_list_retrieved':False,'exact_account_match':False,'account_auth_pass':False,'read_only_scope_proven':False,'orders_placed':False,'market_history_acquired':False,'refresh_attempted':False,'allowlist':sorted(ALLOWED),'account_fingerprint_sha256':EXPECTED_FINGERPRINT}
 def send(msg,expected):
  require_message(msg);res=tr.request(msg,timeout=15)
  if not isinstance(res,expected):raise PreflightRejected('UNEXPECTED_BROKER_RESPONSE')
  return res
 try:
  send(m.ProtoOAApplicationAuthReq(clientId=client_id,clientSecret=client_secret),m.ProtoOAApplicationAuthRes);result['application_auth_pass']=True
  accounts=send(m.ProtoOAGetAccountListByAccessTokenReq(accessToken=access_token),m.ProtoOAGetAccountListByAccessTokenRes);result['account_list_retrieved']=True
  require_view(accounts);result['read_only_scope_proven']=True
  matches=[a for a in accounts.ctidTraderAccount if int(a.ctidTraderAccountId)==int(account_id) and a.HasField('isLive') and a.isLive]
  if len(matches)!=1:raise PreflightRejected('EXACT_LIVE_ACCOUNT_NOT_FOUND')
  result['exact_account_match']=True
  auth=send(m.ProtoOAAccountAuthReq(ctidTraderAccountId=int(account_id),accessToken=access_token),m.ProtoOAAccountAuthRes)
  if int(auth.ctidTraderAccountId)!=int(account_id):raise PreflightRejected('ACCOUNT_AUTH_ID_MISMATCH')
  result['account_auth_pass']=True
  trader=send(m.ProtoOATraderReq(ctidTraderAccountId=int(account_id)),m.ProtoOATraderRes).trader
  if int(trader.ctidTraderAccountId)!=int(account_id):raise PreflightRejected('TRADER_ID_MISMATCH')
  if not trader.HasField('brokerName') or 'pepperstone' not in trader.brokerName.lower() or 'europe' not in trader.brokerName.lower():raise PreflightRejected('BROKER_REGION_NOT_VERIFIED')
  if not trader.HasField('accountType') or trader.accountType!=e.HEDGED:raise PreflightRejected('ACCOUNT_NOT_EXPLICIT_HEDGED')
  if not trader.HasField('totalMarginCalculationType') or trader.totalMarginCalculationType!=e.MAX:raise PreflightRejected('MARGIN_MODE_NOT_MAX')
  if not trader.HasField('swapFree') or trader.swapFree:raise PreflightRejected('SWAP_FREE_STATE_MISMATCH')
  assets=send(m.ProtoOAAssetListReq(ctidTraderAccountId=int(account_id)),m.ProtoOAAssetListRes)
  if not any(a.assetId==trader.depositAssetId and a.name=='EUR' for a in assets.asset):raise PreflightRejected('ACCOUNT_CURRENCY_NOT_EUR')
  # Trader accessRights describes account status; OAuth permissionScope controls
  # this application's authority. SCOPE_TRADE is rejected before AccountAuth.
  result.update({'status':'PROVEN_MACHINE_SIDE_READ_ONLY_AUTH_ONLY','auth_proven':True,'account_currency':'EUR','environment':'Pepperstone Europe LIVE','account_type':'HEDGED','margin_mode':'MAX','request_count':5})
  return result
 finally:tr.close()

def main(out):
 missing=[n for n in NAMES if not os.environ.get(n,'').strip()]
 result={'status':'USER_SECURITY_ACTION_REQUIRED','exact_missing_secret_names':missing,'auth_proven':False,'broker_contact':False,'orders_placed':False,'market_history_acquired':False,'refresh_attempted':False,'source_head':os.environ.get('GITHUB_SHA')}
 if not missing:
  access=os.environ.get('CTRADER_ACCESS_TOKEN','').strip()
  if not access:result['status']='SAFE_ACCESS_TOKEN_OR_PRIVATE_DURABLE_ROTATION_CHECKPOINT_REQUIRED'
  else:
   try:result.update(run(os.environ['CTRADER_CLIENT_ID'],os.environ['CTRADER_CLIENT_SECRET'],access,int(os.environ['CTRADER_EXPECTED_ACCOUNT_ID'])));result['broker_contact']=True
   except Exception as exc:
    # Broker/transport exception text can contain values. Publish only fixed codes.
    result.update({'status':'PREFLIGHT_REJECTED','broker_contact':True,'safe_reason':str(exc) if isinstance(exc,PreflightRejected) else type(exc).__name__})
 Path(out).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
