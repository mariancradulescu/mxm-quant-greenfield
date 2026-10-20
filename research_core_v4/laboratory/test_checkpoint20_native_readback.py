import unittest
from copy import deepcopy
from . import checkpoint20_readback as m
from .common import LabError

class NativeReadbackTest(unittest.TestCase):
    def test_legacy_trust_collision_is_reported_without_values_or_repair(self):
        from .data import DataCatalogue
        from .common import digest
        manifest={'instrument':'PRIVATE_SYMBOL','resolution':'BID_ASK','partition':'DEVELOPMENT',
            'start_ms':0,'end_ms':10,'source':'PRIVATE_ORIGIN','source_sha256':'a'*64,
            'available_at_ms':10,'session_semantics':'POINT','completeness':'UNRESOLVED',
            'account_scope':'PRIVATE_ACCOUNT'}
        cat=DataCatalogue(); key=cat.ingest(manifest,[{'t':1,'side':'bid','price':1}])
        old=cat.export(); meta=old['assets'].pop(key); rows=old['rows'].pop(key)
        del meta['identity_version']
        legacy=digest({'manifest':manifest,'normalized':rows});meta['id']=legacy
        old['assets'][legacy]=meta;old['rows'][legacy]=rows
        shared=deepcopy(old); shared['assets'][legacy]['trust']='AUTHENTICATED_NATIVE_CUSTODY'
        original=deepcopy((shared,old))
        result=m.catalogue_diagnostic(shared,old)
        self.assertFalse(result['compatible'])
        self.assertEqual(result['conflicts'][0]['changed_known_fields'],['trust'])
        self.assertTrue(result['conflicts'][0]['same_rows'])
        self.assertEqual((shared,old),original)
        self.assertNotIn('PRIVATE_',str(result))
        self.assertTrue(m.catalogue_diagnostic(old,old)['compatible'])

    def test_workflow_restricts_secret_scope_and_keeps_evidence_read_only(self):
        w=m.build_workflow('a'*40)
        self.assertEqual(w['on'],{'workflow_dispatch':{}})
        self.assertEqual(set(w['jobs']),{'checkpoint20-readback','independent-cold-readback'})
        for j in w['jobs'].values():
            self.assertEqual(j['environment'],'mxm-r3-custody-v1')
            self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
            self.assertEqual(j['steps'][0]['with']['ref'],'a'*40)
            self.assertFalse(j['steps'][0]['with']['persist-credentials'])
            self.assertIn('refs/heads/mxm-remediation-p0-p4-20261015-v1',j['if'])
            env=next(s['env'] for s in j['steps'] if 'env' in s)
            self.assertEqual(set(env),{'GH_TOKEN','R3_CUSTODY_PRIVATE_KEY_PEM'})
        for source in ('main','a'*39,'g'*40):
            with self.assertRaises(LabError):m.build_workflow(source)

    def test_no_reset_check_rejects_each_preserved_component(self):
        before={'sequence':20,'trial_book':{'used':{},'limits':{}},
                'shared_catalogue':{'assets':{'x':1},'rows':{'x':[]},'quarantine':[]},'programmes':{'A':{'value':1}},'pending':None}
        after=deepcopy(before)
        m.preserve_check(before,after)
        for k,v in [('sequence',0),('trial_book',{'used':{},'limits':{'V2':84}}),
                    ('shared_catalogue',{}),('programmes',{}),('pending',{'exposure':'unknown'})]:
            bad=deepcopy(after);bad[k]=v
            with self.subTest(k=k),self.assertRaises(LabError):m.preserve_check(before,bad)

    def test_positive_call_is_not_a_negative_probe(self):
        with self.assertRaises(LabError):m.reject(lambda:True,'FIXTURE')
        def denied():raise ValueError('fixture denial')
        self.assertEqual(m.reject(denied,'FIXTURE'),'FIXTURE')

    def test_public_checkpoint_is_immutable_not_a_favorable_label(self):
        from .test_checkpoint20_forward_migration import source
        state,_=source()
        auth=m.authority(state)
        m.verify_checkpoint20_public(state,auth,m.EVIDENCE)
        for k,v in [('sequence',19),('orders',1),('ciphertext_sha256','0'*64)]:
            bad=deepcopy(state);bad[k]=v
            with self.assertRaises(LabError):m.verify_checkpoint20_public(bad,m.authority(bad),m.EVIDENCE)
