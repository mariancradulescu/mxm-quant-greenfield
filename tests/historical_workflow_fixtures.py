"""Byte-bound test inputs from historical commits; never installed workflows."""
import hashlib
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    'staging': ('db23bc18b85214a71bfb093b8416e3f51ade175c',
                '.github/workflows/v4-asymmetric-staging-bootstrap.yml',
                '64d146c80a117f0a666025264ee72bf7dde8ee848c72c6ff8e799f5d401111f1',
                'b0831d41f19e9f3825e53c5b6ac19ccab8723027'),
    'm6': ('fe551a1c45f63209b63f90459c2b8366a68662a6',
           '.github/workflows/m6_preparation.yml',
           '3ad5f973e44de9511592f8d565cb113835e27847f2ad6e56fe2a94a725e94f5e',
           '43e9fa810385993cdd637ab0461c2a69c1abd83e'),
}

def historical_workflow_source(name):
    _, _, expected, blob = FIXTURES[name]
    raw = (ROOT / 'docs/laboratory-completion/20261020/historical-workflow-fixtures' / (name+'.txt')).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected, 'HISTORICAL_FIXTURE_SHA256'
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == blob, 'HISTORICAL_FIXTURE_GIT_BLOB'
    return raw.decode('utf-8')

def assert_current_quarantined(name):
    _, path, _, _ = FIXTURES[name]
    installed = yaml.load((ROOT/path).read_text(), Loader=yaml.BaseLoader)
    assert set(installed) == {'name','on','permissions','jobs'}
    assert installed['name'].startswith('Archived by P0-P4 remediation: ')
    assert installed['on'] == {'workflow_dispatch': ''}
    assert installed['permissions'] == {}
    assert installed['jobs'] == {'expected_policy_stop': {
        'if': '${{ false }}', 'runs-on': 'ubuntu-24.04', 'timeout-minutes': '1',
        'steps': [{'run':'echo EXPECTED_POLICY_STOP_LEGACY_AUTHORITY_SUPERSEDED'}]}}
