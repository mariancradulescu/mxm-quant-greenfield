"""Additive monotonic heartbeat and private transport diagnostics. No reconnect."""
import os, socket, ssl, time
from collections import Counter
from m6.ctrader_transport import TransportError
from m6.ctrader_capture import redact_text
from research_core_v4.dom_live_probe_20261013_v1.live_adapter_v1 import LiveReadOnlyTransport, LiveWindowEnded, require

SECRET_NAMES=('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN','CTRADER_REFRESH_TOKEN','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','GH_TOKEN')
def safe_text(value):
    s=str(value)
    for name in SECRET_NAMES:
        secret=os.environ.get(name)
        if secret:s=s.replace(secret,'<REDACTED>')
    return redact_text(s)[:4096]

def error_detail(exc):
    chain=[];seen=set()
    while exc is not None and id(exc) not in seen and len(chain)<8:
        seen.add(id(exc));row={'type':type(exc).__name__,'message':safe_text(exc)}
        for name in ('errno','strerror','library','reason','verify_code','verify_message'):
            value=getattr(exc,name,None)
            if value is not None:row[name]=safe_text(value) if isinstance(value,str) else value
        chain.append(row);exc=exc.__cause__ or exc.__context__
    return {'exception_chain':chain}

class InformationTransport(LiveReadOnlyTransport):
    def __init__(self,*,maximum_connection_seconds=900,marker_handler=None,**kwargs):
        super().__init__(**kwargs)
        require(0<maximum_connection_seconds<=3600,'OWNER_CONNECTION_CAP')
        self.maximum_connection_seconds=maximum_connection_seconds
        self.heartbeat_period=10.;self.next_heartbeat=None;self.heartbeat_stamps=[]
        self.marker_handler=marker_handler or (lambda x:None);self.private_errors=[]
        self.connection_attempted=False;self.partial_frame_received=0;self.failure_socket=None

    def marker(self,kind,**kw):
        self.marker_handler({'kind':kind,'receive_utc':self.now_utc().isoformat(),
            'receive_monotonic_ns':time.monotonic_ns(),'sequence':self.receipt_sequence,**kw})

    def socket_info(self):
        sock=self._sock;out={'endpoint':self.last_connected_endpoint,'connected':self.connected}
        if sock is not None:
            for name in ('getpeername','getsockname','version','cipher'):
                try:out[name]=getattr(sock,name)()
                except Exception:pass
        return out

    def retain_error(self,exc,operation):
        detail={'operation':operation,**error_detail(exc),'socket_tls':self.socket_info(),
                'failure_socket_tls':self.failure_socket,'partial_frame_bytes':self.partial_frame_received}
        self.private_errors.append(detail);self.marker('INTERRUPTION',detail=detail)
        return detail

    def connect(self):
        require(not self.connection_attempted,'RECONNECT_NOT_AUTHORIZED')
        self.connection_attempted=True;self.temporal_check()
        self.first_contact_mono=self._clock();self.contact_deadline=self.first_contact_mono+self.maximum_connection_seconds
        try:endpoints=self._resolve_endpoints()
        except Exception as exc:
            self.retain_error(exc,'CONNECT_DNS');raise TransportError('LIVE_DNS_FAILURE:'+safe_text(exc)) from exc
        self._cached_endpoints=endpoints;last=None
        for endpoint in endpoints[:8]:
            raw=None
            try:
                require(self._clock()<self.contact_deadline,'CONNECT_TIME_CAP')
                raw=self._socket_factory(endpoint,timeout=min(self.connect_timeout,self.contact_deadline-self._clock()))
                try:raw.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,1)
                except OSError:pass
                tls=self._ssl_context_factory().wrap_socket(raw,server_hostname=self.host);raw=None
                tls.settimeout(min(1.,self.response_timeout));self._sock=tls
                self._last_connected_endpoint=endpoint;self.connection_epochs=1;self._last_send=self._clock()
                self.next_heartbeat=self._clock()+self.heartbeat_period
                self.marker('CONNECTION_ESTABLISHED',socket_tls=self.socket_info());return
            except Exception as exc:
                last=exc;self.retain_error(exc,'CONNECT_TCP_TLS:'+str(endpoint))
                if raw is not None:
                    try:raw.close()
                    except OSError:pass
                self.close()
        raise TransportError('LIVE_TCP_TLS_FAILED_BOUNDED_ENDPOINTS') from last

    def heartbeat_due(self):
        now=self._clock()
        if self.next_heartbeat is None:self.next_heartbeat=now+self.heartbeat_period
        if now>=self.next_heartbeat:
            due=self.next_heartbeat;self.send_heartbeat()
            sent=self._clock();self.heartbeat_stamps.append({'due_monotonic':due,'sent_monotonic':sent,'lateness_seconds':sent-due})
            self.marker('PERIODIC_HEARTBEAT_SENT')
            # No bursts after delays; next deadline remains based on monotonic time.
            self.next_heartbeat=sent+self.heartbeat_period

    def _send_bytes(self,framed):
        self.failure_socket=self.socket_info()
        try:super()._send_bytes(framed)
        except Exception as exc:
            self.retain_error(exc,'SEND');raise

    def _recv_exact(self,count,*,deadline):
        sock=self._require_connected();chunks=[];received=0
        while received<count:
            remaining=deadline-self._clock()
            if remaining<=0:
                self.partial_frame_received=received
                exc=TimeoutError('LOCAL_RECEIVE_DEADLINE_PARTIAL_FRAME' if received else 'LOCAL_RECEIVE_DEADLINE')
                self.retain_error(exc,'RECEIVE_DEADLINE');raise exc
            self.heartbeat_due()
            wait=min(1.,remaining,max(.001,self.next_heartbeat-self._clock()))
            try:
                sock.settimeout(wait);block=sock.recv(count-received)
            except socket.timeout:continue
            except OSError as exc:
                self.partial_frame_received=received;self.failure_socket=self.socket_info()
                self.retain_error(exc,'RECEIVE_SOCKET');self.close()
                raise TransportError('LIVE_TLS_RECEIVE_FAILED:'+safe_text(exc)) from exc
            if not block:
                self.partial_frame_received=received;self.failure_socket=self.socket_info()
                exc=TransportError('LIVE_TLS_PEER_EOF');self.retain_error(exc,'RECEIVE_EOF');self.close();raise exc
            chunks.append(block);received+=len(block)
        self.partial_frame_received=0
        return b''.join(chunks)

    def receive_envelope(self,*,deadline):
        try:return super().receive_envelope(deadline=deadline)
        except Exception as exc:
            self.retain_error(exc,'RECEIVE_ENVELOPE');raise

    def unsubscribe_all(self,account_id):
        self.marker('CLEANUP_BEGIN');result=super().unsubscribe_all(account_id)
        self.marker('CLEANUP_COMPLETE',result=result);return result
