import struct
import unittest
from pathlib import Path

from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoHeartbeatEvent
from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq
from m6.ctrader_transport import (
    LIVE_HOST,
    LIVE_PORT,
    decode_envelope,
    encode_envelope,
    extract_payload,
    runtime_transport_preflight,
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
