"""Cold readback of the ORIGINAL W33 quote archive into the EXISTING C# EUR200 account.

No broker network, strategy rerun, margin interpolation, FX fabrication or native order.
Private raw ticks never leave the protected custody runner. The stored bytes and all
six historical side streams must pass the existing sealed decoder.
"""
import base64
import hashlib
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

from . import panel_quote_support as panel
from .common import need, encoded, bytes_digest
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json, unpack
from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
from research_core_v4.successor_c_20261018.readback import FP

MANIFEST_SHA = "PLACEHOLDER"
SOURCE = "ed6e38aa3feac5cf4882952017752e8a627023bf"
EVIDENCE_HEAD = "1f05b49cbfbdac1f8fc6f063f4861ae1f35734fa"
COUNTS = {("AUDUSD", "bid"): 637, ("AUDUSD", "ask"): 667,
          ("Copper", "bid"): 208, ("Copper", "ask"): 210,
          ("SpotCrude", "bid"): 623, ("SpotCrude", "ask"): 624}

def read_regular(path, limit):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit, "W33_REGULAR_BOUNDED_EVIDENCE")
    return path.read_bytes()

def export(folder, tick_path, declaration_path, public_path):
    need(os.environ.get("GITHUB_REPOSITORY") == panel.REPO and
         os.environ.get("GITHUB_REF_NAME") == panel.BRANCH and
         os.environ.get("GITHUB_EVENT_NAME") == "push" and
         os.environ.get("GITHUB_RUN_ATTEMPT") == "1" and
         os.environ.get("GITHUB_JOB") == "authentic-w33-account" and
         os.environ.get("R3_CTRADER_CLIENT_SECRET") is None and
         os.environ.get("R3_CTRADER_ACCESS_TOKEN") is None and
         os.environ.get("R3_CTRADER_REFRESH_TOKEN") is None and
         os.environ.get("SUCCESSOR_APP_PRIVATE_KEY") is None, "W33_CUSTODY_ONLY_NO_BROKER_ACCESS")
    evidence = Path(folder)
    manifest_raw = read_regular(evidence / "MANIFEST.json", 20000)
    need(bytes_digest(manifest_raw) == MANIFEST_SHA, "W33_PINNED_MANIFEST")
    manifest = json.loads(manifest_raw)
    need(manifest["schema"] == "mxm.original-native-source-support-archive.v1" and
         manifest["source_run"] == 40836352578 and manifest["source_head"] == SOURCE and
         manifest["native_decoder"] == panel.NATIVE and
         manifest["source_attempt"] == 1 and manifest["source_conclusion"] == "success" and
         manifest["total_historical_tick_events"] == 2969 and
         manifest["history_requests"] == 6 and manifest["orders"] == 0 and
         manifest["strategy_trials"] == 0 and
         manifest["historical_costs_proven"] is False, "W33_ORIGINAL_IDENTITY")
    for name, meta in manifest["files"].items():
        raw = read_regular(evidence / name, 1024 * 1024)
        need(len(raw) == meta["bytes"] and bytes_digest(raw) == meta["sha256"], "W33_ORIGINAL_FILE_" + name)
    producer_zip = read_regular(evidence / "producer-artifact.zip", 1024 * 1024)
    with zipfile.ZipFile(io.BytesIO(producer_zip)) as archive:
        need(set(archive.namelist()) == {"capture.mxmenc", "producer.json"} and
             all(i.file_size <= 1024 * 1024 for i in archive.infolist()), "W33_PRODUCER_ZIP_SCOPE")
        cipher = archive.read("capture.mxmenc")
        producer = json.loads(archive.read("producer.json"))
    need(bytes_digest(cipher) == manifest["cipher_sha256"] and
         producer["source_sha"] == SOURCE and
         producer["run_id"] == 40836352578 and
         producer["private_sha256"] == manifest["private_sha256"], "W33_ORIGINAL_CIPHER_AND_PRODUCER")
    with tempfile.TemporaryDirectory() as tmp:
        key, fp = _private_key_from_secret(Path(tmp))
        need(fp == FP, "W33_UNCHANGED_CUSTODY_RECIPIENT")
        private_raw = unpack(owner.bounded_decrypt(cipher, key, Path(tmp)),
                             max_bytes=panel.POLICY["max_private_bytes"])
        need(bytes_digest(private_raw) == manifest["private_sha256"], "W33_ORIGINAL_PRIVATE")
        private = strict_json(private_raw, max_elements=3_000_000)
        need(private["identity"]["source_sha"] == SOURCE and
             private["identity"]["run_id"] == 40836352578 and
             private["identity"]["attempt"] == 1, "W33_PRIVATE_IDENTITY")
        profile = panel.verify_private(private)
        need(profile["all_panel_sides_complete_nonempty"] and
             sum(row["events"] for row in profile["cells"]) == 2969, "W33_FULL_SIX_SIDES")
        pairs = [panel.decode_pair(r, private["account"]) for r in private["receipts"]]
        receipts = [
            {**r,
             "request_b64": base64.b64encode(req.SerializeToString()).decode() if req else None,
             "request_envelope_b64": r.get("request_wire"),
             "response_envelope_b64": r["response_wire"]}
            for r, (req, res) in zip(private["receipts"], pairs)
        ]
        rows = []
        for sid, symbol in panel.POLICY["symbols"].items():
            native = panel.native_policy(int(sid))
            for side, code in (("bid", 1), ("ask", 2)):
                events, complete, _ = native.verify_tree(
                    private["trees"][sid][side.upper()], receipts, private["account"], code)
                need(complete and len(events) == COUNTS[(symbol, side)], "W33_REDECODE_SIDE_" + symbol + side)
                for t, raw in events:
                    need(panel.POLICY["from_ms"] <= t < panel.POLICY["to_ms"] and raw > 0,
                         "W33_NATIVE_TIMESTAMP_OR_PRICE")
                    rows.append(dict(symbol=symbol, t=t, side=side, raw=raw))
        rows.sort(key=lambda r: (r["t"], r["symbol"], r["side"]))
        need(len(rows) == 2969, "W33_RECONSTRUCTED_EVENT_TOTAL")
        ticks = b"".join(encoded(row) + b"\n" for row in rows)
        declaration = dict(schema="mxm.declared-quote-assets.v1",
                           source_sha256=manifest["private_sha256"],
                           symbols=profile["quote_assets"])
        for out, raw in ((tick_path, ticks), (declaration_path, encoded(declaration) + b"\n")):
            p = Path(out)
            p.parent.mkdir(parents=True, exist_ok=True)
            need(not p.exists(), "W33_NO_OVERWRITE_PRIVATE_OUTPUT")
            p.write_bytes(raw)
        receipt = dict(schema="mxm.authentic-w33-csharp-source-bridge.v1",
                       native_run=40836352578, pinned_source=SOURCE,
                       native_decoder=panel.NATIVE,
                       original_cipher_sha256=manifest["cipher_sha256"],
                       derived_stream_sha256=bytes_digest(ticks),
                       private_declaration_sha256=manifest["private_sha256"],
                       events=len(rows), six_sides_complete=True,
                       accounts=1, orders=0, strategy_trials=0,
                       broker_requests=0, historical_arrival_proven=False,
                       historical_costs_proven=False,
                       standalone_broker_execution_proven=False,
                       independent_confirmation=False)
        Path(public_path).write_bytes(encoded(receipt) + b"\n")
        print("MXM_ORIGINAL_W33_NATIVE_WIRE_TO_CSHARP_READY " + json.dumps(receipt, sort_keys=True))

if __name__ == "__main__":
    need(len(sys.argv) == 5 and sys.argv[1] == "--original-w33", "W33_READBACK_ARGUMENTS")
    export(*sys.argv[2:])
