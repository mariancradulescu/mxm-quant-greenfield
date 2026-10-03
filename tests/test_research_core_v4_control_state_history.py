"""Keep historical V3 validation distinct from the active V4 transport audit."""
import hashlib
from pathlib import Path
from unittest.mock import patch
from research_core_v4 import crash_recovery_control_v3 as v3
from research_core_v4 import asymmetric_recovery_v4_gate as v4
SNAPSHOT=v3.ROOT/'research_core_v4/state/V4_PRE_SEGMENTED_STAGING_STATE_V1.json'
SNAPSHOT_SHA='1c2b62712f75151e9fc41044c0f621c416c36160912ddf3890dbce52805d70fc'

def validate_historical_v3_and_current_transport():
    if not (v4.ROOT/v4.V4_ACTIVE_REL).exists():
        return v3.validate_current_control_plane()
    assert hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()==SNAPSHOT_SHA
    with patch.object(v3,'STATE',SNAPSHOT), patch.object(v3,'WORKFLOW',v3.ROOT/'research_core_v4/runtime/SUPERSEDED_RECOVERY_V3_WORKFLOW_READ_ONLY.yml'):
        historical=v3.validate_current_control_plane()
    current=v4.audit()
    assert current['status']=='PASS_ASYMMETRIC_RECOVERY_V4_STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED'
    assert current['accepted_canonical_result_count']==0
    for flag in ('arm_present','attempt_lock_present','canonical_result_present','real_execution_authorized'):
        assert current[flag] is False
    return historical
