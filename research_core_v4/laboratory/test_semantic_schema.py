"""Prospective semantic transition; synthetic specifications, no outcome opening."""
from copy import deepcopy
import unittest
from discovery.canonical import freeze_spec
from .admission import TypedTrialBook,bootstrap_typed_book,semantic_hash
from .common import LabError,digest
from .fixtures import candidate
from .test_admission import policies


class SemanticSchema(unittest.TestCase):
    def original(self):
        raw=candidate('V2-C990101','p');raw['parameters']={'lookback':20,'threshold':.25}
        raw['universe']=['B','A'];return freeze_spec(raw)

    def book(self):
        original=self.original()
        legacy={'limits':{'V2':84},'used':{'V2':22},'identities':{'V2:V2-C033':{'spec_hash':'c'*64,'units':1,'state':'RESERVED'}}}
        history={'V2':{'used':21,'result_observations':29,'charged':['opened-'+str(i) for i in range(21)]}}
        b=bootstrap_typed_book(history,legacy,[original])
        b._append('FINGERPRINT_INDEX_UPGRADED',{'previous_index_sha256':digest(b.semantic_registry),
            'identity_semantics':{original['id']:semantic_hash(original,2)},
            'source_spec_hashes':{original['id']:original['spec_hash']},'source_sha':'a'*40})
        return b,original

    def test_numeric_cosmetic_and_universe_equivalence(self):
        original=self.original();changed=deepcopy(original)
        changed.update(id='V2-C990102',rationale='Different label',hypothesis_dimensions={'annotation':'only'})
        changed['parameters']['lookback']=20.0;changed['universe'].reverse()
        self.assertEqual(semantic_hash(original,3),semantic_hash(changed,3))
        changed['parameters']['lookback']=21
        self.assertNotEqual(semantic_hash(original,3),semantic_hash(changed,3))
        changed['parameters']['lookback']=True
        self.assertNotEqual(semantic_hash(original,3),semantic_hash(changed,3))

    def test_unknown_top_level_field_is_not_a_new_identity(self):
        value=self.original();value['note']='cosmetic escape'
        with self.assertRaisesRegex(LabError,'SEMANTIC_SCHEMA_FIELDS'):semantic_hash(value,3)

    def test_large_integers_are_not_rounded_by_decimal_context(self):
        a=self.original();b=deepcopy(a)
        a['parameters']['lookback']=10**35;b['parameters']['lookback']=10**35+1
        self.assertNotEqual(semantic_hash(a,3),semantic_hash(b,3))

    def test_additive_transition_retains_all_history_and_roundtrips(self):
        b,c=self.book();before=b.export();indices=deepcopy(b.semantic_registry)
        b.upgrade_semantic_schema([c],'b'*40)
        self.assertEqual(b.baseline,before['baseline'])
        self.assertEqual(b.events[:-1],before['events'])
        self.assertTrue(all(b.semantic_registry[h]==ids for h,ids in indices.items()))
        self.assertEqual(b.view()['lanes'],before['view']['lanes'])
        self.assertEqual(b.view()['economic_observations'],29);self.assertEqual(b.view()['refunds'],0)
        self.assertEqual(TypedTrialBook.restore(b.export()).export(),b.export())

    def test_changed_missing_or_repeated_transition_refused_without_mutation(self):
        for mode in ('changed','missing','repeated'):
            b,c=self.book()
            if mode=='repeated':b.upgrade_semantic_schema([c],'b'*40)
            before=b.export();source=deepcopy(c)
            if mode=='changed':source['parameters']['lookback']=21;source=freeze_spec(source)
            with self.subTest(mode=mode),self.assertRaises(LabError):
                b.upgrade_semantic_schema([] if mode=='missing' else [source],'b'*40)
            self.assertEqual(b.export(),before)

    def test_equivalent_cross_lane_reservation_does_not_reset_capacity(self):
        b,c=self.book();b.upgrade_semantic_schema([c],'b'*40)
        policies(b,lane='DISTINCT_FIXTURE');renamed=deepcopy(c)
        renamed.update(id='V2-C990102',rationale='Label only');renamed['parameters']['lookback']=20.0
        renamed=freeze_spec(renamed);before=b.export()
        with self.assertRaisesRegex(LabError,'SEMANTIC_DUPLICATE'):
            b.reserve('DISTINCT_FIXTURE',renamed['id'],renamed['spec_hash'],1,candidate=renamed,programme='p')
        self.assertEqual(b.export(),before)
        changed=deepcopy(renamed);changed['parameters']['lookback']=21;changed=freeze_spec(changed)
        b.reserve('DISTINCT_FIXTURE',changed['id'],changed['spec_hash'],1,candidate=changed,programme='p')
        self.assertEqual(TypedTrialBook.restore(b.export()).export(),b.export())
        self.assertEqual(b.view()['lanes']['DISTINCT_FIXTURE']['reservation_holds'],1)
        self.assertEqual(b.view()['lanes']['DISTINCT_FIXTURE']['outcome_charged'],0)


if __name__=='__main__':unittest.main()
