"""Finite transport/book tests; fixtures are never broker evidence."""
import hashlib, unittest
from datetime import datetime,timedelta,timezone
from m6.ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as model
from m6.ctrader_transport import encode_envelope,ProtoMessage
try:
    from research_core_v4.dom_live_probe_20261013_v1.live_adapter_v1 import *
except ModuleNotFoundError:
    from live_adapter_v1 import *

AID=918273645
FP=hashlib.sha256(('ctrader-account:'+str(AID)).encode()).hexdigest()
def quote(identity,side,price,size):return model.ProtoOADepthQuote(id=identity,size=size,**{side:price})
def dom(items=(),deletions=(),sid=1):return m.ProtoOADepthEvent(ctidTraderAccountId=AID,symbolId=sid,newQuotes=items,deletedQuotes=deletions)
def stamp(n=1):return {'receive_utc':'2026-01-01T00:00:00+00:00','receive_monotonic_ns':n*1_000_000_000,'sequence':n,'connection_epoch':1}
class Socket:
    def __init__(self,buffer=b''):self.buffer=buffer;self.sent=[];self.closed=False
    def settimeout(self,value):pass
    def sendall(self,data):self.sent.append(data)
    def recv(self,n):part=self.buffer[:n];self.buffer=self.buffer[n:];return part
    def close(self):self.closed=True

def transport(buffer=b'', handler=None):
    now=datetime.now(timezone.utc)
    t=LiveReadOnlyTransport(start_utc=now-timedelta(seconds=1),end_utc=now+timedelta(minutes=10),
                          account_fingerprint=FP,event_handler=handler or (lambda *x:None))
    t._sock=Socket(buffer);t.connection_epochs=1;t.first_contact_mono=t._clock();t.contact_deadline=t._clock()+1200;t.selected={1}
    return t

class Tests(unittest.TestCase):
    def test_positive_contract_exact(self):
        self.assertEqual(len(ALLOWED),13)
        for name in ALLOWED:
            cls=PROTO_REGISTRY[next(k for k,c in PROTO_REGISTRY.items() if c.__name__==name)]
            # Enumerated names still require initialized protobuf fields.
            obj=cls()
            if not obj.IsInitialized():
                with self.assertRaises(LiveContractError):require_message(obj)
        self.assertEqual(require_message(PROTO_REGISTRY[next(k for k,c in PROTO_REGISTRY.items() if c.__name__=='ProtoHeartbeatEvent')]()),'ProtoHeartbeatEvent')
    def test_all_unenumerated_proto_classes_fail_before_wire(self):
        t=transport();sock=t._sock
        rejected=0
        for name in dir(m):
            cls=getattr(m,name)
            if name.startswith('Proto') and isinstance(cls,type) and name not in ALLOWED:
                with self.assertRaises(LiveContractError):t.request(cls())
                rejected+=1
        self.assertGreater(rejected,70);self.assertEqual(sock.sent,[])
    def test_lower_level_frame_cannot_bypass_contract(self):
        t=transport();sock=t._sock
        request=m.ProtoOANewOrderReq()
        envelope=ProtoMessage(payloadType=request.payloadType,payload=request.SerializePartialToString())
        with self.assertRaises(LiveContractError):t._send_bytes(encode_envelope(envelope))
        self.assertEqual(sock.sent,[])
    def test_interleaved_dom_and_spot_retained_before_correlated_ack(self):
        received=[]
        d=dom([quote(1,'bid',100000,100),quote(2,'ask',100010,200)])
        spot=m.ProtoOASpotEvent(ctidTraderAccountId=AID,symbolId=1,bid=100000,ask=100010,timestamp=1)
        ack=m.ProtoOASubscribeDepthQuotesRes(ctidTraderAccountId=AID)
        buffer=encode_envelope(d)+encode_envelope(spot)+encode_envelope(ack,'mxm-dom-live-000000000001')
        t=transport(buffer,lambda msg,st,en:received.append((type(msg).__name__,st['sequence'])))
        t.expected_events.add('ProtoOASpotEvent')
        req=m.ProtoOASubscribeDepthQuotesReq(ctidTraderAccountId=AID,symbolId=[1])
        self.assertIsInstance(t.request(req),m.ProtoOASubscribeDepthQuotesRes)
        self.assertEqual(received,[('ProtoOADepthEvent',1),('ProtoOASpotEvent',2)])
    def test_account_and_symbol_binding(self):
        t=transport()
        with self.assertRaises(LiveContractError):t.request(m.ProtoOASubscribeDepthQuotesReq(ctidTraderAccountId=AID+1,symbolId=[1]))
        with self.assertRaises(LiveContractError):t.request(m.ProtoOASubscribeDepthQuotesReq(ctidTraderAccountId=AID,symbolId=[2]))
        self.assertEqual(t._sock.sent,[])
    def test_book_initialization_incomplete_then_both_then_delete_replace(self):
        b=DepthBook(1,5);b.depth_event(dom([quote(1,'bid',100,100)]),stamp())
        self.assertEqual(b.summary()['initialization']['observed_bootstrap'],'INCOMPLETE_OR_UNOBSERVED')
        b.depth_event(dom([quote(2,'ask',101,200)]),stamp(2));self.assertIsNotNone(b.first_both)
        b.depth_event(dom([quote(1,'bid',100,300)]),stamp(3));self.assertEqual(b.quotes[1][2],300)
        b.depth_event(dom(deletions=[1]),stamp(4));self.assertNotIn(1,b.quotes)
        self.assertFalse(b.invalid_epoch)
    def test_unknown_deleted_id_and_ambiguous_overlap_detected(self):
        b=DepthBook(1,5);b.depth_event(dom(deletions=[999]),stamp());self.assertTrue(b.invalid_epoch)
        self.assertEqual(b.counts['unknown_deleted_ids'],1)
        b.depth_event(dom([quote(1,'bid',100,100)],deletions=[1]),stamp(2))
        self.assertEqual(b.counts['new_and_deleted_same_event_ids'],1)
    def test_disconnect_not_ignored(self):
        d=m.ProtoOAAccountDisconnectEvent(ctidTraderAccountId=AID)
        t=transport(encode_envelope(d))
        with self.assertRaises(LiveInterrupted):t.receive_envelope(deadline=t._clock()+1)
    def test_deadline_prevents_wire(self):
        t=transport();sock=t._sock;t.end_utc=t.now_utc()-timedelta(seconds=1)
        with self.assertRaises(LiveWindowEnded):t.request(m.ProtoOASubscribeDepthQuotesReq(ctidTraderAccountId=AID,symbolId=[1]))
        self.assertEqual(sock.sent,[])
    def test_unsubscribe_both_even_after_capture_deadline(self):
        a=m.ProtoOAUnsubscribeDepthQuotesRes(ctidTraderAccountId=AID)
        b=m.ProtoOAUnsubscribeSpotsRes(ctidTraderAccountId=AID)
        t=transport(encode_envelope(a,'mxm-dom-live-000000000001')+encode_envelope(b,'mxm-dom-live-000000000002'))
        sock=t._sock;t.end_utc=t.now_utc()-timedelta(seconds=1)
        result=t.unsubscribe_all(AID)
        self.assertEqual(len(sock.sent),2);self.assertTrue(sock.closed)
        self.assertEqual(result['ProtoOAUnsubscribeDepthQuotesReq']['response_type'],'ProtoOAUnsubscribeDepthQuotesRes')
    def test_raw_events_after_capture_deadline_not_retained(self):
        received=[];t=transport(encode_envelope(dom([quote(1,'bid',1,1)])),lambda *x:received.append(x))
        t.expected_events={'ProtoOADepthEvent'};t.end_utc=t.now_utc()-timedelta(seconds=1)
        t.receive_envelope(deadline=t._clock()+1);self.assertEqual(received,[])

if __name__=='__main__':unittest.main()
