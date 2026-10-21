"""Synthetic policy adversaries only; no Actions dispatch or credential access."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from verification import R3_WORKFLOW_BOUNDARY as b

SOURCE='a'*40
WITNESS={'id':17,'target':'branch','source_type':'Repository','source':b.REPO,
 'enforcement':'active','conditions':{'ref_name':{'include':['refs/heads/'+b.SOURCE_REF],'exclude':[]}},
 'rules':[{'type':x} for x in ('creation','update','deletion','non_fast_forward')],
 'updated_at':'2026-10-21T12:00:00Z','bypass_actors':[]}

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.write('main')

    def write(self,mode):
        expected=b.desired_workflows(mode)
        expected[b.CI]=b.build_ci(SOURCE,mode,WITNESS)
        for path,raw in expected.items():
            p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(raw)

    def verify(self,mode='main'):
        return b.verify_root(self.root,mode,SOURCE,WITNESS)

    def test_all_snapshot_bytes_match_native_git_blob_inventory(self):
        provenance=json.loads((b.SNAPSHOTS/'PROVENANCE.json').read_bytes())
        for mode in ('main','exec'):
            native={row['path']:row['git_blob_sha'] for row in provenance[mode]['files']}
            self.assertEqual(set(native),set(b.baseline(mode)))
            for path,source in b.baseline(mode).items():
                raw=source.encode()
                self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),native[path])

    def test_main_and_execution_namespaces_are_complete_and_credential_routes_finite(self):
        for mode in ('main','exec'):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);expected=b.desired_workflows(mode)
                expected[b.CI]=b.build_ci(SOURCE,mode,WITNESS)
                for path,raw in expected.items():
                    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(raw)
                result=b.verify_root(root,mode,SOURCE,WITNESS)
                self.assertEqual(result['workflow_count'],len(b.baseline(mode)))
                self.assertGreater(len(result['retired_paths']),0)
                for path,raw in expected.items():
                    if path not in b.ACTIVE and path!=b.CI:self.assertFalse(b.legacy_privileged(raw),path)

    def test_previous_installed_guard_accepts_unknown_route_but_whole_guard_refuses(self):
        original=b.ROOT/'verification/workflow-boundary/previous_guard.py.txt'
        namespace={'__name__':'synthetic_previous_guard'};exec(original.read_text(),namespace)
        # Keep the original R7 bytes so this reproduces only the missing namespace check.
        (self.root/'.github/workflows/mxm-integrated-p0.yml').write_text(b.baseline('main')['.github/workflows/mxm-integrated-p0.yml'])
        p=self.root/'.github/workflows/synthetic-never-installed.yml'
        p.write_text('name: synthetic\non: workflow_dispatch\npermissions: {}\njobs:\n  synthetic:\n    environment: mxm-p0-successor-issuer-v1\n    runs-on: ubuntu-24.04\n    steps:\n      - run: echo NEVER_EXECUTED\n        env:\n          SUCCESSOR_APP_PRIVATE_KEY: ${{ secrets.SUCCESSOR_APP_PRIVATE_KEY }}\n')
        namespace['verify'](self.root)
        with self.assertRaisesRegex(ValueError,'BOUNDARY_WORKFLOW_INVENTORY'):self.verify()

    def test_secret_free_alias_filename_also_requires_explicit_admission(self):
        (self.root/'.github/workflows/alias.yaml').write_text('name: alias\non: workflow_dispatch\npermissions: {}\njobs: {}\n')
        with self.assertRaisesRegex(ValueError,'BOUNDARY_WORKFLOW_INVENTORY'):self.verify()

    def test_changed_existing_checkout_is_refused(self):
        p=self.root/'.github/workflows/mxm-integrated-p0.yml'
        p.write_text(p.read_text().replace('dbd0a42bf73f9ae5847a90a4ed159d21e0d7197a','b'*40))
        with self.assertRaisesRegex(ValueError,'BOUNDARY_WORKFLOW_BYTES'):self.verify()

    def test_retired_workflow_cannot_reactivate(self):
        p=self.root/'.github/workflows/mxm-r3-secret-isolation.yml'
        p.write_text(b.baseline('main')[str(p.relative_to(self.root))])
        with self.assertRaisesRegex(ValueError,'BOUNDARY_WORKFLOW_BYTES'):self.verify()

    def test_missing_known_workflow_is_refused(self):
        (self.root/'.github/workflows/mxm-r3-chronology-reception.yml').unlink()
        with self.assertRaisesRegex(ValueError,'BOUNDARY_WORKFLOW_INVENTORY'):self.verify()

    def test_changed_ci_self_contract_is_refused(self):
        p=self.root/b.CI;p.write_text(p.read_text().replace('Whole-workflow namespace','Removed namespace'))
        with self.assertRaisesRegex(ValueError,'BOUNDARY_WORKFLOW_BYTES'):self.verify()

    def test_workflow_symlink_is_refused(self):
        p=self.root/'.github/workflows/mxm-integrated-p0.yml';raw=p.read_text();p.unlink()
        target=self.root/'synthetic-target';target.write_text(raw);p.symlink_to(target)
        with self.assertRaisesRegex(ValueError,'BOUNDARY_WORKFLOW_FILE_TYPE'):self.verify()

    def test_dynamic_environment_and_reusable_inherited_secrets_are_privileged(self):
        for job in ({'environment':'${{ inputs.environment }}'}, {'uses':'external/repo/.github/workflows/entry.yml@main','secrets':'inherit'}):
            self.assertTrue(b.legacy_privileged(json.dumps({'permissions':{},'jobs':{'synthetic':job}})))

    def test_policy_drift_or_bypass_refuses_read_only_source_admission(self):
        class Route:
            def __init__(self,policy):self.policy=policy
            def json(self,path):
                return {'object':{'sha':SOURCE}} if path.startswith('git/ref/') else self.policy
        b.verify_seal(Route(copy.deepcopy(WITNESS)),SOURCE,WITNESS)
        for field,value in [('updated_at','2026-10-21T12:00:01Z'),('bypass_actors',[{'actor_id':1}])]:
            changed=copy.deepcopy(WITNESS);changed[field]=value
            with self.assertRaises(ValueError):b.verify_seal(Route(changed),SOURCE,WITNESS)

    def test_same_revision_redacted_actor_metadata_uses_exact_public_witness(self):
        policy=copy.deepcopy(WITNESS);policy.pop('bypass_actors')
        class Route:
            def json(self,path):return {'object':{'sha':SOURCE}} if path.startswith('git/ref/') else policy
        b.verify_seal(Route(),SOURCE,WITNESS)
