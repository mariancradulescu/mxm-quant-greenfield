"""P0-16 static boundary: ordinary execution must never request fault injection.

A technical orchestration guard, not an economic or end-to-end certificate.
Runs without market data, cloud credentials, GitHub write privileges or secrets.
"""
from pathlib import Path

def verify(root: Path) -> None:
    workflow = (root / ".github/workflows/mxm-integrated-p0.yml").read_text()
    assert "LAB_INTEGRATED_PROTOCOL: v2" in workflow
    assert "LAB_SOURCE_SHA: eab050084982916ad0c67798b38b947bac66b2b2" in workflow
    assert "fault_before_fence:" in workflow, "Preserve current handoff input compatibility"
    assert workflow.count("LAB_FAULT_BEFORE_FENCE: '0'") == 1
    assert "LAB_FAULT_ACK:" not in workflow
    assert "github.event_name == 'push' && '1'" not in workflow
    assert "INJECTED_CRASH" not in workflow
    assert "secrets.SUCCESSOR_APP_PRIVATE_KEY" not in workflow
    assert "if: needs.durable-archive.result == 'success' && needs.durable-archive.outputs.next == 'STOP'" in workflow
    # The sealed R2 implementation still trusts bare JSON status. Block
    # all economic admissions at the workflow boundary until native E2E proof verification.
    assert workflow.count("P0-17 refuse unverified economic acceptance certificates") == 1
    assert "P0-17_NATIVE_CERTIFICATE_VERIFICATION_NOT_INSTALLED" in workflow
    assert "admission['mode'] != 'TECHNICAL_NONOUTCOME'" in workflow
    assert workflow.index("P0-17 refuse unverified economic acceptance certificates") < workflow.index("- id: prepare")


if __name__ == "__main__":
    verify(Path(__file__).resolve().parents[1])
    print("P0-16 ordinary workflow fault injection: DISABLED; no runtime operations performed")
