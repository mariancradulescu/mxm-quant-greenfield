import socket
import struct
import unittest
from pathlib import Path

from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoHeartbeatEvent
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAApplicationAuthReq,
    ProtoOAGetTickDataReq,
    ProtoOAGetTickDataRes,
)
from m6.ctrader_transport import (
    LIVE_HOST,
    LIVE_PORT,
    decode_envelope,
    encode_envelope,
    extract_payload,
    runtime_transport_preflight,
    StdlibCTraderTransport,
)


class M6StdlibTransportTests(unittest.TestCase):
    def test_01_int32_big_endian_framing_roundtrip(self):
        request = ProtoOAApplicationAuthReq(clientId="A", clientSecret="B")
        framed = encode_envelope(request, "mxm-test")
        size = struct.unpack("!I", framed[:4])[0]
        self.assertEqual(size, len(framed) - 4)
        envelope = decode_envelope(framed[4:])
        self.assertEqual(envelope.clientMsgId, "mxm-test")
        parsed = extract_payload(envelope)
        self.assertEqual(parsed.clientId, "A")
        self.assertEqual(parsed.clientSecret, "B")

    def test_02_heartbeat_roundtrip_and_preflight_no_network(self):
        framed = encode_envelope(ProtoHeartbeatEvent())
        envelope = decode_envelope(framed[4:])
        parsed = extract_payload(envelope)
        self.assertIsInstance(parsed, ProtoHeartbeatEvent)
        report = runtime_transport_preflight()
        self.assertEqual(report["live_host"], LIVE_HOST)
        self.assertEqual(report["live_port"], LIVE_PORT)
        self.assertFalse(report["network_connection_attempted"])
        self.assertFalse(report["cryptography_required"])
        self.assertFalse(report["rust_required"])

    def test_03_active_android_runtime_has_no_rust_crypto_transport_imports(self):
        root = Path(__file__).resolve().parents[1]
        runtime = (root / "m6/ctrader_openapi.py").read_text(encoding="utf-8")
        transport = (root / "m6/ctrader_transport.py").read_text(encoding="utf-8")
        requirements = (root / "tools/requirements-m6-capture.txt").read_text(encoding="utf-8")
        combined = runtime + "\n" + transport
        for forbidden in (
            "from twisted",
            "import twisted",
            "from OpenSSL",
            "import OpenSSL",
            "import cryptography",
            "from cryptography",
            "from ctrader_open_api",
            "import ctrader_open_api",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertEqual(requirements.strip(), "protobuf==3.20.1")

    def test_04_vendored_generated_message_files_exist(self):
        root = Path(__file__).resolve().parents[1]
        for rel in (
            "m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py",
            "m6/ctrader_proto/OpenApiCommonMessages_pb2.py",
            "m6/ctrader_proto/OpenApiModelMessages_pb2.py",
            "m6/ctrader_proto/OpenApiMessages_pb2.py",
            "m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt",
        ):
            self.assertTrue((root / rel).is_file(), rel)


    def test_05_request_batch_correlates_out_of_order_responses_on_one_connection(self):
        class FakeBatchTransport(StdlibCTraderTransport):
            def __init__(self):
                super().__init__()
                self._sock = object()
                self.sent_ids = []
                self._queued = None

            def _send_bytes(self, payload):
                size = struct.unpack("!I", payload[:4])[0]
                envelope = decode_envelope(payload[4:4+size])
                self.sent_ids.append(envelope.clientMsgId)

            def receive_envelope(self, *, deadline):
                if self._queued is None:
                    self._queued = []
                    for index, client_id in reversed(list(enumerate(self.sent_ids))):
                        response = ProtoOAGetTickDataRes(ctidTraderAccountId=1)
                        response.hasMore = bool(index % 2)
                        framed = encode_envelope(response, client_id)
                        self._queued.append(decode_envelope(framed[4:]))
                return self._queued.pop(0)

            def close(self):
                self._sock = None

        transport = FakeBatchTransport()
        requests = [
            ProtoOAGetTickDataReq(
                ctidTraderAccountId=1,
                symbolId=127,
                type=1,
                fromTimestamp=1000+i,
                toTimestamp=2000+i,
            )
            for i in range(4)
        ]
        responses = transport.request_batch(
            requests,
            timeout=1,
            min_interval_seconds=0,
        )
        self.assertEqual(len(transport.sent_ids), 4)
        self.assertEqual([bool(x.hasMore) for x in responses], [False, True, False, True])

    def test_06_batch_transport_keeps_single_connection_and_client_msg_ids_unique(self):
        source = (Path(__file__).resolve().parents[1] / "m6/ctrader_transport.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def request_batch(", source)
        self.assertIn("pending[client_msg_id]", source)
        self.assertIn("return [pending[msg_id] for msg_id in ordered_ids]", source)
        self.assertNotIn("ThreadPoolExecutor", source)

    def test_07_dns_failure_reconnect_uses_cached_ip_and_keeps_tls_hostname(self):
        class FakeRaw:
            def __init__(self):
                self.closed=False
                self.timeouts=[]
            def setsockopt(self,*args):
                pass
            def settimeout(self,value):
                self.timeouts.append(value)
            def close(self):
                self.closed=True

        class FakeContext:
            def __init__(self):
                self.server_names=[]
            def wrap_socket(self,raw,*,server_hostname):
                self.server_names.append(server_hostname)
                return raw

        class Resolver:
            def __init__(self):
                self.calls=0
            def __call__(self,host,port,*,type):
                self.calls+=1
                if self.calls==1:
                    return [
                        (socket.AF_INET,socket.SOCK_STREAM,6,"",("203.0.113.10",port))
                    ]
                raise socket.gaierror(7,"No address associated with hostname")

        resolver=Resolver()
        context=FakeContext()
        endpoints=[]
        def factory(endpoint,timeout):
            endpoints.append(endpoint)
            return FakeRaw()

        transport=StdlibCTraderTransport(
            socket_factory=factory,
            ssl_context_factory=lambda:context,
            resolver=resolver,
        )
        transport.connect()
        self.assertEqual(
            transport.cached_endpoints,
            (("203.0.113.10",LIVE_PORT),),
        )
        transport.close()
        transport.connect()
        self.assertEqual(
            endpoints,
            [("203.0.113.10",LIVE_PORT),("203.0.113.10",LIVE_PORT)],
        )
        self.assertEqual(
            context.server_names,
            [LIVE_HOST,LIVE_HOST],
        )

    def test_08_persisted_cached_ip_can_bootstrap_when_dns_is_temporarily_down(self):
        class FakeRaw:
            def setsockopt(self,*args):
                pass
            def settimeout(self,value):
                pass
            def close(self):
                pass

        class FakeContext:
            def __init__(self):
                self.server_name=None
            def wrap_socket(self,raw,*,server_hostname):
                self.server_name=server_hostname
                return raw

        def resolver(*args,**kwargs):
            raise socket.gaierror(7,"No address associated with hostname")

        used=[]
        context=FakeContext()
        transport=StdlibCTraderTransport(
            socket_factory=lambda endpoint,timeout: (used.append(endpoint) or FakeRaw()),
            ssl_context_factory=lambda:context,
            resolver=resolver,
        )
        transport.seed_cached_endpoints([["203.0.113.20",LIVE_PORT]])
        transport.connect()
        self.assertEqual(used,[("203.0.113.20",LIVE_PORT)])
        self.assertEqual(context.server_name,LIVE_HOST)



if __name__ == "__main__":
    unittest.main(verbosity=2)
