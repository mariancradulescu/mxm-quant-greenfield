"""Pure-stdlib TLS transport for cTrader Open API protobuf messages.

This module intentionally avoids Twisted, pyOpenSSL, service_identity and cryptography.
It uses the official cTrader protobuf envelope/messages and the documented LIVE endpoint
over TLS, with the same 32-bit length-prefix framing used by Spotware OpenApiPy.
"""
from __future__ import annotations

import socket
import ssl
import struct
import time
from typing import Any

from .ctrader_capture import CaptureContractError, redact_text, require_read_only_request
from .ctrader_proto import OpenApiCommonMessages_pb2 as common_messages
from .ctrader_proto import OpenApiMessages_pb2 as oa_messages

LIVE_HOST = "live.ctraderapi.com"
LIVE_PORT = 5035
HEARTBEAT_IDLE_SECONDS = 10.0
DEFAULT_RESPONSE_TIMEOUT = 30.0
MAX_FRAME_BYTES = 15_000_000


class TransportError(CaptureContractError):
    pass


def _build_registry() -> dict[int, type]:
    registry: dict[int, type] = {}
    for module in (common_messages, oa_messages):
        for name in dir(module):
            if not name.startswith("Proto"):
                continue
            klass = getattr(module, name)
            if not isinstance(klass, type):
                continue
            try:
                instance = klass()
                payload_type = int(instance.payloadType)
            except Exception:
                continue
            if payload_type:
                registry[payload_type] = klass
    if not registry:
        raise TransportError("official cTrader protobuf response registry is empty")
    return registry


PROTO_REGISTRY = _build_registry()
ProtoMessage = common_messages.ProtoMessage
ProtoHeartbeatEvent = common_messages.ProtoHeartbeatEvent


def extract_payload(envelope: Any):
    klass = PROTO_REGISTRY.get(int(envelope.payloadType))
    if klass is None:
        raise TransportError(f"unsupported cTrader payload type {int(envelope.payloadType)}")
    message = klass()
    message.ParseFromString(envelope.payload)
    return message


def encode_envelope(message: Any, client_msg_id: str | None = None) -> bytes:
    if isinstance(message, ProtoMessage):
        envelope = message
    else:
        payload_type = getattr(message, "payloadType", None)
        if payload_type is None:
            raise TransportError(f"message {type(message).__name__} has no payloadType")
        envelope = ProtoMessage(
            payloadType=int(payload_type),
            payload=message.SerializeToString(),
        )
        if client_msg_id:
            envelope.clientMsgId = client_msg_id
    raw = envelope.SerializeToString()
    if len(raw) > MAX_FRAME_BYTES:
        raise TransportError(f"protobuf frame too large: {len(raw)} bytes")
    return struct.pack("!I", len(raw)) + raw


def decode_envelope(raw: bytes):
    envelope = ProtoMessage()
    envelope.ParseFromString(raw)
    return envelope


class StdlibCTraderTransport:
    def __init__(
        self,
        host: str = LIVE_HOST,
        port: int = LIVE_PORT,
        *,
        connect_timeout: float = 20.0,
        response_timeout: float = DEFAULT_RESPONSE_TIMEOUT,
        socket_factory=socket.create_connection,
        ssl_context_factory=ssl.create_default_context,
        clock=time.monotonic,
    ):
        self.host = host
        self.port = int(port)
        self.connect_timeout = float(connect_timeout)
        self.response_timeout = float(response_timeout)
        self._socket_factory = socket_factory
        self._ssl_context_factory = ssl_context_factory
        self._clock = clock
        self._sock = None
        self._sequence = 0
        self._last_send = 0.0
        self._last_rate_limited_request_send = 0.0

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def connect(self) -> None:
        self.close()
        try:
            raw = self._socket_factory((self.host, self.port), timeout=self.connect_timeout)
            try:
                raw.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except OSError:
                pass
            context = self._ssl_context_factory()
            tls = context.wrap_socket(raw, server_hostname=self.host)
            tls.settimeout(min(5.0, self.response_timeout))
            self._sock = tls
            self._last_send = self._clock()
        except Exception as exc:
            self.close()
            raise TransportError(
                f"cTrader LIVE TLS connection failed: {type(exc).__name__}: {redact_text(str(exc))}"
            ) from None

    def close(self) -> None:
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def _require_connected(self):
        if self._sock is None:
            raise TransportError("cTrader TLS transport is not connected")
        return self._sock

    def _send_bytes(self, payload: bytes) -> None:
        sock = self._require_connected()
        try:
            sock.sendall(payload)
            self._last_send = self._clock()
        except OSError as exc:
            self.close()
            raise TransportError(
                f"cTrader TLS send failed: {type(exc).__name__}: {redact_text(str(exc))}"
            ) from None

    def send_heartbeat(self) -> None:
        self._send_bytes(encode_envelope(ProtoHeartbeatEvent()))

    def _recv_exact(self, count: int, *, deadline: float) -> bytes:
        sock = self._require_connected()
        chunks: list[bytes] = []
        received = 0
        while received < count:
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise TimeoutError("cTrader response timeout")
            try:
                sock.settimeout(min(5.0, remaining))
                block = sock.recv(count - received)
            except socket.timeout:
                if self._clock() - self._last_send >= HEARTBEAT_IDLE_SECONDS:
                    self.send_heartbeat()
                continue
            except OSError as exc:
                self.close()
                raise TransportError(
                    f"cTrader TLS receive failed: {type(exc).__name__}: {redact_text(str(exc))}"
                ) from None
            if not block:
                self.close()
                raise TransportError("cTrader TLS connection closed by peer")
            chunks.append(block)
            received += len(block)
        return b"".join(chunks)

    def receive_envelope(self, *, deadline: float):
        header = self._recv_exact(4, deadline=deadline)
        size = struct.unpack("!I", header)[0]
        if size <= 0 or size > MAX_FRAME_BYTES:
            raise TransportError(f"invalid cTrader protobuf frame length: {size}")
        body = self._recv_exact(size, deadline=deadline)
        return decode_envelope(body)

    def request_batch(
        self,
        requests: list[Any],
        *,
        timeout: float | None = None,
        min_interval_seconds: float = 0.21,
    ) -> list[Any]:
        """Pipeline a bounded read-only request batch over one LIVE connection.

        Requests are serialized on the wire at the caller-supplied minimum interval and
        responses are then drained/correlated by clientMsgId. This avoids concurrent
        send/receive operations while allowing multiple historical requests to be in
        flight, matching cTrader's message-queue guidance and preserving one LIVE
        connection.
        """
        if not requests:
            return []
        if min_interval_seconds < 0:
            raise TransportError("batch request interval cannot be negative")
        for request in requests:
            require_read_only_request(type(request).__name__)
        if not self.connected:
            self.connect()

        ordered_ids: list[str] = []
        pending: dict[str, Any] = {}
        heartbeat_type = int(ProtoHeartbeatEvent().payloadType)

        for request in requests:
            now = self._clock()
            if self._last_rate_limited_request_send > 0.0:
                wait = min_interval_seconds - (
                    now - self._last_rate_limited_request_send
                )
                if wait > 0:
                    time.sleep(wait)
            self._sequence += 1
            client_msg_id = f"mxm-{self._sequence:012d}"
            self._send_bytes(encode_envelope(request, client_msg_id))
            self._last_rate_limited_request_send = self._clock()
            ordered_ids.append(client_msg_id)
            pending[client_msg_id] = None

        deadline = self._clock() + float(timeout or self.response_timeout)
        while any(value is None for value in pending.values()):
            try:
                envelope = self.receive_envelope(deadline=deadline)
            except TimeoutError:
                missing = sum(value is None for value in pending.values())
                raise TransportError(
                    f"historical batch timed out with {missing}/{len(requests)} "
                    f"responses pending after {float(timeout or self.response_timeout):.1f}s"
                ) from None

            if int(envelope.payloadType) == heartbeat_type:
                self.send_heartbeat()
                continue

            client_msg_id = str(getattr(envelope, "clientMsgId", ""))
            if client_msg_id not in pending:
                # Unsolicited event or stale response from an earlier failed batch.
                continue
            if pending[client_msg_id] is not None:
                continue
            pending[client_msg_id] = extract_payload(envelope)

        return [pending[msg_id] for msg_id in ordered_ids]

    def request(self, request: Any, *, timeout: float | None = None):
        require_read_only_request(type(request).__name__)
        if not self.connected:
            self.connect()
        self._sequence += 1
        client_msg_id = f"mxm-{self._sequence:012d}"
        self._send_bytes(encode_envelope(request, client_msg_id))
        deadline = self._clock() + float(timeout or self.response_timeout)
        heartbeat_type = int(ProtoHeartbeatEvent().payloadType)

        while True:
            try:
                envelope = self.receive_envelope(deadline=deadline)
            except TimeoutError:
                raise TransportError(
                    f"{type(request).__name__} timed out after {float(timeout or self.response_timeout):.1f}s"
                ) from None

            if int(envelope.payloadType) == heartbeat_type:
                self.send_heartbeat()
                continue

            # Request/response messages are correlated by clientMsgId. Unsolicited events
            # are ignored here; they are not broker evidence and cannot mutate state.
            if str(getattr(envelope, "clientMsgId", "")) != client_msg_id:
                continue

            return extract_payload(envelope)


def runtime_transport_preflight() -> dict[str, Any]:
    if not LIVE_HOST or LIVE_PORT != 5035:
        raise TransportError("cTrader LIVE endpoint constant is invalid")
    heartbeat = ProtoHeartbeatEvent()
    framed = encode_envelope(heartbeat)
    if len(framed) < 5:
        raise TransportError("protobuf framing preflight failed")
    size = struct.unpack("!I", framed[:4])[0]
    if size != len(framed) - 4:
        raise TransportError("protobuf length prefix preflight failed")
    decoded = decode_envelope(framed[4:])
    if int(decoded.payloadType) != int(heartbeat.payloadType):
        raise TransportError("protobuf heartbeat round-trip failed")
    if int(heartbeat.payloadType) not in PROTO_REGISTRY:
        raise TransportError("protobuf registry lacks heartbeat payload")
    return {
        "transport": "python_stdlib_ssl_socket",
        "live_host": LIVE_HOST,
        "live_port": LIVE_PORT,
        "tls_hostname_verification": True,
        "protobuf_framing": "INT32_BIG_ENDIAN_LENGTH_PREFIX",
        "heartbeat_available": True,
        "heartbeat_idle_seconds": HEARTBEAT_IDLE_SECONDS,
        "twisted_required": False,
        "pyopenssl_required": False,
        "cryptography_required": False,
        "rust_required": False,
        "network_connection_attempted": False,
        "credentials_used": False,
    }
