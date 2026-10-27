import copy,json,os,unittest
from unittest.mock import patch
from . import current_margin_reception as n
from . import current_margin_evidence as evidence
class MarginScope(unittest.TestCase):
    def test_fixed_existing_panel_no_prices_or_trial(self):
        self.assertEqual(n.POLICY['original_run'],40455704891);self.assertEqual(n.POLICY['symbol_ids'],[1,2,250])
        for k in ('new_broker_requests','orders','response_tests','economic_model_runs'):self.assertEqual(n.POLICY[k],0)
        self.assertFalse(n.POLICY['market_prices_exported']);self.assertFalse(n.POLICY['automatic_retry'])
    def test_wrong_context_and_any_wrong_role_key_rejected_before_git(self):
        with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
            with self.assertRaisesRegex(ValueError,'NATIVE_CONTEXT'):n.admit()
            git.assert_not_called()
        for key in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM'):
            with patch.dict(os.environ,{key:'artificial'},clear=True):
                with self.assertRaisesRegex(ValueError,'SECRET_ROLE'):n.no_keys()
    def test_one_shot_native_history(self):
        n.one_shot({'total_count':1,'workflow_runs':[{'id':7,'run_attempt':1}]},7)
        for v in ({'total_count':2,'workflow_runs':[{'id':7,'run_attempt':1}]},
          {'total_count':1,'workflow_runs':[{'id':7,'run_attempt':2}]},
          {'total_count':1,'workflow_runs':[{'id':8,'run_attempt':1}]}):
            with self.assertRaises(ValueError):n.one_shot(v,7)
    def test_workflow_exact_read_only_custody_no_other_keys_or_dispatch(self):
        w=n.workflow();self.assertEqual(json.loads((n.ROOT/n.PATH).read_bytes()),w)
        self.assertEqual(w['on'],{'push':{'branches':[n.BRANCH],'paths':[n.PATH]}})
        j=w['jobs'][n.JOB];self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
        self.assertEqual(j['environment'],'mxm-r3-custody-v1')
        secret=[s for s in j['steps'] if 'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in s.get('env',{})]
        self.assertEqual(len(secret),1);self.assertIn(' export ',secret[0]['run']);self.assertNotIn('dotnet',secret[0]['run'])
        for text in ('R3_CTRADER_','SUCCESSOR_APP_PRIVATE_KEY','workflow_dispatch','mxm-r3-pepperstone-v1'):self.assertNotIn(text,json.dumps(w))
        self.assertEqual(j['steps'][-1]['with']['path'],n.OUT)
class NativeMarginExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from .test_spot_observation_reception import NativeSpotWireTests
        NativeSpotWireTests.setUpClass();cls.wire=NativeSpotWireTests()
    def private(self):
        from m6.ctrader_transport import decode_envelope,extract_payload
        import base64
        p=self.wire.private(True)
        for r in p['receipts']:
            env=decode_envelope(base64.b64decode(r['response_wire']));m=extract_payload(env);kind=r['request_type']
            if kind=='ProtoOAAssetListReq':m.asset.add(assetId=2,name='USD')
            if kind=='ProtoOASymbolsListReq':
                for s in m.symbol:s.quoteAssetId=2
            if kind=='ProtoOASymbolByIdReq':
                for s in m.symbol:
                    s.maxVolume=10000000;s.stepVolume=100000;s.lotSize=10000000
                    s.commissionType=2;s.minCommissionType=1;s.minCommissionAsset='USD'
                    s.preciseTradingCommissionRate=350000000;s.preciseMinCommission=0
            if kind=='ProtoOAExpectedMarginReq':m.margin[0].buyMargin=8000;m.margin[0].sellMargin=8001
            r['response_wire']=self.wire.wire(m,r['client_msg_id'])
        return p
    def test_all_three_both_sides_exact_scale_and_no_price_or_identity_export(self):
        rows=evidence.extract(self.private());self.assertEqual([r['symbol_id'] for r in rows],[1,2,250])
        self.assertTrue(all(r['quote_asset']=='USD' for r in rows))
        self.assertTrue(all(r['margin']==dict(volume=100000,buy=8000,sell=8001,money_digits=2) for r in rows))
        for word in ('ctidTraderAccountId','balance','market','bid','ask','response_wire'):self.assertNotIn(word,json.dumps(rows))
    def test_duplicate_or_wrong_request_identity_or_correlation_refused(self):
        for mutate in (lambda p:p['receipts'].append(copy.deepcopy(p['receipts'][7])),
                       lambda p:p['receipts'][7].update(client_msg_id='substituted'),lambda p:p.update(account=43)):
            p=self.private();mutate(p)
            with self.assertRaises(ValueError):evidence.extract(p)
    def test_absent_money_digits_never_falls_back_to_trader_or_default(self):
        import base64
        from m6.ctrader_transport import decode_envelope,extract_payload
        p=self.private();r=p['receipts'][7];m=extract_payload(decode_envelope(base64.b64decode(r['response_wire'])))
        m.ClearField('moneyDigits');r['response_wire']=self.wire.wire(m,r['client_msg_id'])
        rows=evidence.extract(p);self.assertIsNone(rows[0]['margin']['money_digits'])
        self.assertIsNone(evidence.reference(rows)[0]['margin'])
if __name__=='__main__':unittest.main()
