"""Focused negative provenance controls against the integrated R2 source.

Run with the R2 repository root on PYTHONPATH. No checkpoint is mutated or
economic programme executed. Positive bindings are the native encrypted proofs.
"""
import unittest
from copy import deepcopy
from research_core_v4.laboratory.protocol import (
    migrate_private,typed_source_transition,ORIGINAL_SOURCE,ORIGINAL_CIPHER,
    ORIGINAL_PUBLIC,
)

class ProvenanceNegatives(unittest.TestCase):
    def test_original_source_not_an_unrestricted_allowlist(self):
        s={'sequence':16,'source_sha':'0'*40,'ciphertext_sha256':ORIGINAL_CIPHER}
        with self.assertRaisesRegex(Exception,'TRANSITION_EXACT_ORIGINAL'):
            migrate_private({},s,{},[],'a'*40,ORIGINAL_PUBLIC)
    def test_original_cipher_cannot_be_substituted(self):
        s={'sequence':16,'source_sha':ORIGINAL_SOURCE,'ciphertext_sha256':'0'*64}
        with self.assertRaisesRegex(Exception,'TRANSITION_EXACT_ORIGINAL'):
            migrate_private({},s,{},[],'a'*40,ORIGINAL_PUBLIC)
    def test_original_public_bytes_cannot_be_substituted(self):
        s={'sequence':16,'source_sha':ORIGINAL_SOURCE,'ciphertext_sha256':ORIGINAL_CIPHER}
        with self.assertRaisesRegex(Exception,'TRANSITION_EXACT_ORIGINAL'):
            migrate_private({},s,{},[],'a'*40,'0'*64)
    def test_open_original_is_not_a_migration_source(self):
        s={'sequence':16,'source_sha':ORIGINAL_SOURCE,'ciphertext_sha256':ORIGINAL_CIPHER}
        private={'source_sha':ORIGINAL_SOURCE,'sequence':16,'pending':{'fixture':True}}
        before=deepcopy(private)
        with self.assertRaisesRegex(Exception,'TRANSITION_CLOSED_PREDECESSOR'):
            migrate_private(private,s,{},[],'a'*40,ORIGINAL_PUBLIC)
        self.assertEqual(private,before)
    def test_typed_successor_authority_does_not_accept_other_source(self):
        a={'source_sha':'0'*40,'sequence':19,'ciphertext_sha256':'0'*64,'private_sha256':'0'*64}
        with self.assertRaisesRegex(Exception,'TYPED_SOURCE_TRANSITION_AUTHORITY'):
            typed_source_transition({}, {},a,'a'*40)
    def test_typed_private_cannot_be_substituted_even_with_public_authority(self):
        a={'source_sha':'541bfe0e7d1eea060aa38d9e1e46a6639b7db13b','sequence':19,'ciphertext_sha256':'cb14705c8456668c273f3c19a55bde40839e5be13c92cb43ad36b5cd61dc71b5','private_sha256':'47c34e6307d247e03c95f2727112bcbbaee7e40d6a07f104f20b16e622be8102'}
        p={'source_sha':a['source_sha'],'sequence':19}
        s={'source_sha':a['source_sha'],'sequence':19,'ciphertext_sha256':a['ciphertext_sha256']}
        with self.assertRaisesRegex(Exception,'TYPED_SOURCE_TRANSITION_PROVENANCE'):
            typed_source_transition(p,s,a,'a'*40)

if __name__=='__main__':unittest.main(verbosity=2)
