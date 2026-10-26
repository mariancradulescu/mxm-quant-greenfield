import hashlib,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'docs/economic-development/20261026/commission-account-40342741128'
DIGESTS={'original-artificial-stdout.json':'d267d89d0fe9186751c163949d046b13f0f6412d66fb314f948d6fc8af5df691','public-fee-floor-receipt.json':'9d66509eb8812169e5b2d362a187128bd5aad3b411b5429d2a0627b330da4d59'}
def verify(folder=FOLDER):
    results={}
    for name,digest in DIGESTS.items():
        raw=(Path(folder)/name).read_bytes()
        if len(raw)>20000 or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('COMMISSION_ORIGINAL_EVIDENCE_CHANGED')
        results[name]=json.loads(raw)
    a=results['original-artificial-stdout.json'];f=results['public-fee-floor-receipt.json']
    assert a['classification']=='ARTIFICIAL_QUOTES_AND_FX_ONLY' and a['checks']==22 and a['cold_processes']==3 and a['funding_count']==1 and a['orders']==0 and not a['market_account_replay']
    assert a['account']['InitialCapitalEur']==200 and not a['account']['Hard21Proven'] and not a['account']['BrokerFillsProven'] and not a['account']['CostsBrokerVerified']
    assert f['all_floors_independently_reconciled'] and f['source_instruments']==1576 and f['classification_counts']=={'COST_UNRESOLVED_NOT_ELIGIBLE':577,'FEE_HURDLE_ONLY_NOT_FULL_ADMISSION':999}
    assert not f['market_prices_read'] and not f['market_account_replay'] and not f['historical_costs_proven'] and not f['economic_edge_proven'] and not f['hard21_proven'] and f['orders']==0
    return True
class OriginalCosts(unittest.TestCase):
    def test_original_artificial_proof_and_nonmarket_receipt(self):self.assertTrue(verify())
    def test_changed_cost_or_false_promotion_rejected(self):
        for name in DIGESTS:
            with tempfile.TemporaryDirectory() as t:
                for n in DIGESTS:(Path(t)/n).write_bytes((FOLDER/n).read_bytes())
                p=Path(t)/name;b=bytearray(p.read_bytes());b[15]^=1;p.write_bytes(b)
                with self.assertRaises(ValueError):verify(t)
if __name__=='__main__':unittest.main()
