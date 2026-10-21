"""P0-16 static boundary: ordinary execution must never request fault injection.

A technical orchestration guard, not an economic or end-to-end certificate.
Runs without market data, cloud credentials, GitHub write privileges or secrets.
"""
from pathlib import Path

def _legacy_verify(root: Path) -> None:
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


def verify(root: Path) -> None:
    import hashlib,json
    raw=(root/'.github/workflows/mxm-integrated-p0.yml').read_bytes()
    try: workflow=json.loads(raw)
    except json.JSONDecodeError:
        return _legacy_verify(root)
    # Exact regenerated R3 contract, not a permissive JSON/YAML text search.
    assert hashlib.sha256(raw).hexdigest()=='90d7f4eda74f4f3cc3b27233803fdea45e15fec8760b353beab0a3e1556c220c'
    assert workflow['env']['LAB_SOURCE_SHA']=='c6bf7027647d9b1e8e1a4dac50008c3ec0543c1c'
    assert workflow['env']['LAB_INTEGRATED_PROTOCOL']=='v2'
    assert workflow['jobs']['preflight']['needs']=='source-controls'
    assert len(workflow['jobs'])==11 and workflow['permissions']=={}
    assert workflow['on']['workflow_dispatch']['inputs']['fault_before_fence']['default']=='0'
    assert "inputs.fault_before_fence != '1'" in workflow['jobs']['scientific-handoff']['if']
    for name,job in workflow['jobs'].items():
        assert job['permissions']['contents']=='read'
        assert job['steps'][0]['with']=={'ref':'c6bf7027647d9b1e8e1a4dac50008c3ec0543c1c','persist-credentials':False}
        envs=[step.get('env',{}) for step in job['steps']]
        assert not any(any(key.startswith('CTRADER_') for key in env) for env in envs)
        key_steps=[s for s in job['steps'] if 'SUCCESSOR_APP_PRIVATE_KEY' in s.get('env',{})]
        if key_steps:
            assert job['environment']=='mxm-p0-successor-issuer-v1' and len(key_steps)==1
            assert key_steps[0]['run'].startswith('python3 -m research_core_v4.laboratory.custody ')
            assert not any('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in env for env in envs)
        else: assert job['environment']=='mxm-r3-custody-v1'
    assert not any('LAB_FAULT_ACK' in step.get('env',{}) for job in workflow['jobs'].values() for step in job['steps'])

if __name__ == "__main__":
    verify(Path(__file__).resolve().parents[1])
    print("P0-16 exact legacy/R3 contract: ordinary default fault=0; controlled technical fault has no automatic handoff; scoped credentials; no runtime operations")
