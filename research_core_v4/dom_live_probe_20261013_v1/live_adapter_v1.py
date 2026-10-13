"""Independent owner-authorized live-data contract; historical guards unchanged."""
import base64, hashlib, struct, time
from collections import Counter
from datetime import datetime, timezone
from m6.ctrader_transport import StdlibCTraderTransport, ProtoMessage, PROTO_REGISTRY, encode_envelope, extract_payload
from m6.ctrader_proto import OpenApiMessages_pb2 as m

ALLOWED = frozenset({
    'ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq','ProtoOAAccountAuthReq',
    'ProtoOATraderReq','ProtoOAAssetListReq','ProtoOASymbolsListReq','ProtoOASymbolByIdReq',
    'ProtoOAExpectedMarginReq','ProtoOASubscribeDepthQuotesReq','ProtoOAUnsubscribeDepthQuotesReq',
    'ProtoOASubscribeSpotsReq','ProtoOAUnsubscribeSpotsReq','ProtoHeartbeatEvent'})
LIVE = frozenset({'ProtoOASubscribeDepthQuotesReq','ProtoOAUnsubscribeDepthQuotesReq',
                  'ProtoOASubscribeSpotsReq','ProtoOAUnsubscribeSpotsReq'})
CLEANUP = frozenset({'ProtoOAUnsubscribeDepthQuotesReq','ProtoOAUnsubscribeSpotsReq','ProtoHeartbeatEvent'})
EVENTS = frozenset({'ProtoOADepthEvent','ProtoOASpotEvent'})

class LiveContractError(RuntimeError): pass
class LiveWindowEnded(LiveContractError): pass
class LiveInterrupted(LiveContractError): pass

def require(condition, code):
    if not condition: raise LiveContractError(code)

def require_message(message):
    name=type(message).__name__
    require(name in ALLOWED,'LIVE_OUTBOUND_NOT_ENUMERATED:'+name)
    require(message.IsInitialized(),'LIVE_OUTBOUND_REQUIRED_FIELDS:'+name)
    return name

class LiveReadOnlyTransport(StdlibCTraderTransport):
    """One inherited TLS connection, new bounded positive contract on EVERY frame.

    request is additive and receives interleaved events rather than ignoring them.
    No historical capture request, order, refresh, account mutation or reconnect.
    """
    def __init__(self, *, start_utc, end_utc, account_fingerprint, event_handler, **kwargs):
        super().__init__(**kwargs)
        self.start_utc=start_utc;self.end_utc=end_utc;self.account_fingerprint=account_fingerprint
        self.event_handler=event_handler;self.selected=set();self.expected_events=set()
        self.receipt_sequence=0;self.last_receipt_ns=None;self.wire_counts=Counter()
        self.receive_counts=Counter();self.cleanup=False;self.cleanup_end=0
        self.first_contact_mono=None;self.contact_deadline=None;self.last_host_utc=None
        self.connection_epochs=0;self.market_capture_enabled=True

    def now_utc(self): return datetime.now(timezone.utc)

    def temporal_check(self, name=None):
        now=self.now_utc()
        require(self.last_host_utc is None or now>=self.last_host_utc,'HOST_CLOCK_BACKWARDS')
        self.last_host_utc=now
        if self.cleanup:
            require(name in CLEANUP,'CLEANUP_REQUEST_SCOPE')
            if self._clock()>=self.cleanup_end: raise LiveWindowEnded('CLEANUP_DEADLINE')
            return
        if now<self.start_utc or now>=self.end_utc: raise LiveWindowEnded('ABSOLUTE_TECHNICAL_WINDOW')
        if self.contact_deadline is not None and self._clock()>=self.contact_deadline:
            raise LiveWindowEnded('TWENTY_MINUTE_CONTACT_CAP')

    def connect(self):
        require(self.connection_epochs==0,'RECONNECT_NOT_AUTHORIZED')
        self.temporal_check()
        self.first_contact_mono=self._clock();self.contact_deadline=self.first_contact_mono+1200
        super().connect();self.connection_epochs+=1

    def validate(self,message):
        name=require_message(message);self.temporal_check(name)
        if hasattr(message,'ctidTraderAccountId'):
            fp=hashlib.sha256(('ctrader-account:'+str(message.ctidTraderAccountId)).encode('ascii')).hexdigest()
            require(fp==self.account_fingerprint,'LIVE_ACCOUNT_FINGERPRINT')
        if name in LIVE:
            ids=list(message.symbolId)
            require(0<len(ids)<=3 and len(ids)==len(set(ids)) and set(ids)<=self.selected,'LIVE_SYMBOL_SCOPE')
        elif name=='ProtoOASymbolByIdReq':
            require(0<len(message.symbolId)<=3 and set(message.symbolId)<=self.selected,'METADATA_SYMBOL_SCOPE')
        elif name=='ProtoOAExpectedMarginReq':
            require(message.symbolId in self.selected and len(message.volume)==1,'MARGIN_SYMBOL_SCOPE')
        return name

    def _send_bytes(self, framed):
        # Lower-level callers cannot bypass this independent per-frame control.
        require(len(framed)>=4 and struct.unpack('!I',framed[:4])[0]==len(framed)-4,'LIVE_FRAME_LENGTH')
        envelope=ProtoMessage();envelope.ParseFromString(framed[4:])
        require(envelope.IsInitialized(),'LIVE_ENVELOPE_REQUIRED_FIELDS')
        message=extract_payload(envelope);name=self.validate(message)
        super()._send_bytes(framed);self.wire_counts[name]+=1

    def receive_envelope(self, *, deadline):
        envelope=super().receive_envelope(deadline=deadline)
        now=self.now_utc();ns=time.monotonic_ns()
        require(self.last_receipt_ns is None or ns>=self.last_receipt_ns,'RECEIPT_CLOCK_BACKWARDS')
        self.last_receipt_ns=ns;self.receipt_sequence+=1
        message=extract_payload(envelope);name=type(message).__name__;self.receive_counts[name]+=1
        if name in EVENTS:
            require(hashlib.sha256(('ctrader-account:'+str(message.ctidTraderAccountId)).encode('ascii')).hexdigest()==self.account_fingerprint,'EVENT_ACCOUNT_FINGERPRINT')
            require(int(message.symbolId) in self.selected and name in self.expected_events,'UNREQUESTED_EVENT_SYMBOL_OR_TYPE')
            if self.market_capture_enabled and self.start_utc<=now<self.end_utc:
                self.event_handler(message,{'sequence':self.receipt_sequence,'receive_utc':now.isoformat(),
                                          'receive_monotonic_ns':ns,'connection_epoch':self.connection_epochs},envelope)
        elif name in ('ProtoOAAccountDisconnectEvent','ProtoOAClientDisconnectEvent','ProtoOAAccountsTokenInvalidatedEvent'):
            raise LiveInterrupted(name)
        return envelope

    def request(self, request, *, timeout=None):
        name=self.validate(request)
        require(self.connected,'REQUEST_REQUIRES_EXISTING_CONNECTION')
        if name=='ProtoOASubscribeDepthQuotesReq':self.expected_events.add('ProtoOADepthEvent')
        if name=='ProtoOASubscribeSpotsReq':self.expected_events.add('ProtoOASpotEvent')
        self._sequence+=1;cid=f'mxm-dom-live-{self._sequence:012d}'
        self._send_bytes(encode_envelope(request,cid))
        limit=self.cleanup_end if self.cleanup else min(self.contact_deadline,
                       self._clock()+max(0.,(self.end_utc-self.now_utc()).total_seconds()))
        deadline=min(self._clock()+float(timeout or self.response_timeout),limit)
        while True:
            envelope=self.receive_envelope(deadline=deadline)
            payload=extract_payload(envelope)
            if type(payload).__name__=='ProtoHeartbeatEvent':self.send_heartbeat();continue
            if str(getattr(envelope,'clientMsgId',''))==cid:return payload
            # Events already handled and retained in exact receive order above.

    def stream_until(self, deadline):
        deadline=min(deadline,self.contact_deadline,
                     self._clock()+max(0.,(self.end_utc-self.now_utc()).total_seconds()))
        while self._clock()<deadline:
            try:envelope=self.receive_envelope(deadline=deadline)
            except TimeoutError:
                # A deadline timeout can leave a partial frame; never resume/reconnect.
                self.close();return 'CAPTURE_DEADLINE_TIMEOUT_CONNECTION_CLOSED'
            payload=extract_payload(envelope)
            if type(payload).__name__=='ProtoHeartbeatEvent':self.send_heartbeat()
            elif isinstance(payload,m.ProtoOAErrorRes):raise LiveInterrupted('UNSOLICITED_BROKER_ERROR:'+payload.errorCode)
        return 'CAPTURE_DEADLINE'

    def unsubscribe_all(self, account_id):
        self.market_capture_enabled=False;self.cleanup=True;self.cleanup_end=self._clock()+15
        results={}
        if not self.connected:return {'connection':'CLOSED_NO_UNSUBSCRIBE_POSSIBLE'}
        for cls in (m.ProtoOAUnsubscribeDepthQuotesReq,m.ProtoOAUnsubscribeSpotsReq):
            if not self.selected:continue
            request=cls(ctidTraderAccountId=account_id);request.symbolId.extend(sorted(self.selected))
            try:
                response=self.request(request,timeout=5)
                results[cls.__name__]={'response_type':type(response).__name__,
                                      'broker_error':response.errorCode if isinstance(response,m.ProtoOAErrorRes) else None}
            except Exception as exc:
                results[cls.__name__]={'failure_type':type(exc).__name__}
                self.close();break
        self.close();return results

class DepthBook:
    def __init__(self, sid, digits):
        self.sid=sid;self.digits=digits;self.quotes={};self.counts=Counter();self.invalid_epoch=False
        self.spot={};self.level_min={'bid':None,'ask':None};self.level_max={'bid':0,'ask':0}
        self.size_min={'bid':None,'ask':None};self.size_max={'bid':None,'ask':None}
        self.total_min={'bid':None,'ask':None};self.total_max={'bid':None,'ask':None}
        self.distinct_size={'bid':set(),'ask':set()};self.first_both=None;self.first_three=None
        self.first_event=None;self.last_event=None;self.last_dom_ns=None;self.max_dom_gap_ns=0
        self.first_raw_sample=None;self.last_raw_sample=None

    def levels(self, side):
        levels={}
        for kind,price,size in self.quotes.values():
            if kind==side and size>0:levels[price]=levels.get(price,0)+size
        return sorted(levels.items(),reverse=side=='bid')

    def spot_event(self,event,stamp):
        self.counts['spot_events']+=1
        for side in ('bid','ask'):
            if event.HasField(side):self.spot[side]=(int(getattr(event,side)),stamp['receive_monotonic_ns']);self.counts['spot_'+side+'_updates']+=1
        if not event.HasField('timestamp'):self.counts['spot_server_timestamp_missing']+=1

    def depth_event(self,event,stamp):
        self.counts['depth_events']+=1;self.counts['new_quote_items']+=len(event.newQuotes);self.counts['deleted_quote_items']+=len(event.deletedQuotes)
        self.first_event=self.first_event or stamp['receive_utc'];self.last_event=stamp['receive_utc']
        now=stamp['receive_monotonic_ns']
        if self.last_dom_ns is not None:self.max_dom_gap_ns=max(self.max_dom_gap_ns,now-self.last_dom_ns)
        self.last_dom_ns=now
        ids=[int(q.id) for q in event.newQuotes];deleted=list(event.deletedQuotes)
        if len(set(ids))!=len(ids):self.counts['duplicate_new_ids']+=1;self.invalid_epoch=True
        if len(set(deleted))!=len(deleted):self.counts['duplicate_deleted_ids']+=1;self.invalid_epoch=True
        if set(ids)&set(deleted):self.counts['new_and_deleted_same_event_ids']+=len(set(ids)&set(deleted));self.invalid_epoch=True
        for identity in deleted:
            if identity not in self.quotes:self.counts['unknown_deleted_ids']+=1;self.invalid_epoch=True
            else:del self.quotes[identity]
        for quote in event.newQuotes:
            if quote.HasField('bid')==quote.HasField('ask'):
                self.counts['invalid_quote_side']+=1;self.invalid_epoch=True;continue
            side='bid' if quote.HasField('bid') else 'ask';price=int(getattr(quote,side));size=int(quote.size)
            self.counts['new_'+side+'_items']+=1
            if price<=0 or size<=0:self.counts['nonpositive_quote_price_or_size']+=1;self.invalid_epoch=True
            if quote.id in self.quotes:self.counts['replaced_known_ids']+=1
            self.quotes[int(quote.id)]=(side,price,size)
            units=size/100
            self.size_min[side]=units if self.size_min[side] is None else min(self.size_min[side],units)
            self.size_max[side]=units if self.size_max[side] is None else max(self.size_max[side],units)
            if len(self.distinct_size[side])<10000:self.distinct_size[side].add(size)
        require(len(self.quotes)<=10000,'BOOK_QUOTE_ID_RESOURCE_CAP')
        bid,ask=self.levels('bid'),self.levels('ask')
        for side,levels in [('bid',bid),('ask',ask)]:
            n=len(levels);self.level_min[side]=n if self.level_min[side] is None else min(self.level_min[side],n)
            self.level_max[side]=max(self.level_max[side],n);total=sum(v for _,v in levels)/100
            self.total_min[side]=total if self.total_min[side] is None else min(self.total_min[side],total)
            self.total_max[side]=total if self.total_max[side] is None else max(self.total_max[side],total)
        if bid and ask:
            self.counts['both_sided_states']+=1;self.first_both=self.first_both or stamp['receive_utc']
            if bid[0][0]>ask[0][0]:self.counts['crossed_book_states']+=1;self.invalid_epoch=True
        if len(bid)>=3 and len(ask)>=3:self.counts['three_level_both_states']+=1;self.first_three=self.first_three or stamp['receive_utc']
        contemporaneous=all(s in self.spot and 0<=now-self.spot[s][1]<=2_000_000_000 for s in ('bid','ask'))
        if contemporaneous and bid and ask:
            self.counts['contemporaneous_spot_comparisons']+=1
            tolerance=10**(5-self.digits)
            if abs(bid[0][0]-self.spot['bid'][0])<=tolerance and abs(ask[0][0]-self.spot['ask'][0])<=tolerance:
                self.counts['best_prices_within_one_native_digit']+=1
        sample={'receive_utc':stamp['receive_utc'],'sequence':stamp['sequence'],
                'bid_levels':[{'raw_price':p,'size_cents':s} for p,s in bid[:3]],
                'ask_levels':[{'raw_price':p,'size_cents':s} for p,s in ask[:3]]}
        self.first_raw_sample=self.first_raw_sample or sample;self.last_raw_sample=sample

    def summary(self):
        observed=self.counts['depth_events']>0
        return {'symbol_id':self.sid,'state':'DOM_EVENTS_OBSERVED' if observed else 'NO_DOM_EVENTS_OBSERVED',
                'counts':dict(self.counts),'first_event_utc':self.first_event,'last_event_utc':self.last_event,
                'initialization':{'first_both_sides_utc':self.first_both,'first_three_levels_utc':self.first_three,
                                  'server_initial_snapshot_completeness_flag':'NOT_EXPOSED',
                                  'observed_bootstrap':'BOTH_SIDES_OBSERVED' if self.first_both else 'INCOMPLETE_OR_UNOBSERVED',
                                  'reconstruction_epoch_ambiguous':self.invalid_epoch},
                'distinct_price_levels_min':self.level_min,'distinct_price_levels_max':self.level_max,
                'individual_size_units_min':self.size_min,'individual_size_units_max':self.size_max,
                'total_quoted_size_units_min':self.total_min,'total_quoted_size_units_max':self.total_max,
                'distinct_size_values_capped_at_10000':{s:len(v) for s,v in self.distinct_size.items()},
                'max_inter_DOM_receipt_gap_seconds':self.max_dom_gap_ns/1e9,
                'quantity_semantics':'BROKER_QUOTED_SIZE_NOT_EXECUTED_VOLUME_OR_FILL_GUARANTEE',
                'chronology':'LOCAL_RECEIPT_ORDER_ONLY_NO_DOM_SERVER_TIMESTAMP'}
