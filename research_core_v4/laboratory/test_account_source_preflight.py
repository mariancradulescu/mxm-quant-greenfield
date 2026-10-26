import hashlib,json,tempfile,unittest
from pathlib import Path
from .account_source_preflight import scan,consecutive
from .intrinsic_reference import snapshots
class SourceAdmission(unittest.TestCase):
    def run_source(self,events,mutate=None,**kw):
        raw=b''.join((json.dumps(e)+'\n').encode() for e in events)
        m={'quote_events':len(events),'source_run_id':1,'members':{'capture.mxmenc':{'sha256':'a'}},'private_sha256':'b','code_source':'c','source_head':'d'}
        r={'rows':len(events),'run':1,'cipher_sha256':'a','private_sha256':'b','source_code':'c','source_trigger':'d','first_ms':0,'end_ms':20000,'derived_sha256':hashlib.sha256(raw).hexdigest()}
        if mutate:mutate(r,m)
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'source';p.write_bytes(raw);v=scan(p,r,m,**kw)
            # Independent legacy array consumer and new streaming preflight
            # must agree on every unavailable timestamp, without a strategy.
            if not kw:self.assertEqual(v['unavailable_groups'],sum(q is None for _,q in snapshots(p)))
            return v
    def test_real_export_contract_async_stale_ambiguous_and_locked(self):
        def e(t,s,v):return {'t':t,'side':s,'raw':v}
        rows=[e(0,'bid',100),e(0,'ask',102),e(5000,'bid',101),e(5001,'bid',101),e(6000,'ask',103),e(6000,'ask',104),e(7000,'ask',101),e(8000,'ask',105)]
        v=self.run_source(rows);self.assertEqual(v['unavailable_groups'],3);self.assertEqual(set(v['reasons']),{'STALE_SIDE','AMBIGUOUS_SIDE','LOCKED_BOOK_CONSUMER_REJECTS'})
        self.assertEqual(v['admission'],'REQUIRES_EXPLICIT_EXPOSURE_PATH_GUARD');self.assertFalse(v['economic_evaluation_performed'])
    def test_manifest_without_redundant_side_counts_valid_but_contradiction_fails(self):
        rows=[{'t':1,'side':'bid','raw':100},{'t':1,'side':'ask','raw':102}]
        self.assertEqual(self.run_source(rows)['admission'],'SOURCE_CONTRACT_PASS_ONLY')
        with self.assertRaises(ValueError):self.run_source(rows,lambda r,m:m.update(bid_events=99))
        with self.assertRaises(ValueError):self.run_source(rows,lambda r,m:r.update(derived_sha256='0'*64))
        with self.assertRaises(ValueError):self.run_source(rows,lambda r,m:r.update(source_code='other'))
    def test_no_sorting_no_future_no_bool_timestamp(self):
        for rows in ([{'t':2,'side':'bid','raw':100},{'t':1,'side':'ask','raw':102}],[{'t':20000,'side':'bid','raw':100}],[{'t':True,'side':'bid','raw':100}]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):self.run_source(rows)
    def test_consecutive_is_not_executable_coverage(self):
        self.assertTrue(consecutive([{'first_ms':0,'end_ms':10},{'first_ms':10,'end_ms':20}]))
        with self.assertRaises(ValueError):consecutive([{'first_ms':0,'end_ms':10},{'first_ms':11,'end_ms':20}])
if __name__=='__main__':unittest.main()
