"""Original sealed cutoff and protected availability; artificial bars only."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest
from .common import LabError
from . import common,data,economics,science,volume_pressure
from .fixtures import programme,T


class PartitionAuthority(unittest.TestCase):
    def test_all_consumers_use_exact_original_sealed_cutoff(self):
        expected=1789646578000
        for module in (common,data,economics,science,volume_pressure):
            with self.subTest(module=module.__name__):
                self.assertEqual(getattr(module,'DEVELOPMENT_END_MS',None),expected)

    def test_modified_original_authority_is_refused(self):
        loader=getattr(common,'development_end_ms',None)
        self.assertTrue(callable(loader))
        root=Path(__file__).resolve().parents[2]
        budget=(root/'V2_SEARCH_BUDGET_V1.json').read_bytes()
        wave=(root/'discovery/WAVE_01_V1.json').read_bytes()
        with patch.object(Path,'read_bytes',side_effect=[budget,wave+b' ']):
            with self.assertRaisesRegex(LabError,'FROZEN_PARTITION_AUTHORITY'):loader()

    def test_historical_bar_with_protected_availability_is_refused(self):
        x=deepcopy(programme()['tasks']['validate_data']['input'])
        x['rows'][0]['available_at']=1789646578000
        with self.assertRaisesRegex(LabError,'PROTECTED_ROW_AVAILABILITY'):
            data.DataCatalogue().ingest(x['manifest'],x['rows'])

    def test_protected_decision_cannot_read_development_cache(self):
        x=programme()['tasks']['validate_data']['input'];cache=data.DataCatalogue()
        ident=cache.ingest(x['manifest'],x['rows'])
        with self.assertRaisesRegex(LabError,'PROTECTED_READ_GATE'):
            cache.view(ident,1789646578000)
        self.assertEqual(cache.view(ident,T),x['rows'])


if __name__=='__main__':unittest.main()
