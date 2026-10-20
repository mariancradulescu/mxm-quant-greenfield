"""Preserve both historic trust variants; never make ambiguous data executable."""
import unittest
from copy import deepcopy
from .common import digest,LabError
from .data import DataCatalogue
from .execution import catalogue_extends

def legacy():
    manifest={'instrument':'X','resolution':'BID_ASK','partition':'DEVELOPMENT',
        'start_ms':0,'end_ms':10,'source':'PEPPERSTONE_TEST','source_sha256':'a'*64,
        'available_at_ms':10,'session_semantics':'POINT','completeness':'CONFIRMED_COMPLETE',
        'account_scope':'existing'}
    cat=DataCatalogue();ident=cat.ingest(manifest,[{'t':1,'side':'bid','price':1},
        {'t':2,'side':'ask','price':2}],trust='AUTHENTICATED_NATIVE_CUSTODY')
    value=deepcopy(cat.export());meta=value['assets'].pop(ident);rows=value['rows'].pop(ident)
    del meta['identity_version'];ident=digest({'manifest':manifest,'normalized':rows})
    meta['id']=ident;value['assets'][ident]=meta;value['rows'][ident]=rows
    other=deepcopy(value);other['assets'][ident]['trust']='UNVERIFIED'
    return value,other,ident

class LegacyQuarantineTests(unittest.TestCase):
    def test_quarantined_legacy_asset_cannot_be_read_or_declared_complete(self):
        shared,saved,ident=legacy()
        shared['quarantine'].append({'reason':'LEGACY_TRUST_PROVENANCE_CONFLICT',
            'asset_id':ident,'metadata_variants':[shared['assets'][ident],saved['assets'][ident]]})
        cat=DataCatalogue.restore(shared)
        with self.subTest(path='query'):
            self.assertEqual(cat.query('X','BID_ASK',0,10,authentic_only=True),[])
        with self.subTest(path='view'),self.assertRaises(LabError):cat.view(ident,10)

    def test_migration_preserves_variants_but_refuses_query_and_view(self):
        from .execution import quarantine_legacy_trust_conflicts
        shared,saved,ident=legacy();before=deepcopy((shared,saved))
        with self.assertRaises(LabError):catalogue_extends(shared,saved)
        repaired=quarantine_legacy_trust_conflicts(shared,[saved])
        self.assertEqual((shared,saved),before)
        self.assertEqual(repaired['assets'],shared['assets'])
        self.assertEqual(repaired['rows'],shared['rows'])
        catalogue_extends(repaired,shared);catalogue_extends(repaired,saved)
        cat=DataCatalogue.restore(repaired)
        self.assertEqual(cat.query('X','BID_ASK',0,10,authentic_only=True),[])
        self.assertFalse(cat.structural_support(ident,0,10))
        with self.assertRaises(LabError):cat.view(ident,10)
        self.assertEqual(quarantine_legacy_trust_conflicts(repaired,[saved]),repaired)
        forged=deepcopy(repaired);forged['quarantine'][0]['metadata_variants']=[shared['assets'][ident]]
        with self.assertRaises(LabError):catalogue_extends(forged,saved)

    def test_only_exact_legacy_trust_conflicts_are_repairable(self):
        from .execution import quarantine_legacy_trust_conflicts
        shared,saved,ident=legacy()
        for mutate in [lambda s:s['assets'][ident].update(row_count=999),
                       lambda s:s['assets'].pop(ident),
                       lambda s:s['rows'][ident][0].update(price=4)]:
            bad=deepcopy(saved);mutate(bad)
            with self.assertRaises(LabError):quarantine_legacy_trust_conflicts(shared,[bad])
        new=DataCatalogue();m={k:v for k,v in shared['assets'][ident].items() if k not in
            {'id','normalized_sha256','row_count','conflicts','invalid','interpolated','trust'}}
        key=new.ingest(m,shared['rows'][ident],trust='AUTHENTICATED_NATIVE_CUSTODY')
        forged=deepcopy(new.export());forged['assets'][key]['trust']='UNVERIFIED'
        with self.assertRaises(LabError):quarantine_legacy_trust_conflicts(new.export(),[forged])

    def test_both_feature_paths_refuse_quarantined_inputs(self):
        from .test_volume_pressure import VolumePressure
        from .volume_pressure import volume_pressure_intents
        from .science import causal_intents
        _,spec,cache=VolumePressure().setup_case()
        cache.quarantine.append({'reason':'LEGACY_TRUST_PROVENANCE_CONFLICT','asset_id':'a'})
        with self.assertRaisesRegex(LabError,'CACHE_PROVENANCE_QUARANTINED'):
            volume_pressure_intents(spec,cache,{'A':'a'})
        spec={'parameters':{'causal_dsl':{'entry_delay_ms':1,'hold_ms':1}}}
        with self.assertRaisesRegex(LabError,'CACHE_PROVENANCE_QUARANTINED'):
            causal_intents(spec,cache,{'x':'a'})
