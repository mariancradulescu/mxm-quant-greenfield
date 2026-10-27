"""Independent scope/provenance negatives, no decryption or market replay."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from . import gbpusd_source_exposure as n
from .common import bytes_digest,encoded
class GbpSourceExposure(unittest.TestCase):
    def originals(self):
        c=n.SOURCES['GBPUSD']
        m=json.loads((n.ROOT/n.ARCHIVE/'MANIFEST.json').read_bytes())
        b={'symbol':'GBPUSD','source_run':c['run'],'source_code':c['code'],'source_trigger':c['trigger'],
           'cipher_sha256':c['cipher'],'private_sha256':c['private'],'events':c['bid']+c['ask'],
           'derived_sha256':'a'*64,'orders':0,'strategy_trials':0,'economic_outcomes':0,
           'historical_arrival_order_proven':False,'historical_costs_proven':False}
        return b,m
    def test_exact_preexisting_identity_and_window(self):
        b,m=self.originals();r=n.source_receipt(b,m)
        self.assertEqual((r['run'],r['rows']),(40179011821,1275114))
        self.assertEqual((r['first_ms'],r['end_ms']),(n.START,n.END))
    def test_no_symbol_source_period_or_economic_promotion_substitution(self):
        for field,value in [('symbol','EURUSD'),('source_run',39917922508),('source_code','bad'),
          ('source_trigger','bad'),('cipher_sha256','bad'),('private_sha256','bad'),('events',1),
          ('orders',1),('strategy_trials',1),('economic_outcomes',1),
          ('historical_arrival_order_proven',True),('historical_costs_proven',True)]:
            b,m=self.originals();b[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):n.source_receipt(b,m)
        for field,value in [('symbol_id',1),('symbol_name','EURUSD'),('from_ms',n.START+1),('to_ms',n.END-1)]:
            b,m=self.originals();m['policy'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):n.source_receipt(b,m)
    def test_wrong_context_and_key_stop_before_git_or_network(self):
        with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
            with self.assertRaisesRegex(ValueError,'NATIVE_CONTEXT'):n.admit()
            git.assert_not_called()
        env={'GITHUB_REPOSITORY':n.REPO,'GITHUB_REF_NAME':n.BRANCH,'GITHUB_EVENT_NAME':'push',
             'GITHUB_RUN_ATTEMPT':'1','GITHUB_JOB':n.JOB,
             'GITHUB_WORKFLOW_REF':n.REPO+'/'+n.PATH+'@refs/heads/'+n.BRANCH}
        for key in n.SECRET_NAMES:
            with patch.dict(os.environ,{**env,key:'artificial'},clear=True),patch.object(n.subprocess,'check_output') as git:
                with self.assertRaisesRegex(ValueError,'NO_KEYS_BEFORE_ADMISSION'):n.admit()
                git.assert_not_called()
    def test_no_second_attempt(self):
        for history in ({'total_count':0,'workflow_runs':[]},
            {'total_count':1,'workflow_runs':[{'id':9,'run_attempt':2}]},
            {'total_count':2,'workflow_runs':[{'id':9,'run_attempt':1}]}):
            with self.assertRaises(ValueError):n.one_shot(history,9)
    def test_exact_workflow_custody_scope_and_no_eurusd_redecode(self):
        w=n.workflow();self.assertEqual(json.loads((n.ROOT/n.PATH).read_bytes()),w)
        self.assertEqual(w['on'],{'push':{'branches':[n.BRANCH],'paths':[n.PATH]}})
        j=w['jobs'][n.JOB];self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
        self.assertEqual(j['environment'],'mxm-r3-custody-v1')
        secret=[s for s in j['steps'] if 'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in s.get('env',{})]
        self.assertEqual(len(secret),1);self.assertIn('export GBPUSD',secret[0]['run'])
        body=json.dumps(w)
        for banned in ('export EURUSD','R3_CTRADER_','SUCCESSOR_APP_PRIVATE_KEY','dotnet','workflow_dispatch'):
            self.assertNotIn(banned,body)
        self.assertEqual(j['steps'][-1]['with']['path'],n.OUT)
    def test_artificial_full_path_preserves_invalid_groups_and_never_promotes(self):
        # Exercise new receipt translation + shared production profiler together.
        b,m=self.originals()
        rows=[]
        for t in range(n.START,n.START+303000,3000):
            rows.extend(({'t':t,'side':'bid','raw':100},{'t':t,'side':'ask','raw':102}))
        # A crossed book terminates the observed stretch, never discarded.
        rows.extend(({'t':n.START+303000,'side':'bid','raw':110},
                     {'t':n.START+303000,'side':'ask','raw':105}))
        raw=b''.join(encoded(e)+b'\n' for e in rows)
        r=n.source_receipt(b,m)
        # Artificial counts replace the large original only AFTER identity adapter.
        r.update(rows=len(rows),derived_sha256=bytes_digest(raw));m['quote_events']=len(rows)
        m.pop('bid_events',None);m.pop('ask_events',None)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'artificial';p.write_bytes(raw);result=n.profile(p,r,m)
            self.assertEqual(result['observed_groups'],102)
            self.assertEqual(result['healthy_observation_groups'],101)
            self.assertEqual(result['unavailable_observation_groups'],1)
            self.assertEqual(result['observed_stretches_at_least_5min'],1)
            self.assertFalse(result['broker_fills_proven'])
            self.assertFalse(result['historical_execution_costs_proven'])
            p.write_bytes(raw+b'{}\n')
            with self.assertRaises(ValueError):n.profile(p,r,m)
if __name__=='__main__':unittest.main()
