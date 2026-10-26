import hashlib,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/'docs/economic-development/20261026/eur-book-40319142037/receipt.json'
def verify(path=PATH):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!='ef2e4fd7c3fb41f67f4425e42ab1ef95da945fa1ea7b214c37bf1416e8df46dd':raise ValueError('EUR_BOOK_PUBLIC_RECEIPT_CHANGED')
    r=json.loads(raw)
    assert r['schema']=='mxm.eur-book-reception-public.v1' and r['run_id']==40319142037 and r['source_sha']=='3be1c18f182049edd10a641fac26d55895751776'
    assert r['original_economic_run']==40285218660 and r['original_guard_source_class']=='OBSERVED_LOCKED' and r['original_cursor_and_source_authenticated'] and r['independent_every_group_reconciled']
    assert sum(v['rows'] for v in r['sources'].values())==2129692 and sum(v['groups'] for v in r['sources'].values())==1208751
    assert all(r[k] is False for k in ('closed_policy_changed','market_account_replay','historical_fills_proven','hard21_proven','economic_edge_proven','native_ctrader_runtime_reception'))
    assert r['new_models']==r['new_economic_outcomes']==r['new_broker_requests']==r['orders']==0
    return r
class OriginalReception(unittest.TestCase):
    def test_original_diagnostic_no_promotion(self):self.assertEqual(verify()['original_guard_source_class'],'OBSERVED_LOCKED')
    def test_altered_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'receipt';p.write_bytes(PATH.read_bytes().replace(b'OBSERVED_LOCKED',b'OBSERVED_POSITIVE_SPREAD'))
            with self.assertRaises(ValueError):verify(p)
if __name__=='__main__':unittest.main()
