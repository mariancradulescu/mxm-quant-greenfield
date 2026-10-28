import json,unittest
from .anchor_existing_metadata_readback import workflow,ROOT,PATH
class OriginalReadback(unittest.TestCase):
 def test_only_custody_and_exact_single_readback_route(self):
  w=workflow();self.assertEqual(json.loads((ROOT/PATH).read_bytes()),w)
  self.assertEqual(set(w['on']),{'push'});self.assertEqual(len(w['jobs']),1)
  job=w['jobs']['original-readback'];self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
  raw=json.dumps(w);self.assertNotIn('R3_CTRADER',raw);self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',raw)
  self.assertEqual(sum('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in x.get('env',{}) for x in job['steps']),1)
class TypedIdentities(unittest.TestCase):
 def test_active_and_archived_native_schemas_never_invent_fields(self):
  from m6.ctrader_proto import OpenApiModelMessages_pb2 as m
  from .anchor_existing_metadata_readback import project_symbol
  a=m.ProtoOALightSymbol(symbolId=250,symbolName='SpotCrude',enabled=True,baseAssetId=10,quoteAssetId=20)
  z=m.ProtoOAArchivedSymbol(symbolId=7393,name='WTOIL-PERP',utcLastUpdateTimestamp=1)
  old=m.ProtoOAArchivedSymbol(symbolId=250,name='OldName',utcLastUpdateTimestamp=1)
  row=project_symbol(7393,{10:'WTI',20:'USD'},{250:a},{7393:z},{})
  self.assertEqual(row['name'],'WTOIL-PERP');self.assertTrue(row['archived']);self.assertIsNone(row['quote']);self.assertIsNone(row['enabled']);self.assertFalse(row['full_present'])
  active=project_symbol(250,{10:'WTI',20:'USD'},{250:a},{250:old},{})
  self.assertEqual(active['name'],'SpotCrude');self.assertEqual(active['quote'],'USD');self.assertFalse(active['archived']);self.assertTrue(active['enabled'])
  empty=m.ProtoOALightSymbol(symbolId=7)
  self.assertIsNone(project_symbol(7,{}, {7:empty},{},{})['quote'])
if __name__=='__main__':unittest.main()
