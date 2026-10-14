"""Synthetic tests only. No broker contacts."""
import errno,os,socket,unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from research_core_v4.dom_live_probe_20261013_v1.test_live_v1 import AID,FP,quote,dom,stamp,Socket
from research_core_v4.dom_information_20261014_v1.live_adapter_v1 import InformationTransport,error_detail
from research_core_v4.dom_information_20261014_v1.information_v1 import InformationBook
from m6.ctrader_transport import encode_envelope,TransportError
from m6.ctrader_proto import OpenApiMessages_pb2 as m
RULES={'warmup_seconds':0,'bin_seconds':300,'maximum_state_age_seconds':2,'minimum_fresh_complete_seconds':2,'minimum_supported_bins':1,'minimum_fixed_bbo_quantity_events_per_side_bin':1}
class Clock:
    def __init__(self):self.t=0.
    def __call__(self):return self.t
class TimedSocket(Socket):
    def __init__(self,clock,buffer=b'',mode='traffic'):super().__init__(buffer);self.clock=clock;self.mode=mode;self.timeout=0
    def settimeout(self,v):self.timeout=v
    def recv(self,n):
        if self.mode=='absent':self.clock.t+=self.timeout;raise socket.timeout()
        if self.mode=='error':raise ConnectionResetError(errno.ECONNRESET,'test reset')
        self.clock.t+=.6
        return super().recv(n)
def transport(mode='traffic',buffer=b''):
    clock=Clock();now=datetime.now(timezone.utc);markers=[]
    t=InformationTransport(start_utc=now-timedelta(seconds=1),end_utc=now+timedelta(minutes=15),account_fingerprint=FP,event_handler=lambda *x:None,marker_handler=markers.append,clock=clock)
    t._sock=TimedSocket(clock,buffer,mode);t.connection_epochs=1;t.connection_attempted=True;t.contact_deadline=900;t.selected={1};t.expected_events={'ProtoOADepthEvent'};t.next_heartbeat=10
    return t,clock,markers
class Tests(unittest.TestCase):
    def test_continuous_traffic_sends_periodic_heartbeat(self):
        t,c,_=transport(buffer=encode_envelope(dom([quote(1,'bid',100,100)]))*30)
        for i in range(25):t.receive_envelope(deadline=100)
        self.assertGreaterEqual(len(t.heartbeat_stamps),2)
        self.assertLessEqual(max(x['lateness_seconds'] for x in t.heartbeat_stamps),.61)
    def test_absent_traffic_heartbeats_and_finite_deadline(self):
        t,c,_=transport(mode='absent')
        with self.assertRaises(TimeoutError):t.receive_envelope(deadline=31)
        self.assertEqual(len(t.heartbeat_stamps),3);self.assertLessEqual(c.t,31)
    def test_real_reset_errno_and_socket_saved(self):
        t,c,markers=transport(mode='error')
        with self.assertRaises(TransportError) as e:t.receive_envelope(deadline=5)
        self.assertIsInstance(e.exception.__cause__,ConnectionResetError)
        self.assertEqual(t.private_errors[0]['exception_chain'][0]['errno'],errno.ECONNRESET)
        self.assertFalse(t.connected);self.assertTrue(any(x['kind']=='INTERRUPTION' for x in markers))
    def test_partial_frame_not_resumed(self):
        t,c,_=transport(buffer=b'\x00\x00')
        with self.assertRaises(TransportError):t.receive_envelope(deadline=5)
        self.assertEqual(t.private_errors[0]['partial_frame_bytes'],2)
        with self.assertRaises(Exception):t.connect()
    def test_cleanup_finite_and_closed(self):
        a=m.ProtoOAUnsubscribeDepthQuotesRes(ctidTraderAccountId=AID);b=m.ProtoOAUnsubscribeSpotsRes(ctidTraderAccountId=AID)
        t,c,marks=transport(buffer=encode_envelope(a,'mxm-dom-live-000000000001')+encode_envelope(b,'mxm-dom-live-000000000002'))
        sock=t._sock;result=t.unsubscribe_all(AID)
        self.assertTrue(sock.closed);self.assertEqual(len(result),2);self.assertEqual(marks[-1]['kind'],'CLEANUP_COMPLETE')
    def test_secret_values_removed(self):
        with patch.dict(os.environ,{'CTRADER_ACCESS_TOKEN':'example-unique-token'}):
            self.assertNotIn('example-unique-token',str(error_detail(RuntimeError('failed example-unique-token'))))
    def book(self):return InformationBook(1,5,start_utc=datetime(2026,1,1,tzinfo=timezone.utc),rules=RULES)
    def state(self,b,n,sizes=(100,200,300,400,500,600),shift=0):
        items=[quote(i+1,'bid' if i<3 else 'ask',(100-i if i<3 else 101+i-3)+shift,s) for i,s in enumerate(sizes)]
        b.depth_event(dom(items),stamp(n))
    def test_fixed_price_quantity_bid_ask_separated(self):
        b=self.book();self.state(b,1);self.state(b,2,(150,200,300,400,500,600));self.state(b,3,(150,200,300,450,500,600));b.finish(4_000_000_000)
        x=b.summary()['information'];t=x['totals']
        self.assertEqual(t['bid_only_quantity_events'],1);self.assertEqual(t['ask_only_quantity_events'],1)
        self.assertEqual(t['bid_same_price_quantity_changes'],1);self.assertEqual(t['ask_same_price_quantity_changes'],1)
        self.assertTrue(x['verdict'].endswith('FOR_SEPARATE_STUDY_DESIGN'))
    def test_price_ladder_translation_not_independent_quantity(self):
        b=self.book();self.state(b,1);self.state(b,2,shift=10)
        t=b.summary()['information']['totals'];self.assertEqual(t['price_ladder_only_compatible_events'],1)
        self.assertEqual(t.get('quantity_distinct_from_rank_size_preserving_ladder_events',0),0)
    def test_stale_or_invalid_state_excluded_and_no_fill_across_gap(self):
        b=self.book();self.state(b,1);self.state(b,10,(150,200,300,400,500,600))
        self.assertEqual(b.summary()['information']['totals'].get('valid_adjacent_pairs',0),0)
        self.assertEqual(b.valid_seconds,2)
        b.depth_event(dom(deletions=[999]),stamp(11));self.state(b,12)
        self.assertTrue(b.invalid_epoch);self.assertFalse(b.previous_valid)
    def test_rank_migration_not_fixed_rank_quantity(self):
        b=self.book();self.state(b,1);self.state(b,2,shift=1)
        self.assertGreater(sum(x['rank_migration_pairs'] for x in b.summary()['information']['rank_conditioned_quantity']),0)
    def test_warmup_prevents_pair_scoring(self):
        b=self.book();b.rules={**RULES,'warmup_seconds':120};self.state(b,1);self.state(b,2)
        self.assertEqual(b.summary()['information']['totals'].get('valid_adjacent_pairs',0),0)
if __name__=='__main__':unittest.main()
