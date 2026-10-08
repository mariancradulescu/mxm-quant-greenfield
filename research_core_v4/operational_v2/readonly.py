"""Accepted cTrader transport/auth/decoder route fenced to five read-only types."""
import hashlib,json,struct,time
from m6.ctrader_transport import StdlibCTraderTransport,decode_envelope
from m6.ctrader_proto import OpenApiMessages_pb2 as m
from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoHeartbeatEvent
from research_core_v4 import shallow_m5_support_v2 as decoder
from research_core_v4 import shallow_m5_support_v2_boundary_v4 as boundary
from research_core_v4 import shallow_m5_support_v2_production as route
ALLOWED={int(m.ProtoOAApplicationAuthReq().payloadType),int(m.ProtoOAGetAccountListByAccessTokenReq().payloadType),int(m.ProtoOAAccountAuthReq().payloadType),int(ProtoHeartbeatEvent().payloadType),2137}
class ReadOnlyTransport(StdlibCTraderTransport):
 def __init__(self,**kw):super().__init__(**kw);self.ledger=[];self.bound_ctx=None;self.stage=None
 def _send_bytes(self,frame):
  assert len(frame)>=4 and struct.unpack('!I',frame[:4])[0]==len(frame)-4
  e=decode_envelope(frame[4:]);pt=int(e.payloadType)
  if pt not in ALLOWED:raise PermissionError('ZERO_ORDER_CAPABILITY_PAYLOAD_BLOCKED')
  rec={'sequence':len(self.ledger)+1,'payload_type':pt,'send_attempt_epoch_ns':time.time_ns(),'send_returned':False,'stage':self.stage}
  if pt==2137:
   assert self.bound_ctx is not None;req=decoder.ProtoOAGetTrendbarsReqV2();req.ParseFromString(e.payload);decoder.validate_request(req,self.bound_ctx);assert str(e.clientMsgId)==self.bound_ctx.client_msg_id
   rec.update({'symbol_id':self.bound_ctx.symbol_id,'from_ms':self.bound_ctx.from_ms,'to_ms':self.bound_ctx.to_ms,'count':5000,'period':5,'client_msg_id':str(e.clientMsgId),'account_fingerprint_sha256':route.ACCOUNT_FINGERPRINT_SHA256})
  self.ledger.append(rec);super()._send_bytes(frame);rec['send_returned']=True

def send_page(tr,ctx,digits,limiter):
 tr.bound_ctx=ctx;req=route.build_history_request(ctx)
 from m6.ctrader_transport import encode_envelope
 from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
 e=ProtoMessage(payloadType=2137,payload=req.SerializeToString(),clientMsgId=ctx.client_msg_id);limiter.before_send();tr._send_bytes(encode_envelope(e));deadline=tr._clock()+tr.response_timeout
 while True:
  raw=tr.receive_envelope(deadline=deadline)
  if int(raw.payloadType)==int(ProtoHeartbeatEvent().payloadType):tr.send_heartbeat();continue
  if not raw.HasField('clientMsgId') or str(raw.clientMsgId)!=ctx.client_msg_id:continue
  if int(raw.payloadType)==int(m.ProtoOAErrorRes().payloadType):
   err=m.ProtoOAErrorRes();err.ParseFromString(raw.payload);raise RuntimeError('BROKER_ERROR_'+str(err.errorCode))
  page=boundary.bind_and_normalize_response(raw,ctx=ctx,digits=digits)
  rec=next(x for x in reversed(tr.ledger) if x.get('client_msg_id')==ctx.client_msg_id)
  rec['response_sha256']=hashlib.sha256(raw.SerializeToString()).hexdigest();rec['response_geometry']=page.geometry.as_dict();rec['response_received_epoch_ns']=time.time_ns()
  return page
