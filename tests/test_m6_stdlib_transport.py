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


if __name__ == "__main__":
    unittest.main(verbosity=2)
