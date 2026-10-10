from pathlib import Path
import json,hashlib,gzip,re,zipfile,io,sys
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
from cryptography.hazmat.primitives import padding
import dnfile
from dncil.cil.body import CilMethodBody
from dncil.cil.body.reader import CilMethodBodyReaderBytes
r=Path(sys.argv[1]);out=Path(sys.argv[2])
h=lambda b:hashlib.sha256(b).hexdigest()
p=(r/'cloud_delivery_preflight_v1.algo').read_bytes();assert p[:5]==b'algo\x02'
n=int.from_bytes(p[5:9],'big');metadata=json.loads(gzip.decompress(p[9:9+n]));rem=p[9+n:];l=int.from_bytes(rem[:4],'big');assert l==16
fmt=(r/'SDK_FORMAT_REVIEW.cs').read_text();key=bytes(map(int,re.search(r'FormatV2Key = new byte\[32\]\s*\{(.*?)\}',fmt,re.S).group(1).replace('\n','').replace('\t','').split(',')))
d=Cipher(algorithms.AES(key),modes.CBC(rem[4:4+l])).decryptor();plain=d.update(rem[4+l:])+d.finalize();u=padding.PKCS7(128).unpadder();plain=u.update(plain)+u.finalize();z=zipfile.ZipFile(io.BytesIO(plain))
expected=['lib/MXM_DeliveryProbe_20261012.dll','lib/MXM_DeliveryProbe_20261012.deps.json'];assert z.namelist()==expected
inventory=[]
for name in expected:
 b=z.read(name);assert b==(r/name.split('/')[-1]).read_bytes();inventory.append({'path':name,'bytes':len(b),'sha256':h(b),'exact_build_output_match':True})
assert metadata['Store']['SourceIncluded']==False
assert len(metadata['Types'])==1 and metadata['Types'][0]['TypeName']=='Mxm.Native.Preflight.DeliveryProbe' and metadata['Types'][0]['Capabilities']==[] and metadata['Types'][0]['Parameters']==[]
pe=dnfile.dnPE(str(r/'MXM_DeliveryProbe_20261012.dll'))
assemblies=[str(x.Name) for x in pe.net.mdtables.AssemblyRef];assert set(assemblies)=={'System.Runtime','System.Collections','cAlgo.API'}
refs=[]
for row in pe.net.mdtables.MemberRef:
 c=row.Class.row;refs.append({'namespace':str(getattr(c,'TypeNamespace','')),'type':str(getattr(c,'TypeName','')),'member':str(row.Name),'parent_table':row.Class.table.name})
for item in refs:
 assert not any(s.lower() in (item['namespace']+'.'+item['type']+'.'+item['member']).lower() for s in ['ExecuteMarket','Place','Modify','ClosePosition','CloseTrade','CancelOrder','OrderAsync','System.Net','System.IO','WebSocket','Http','Reflection.Emit','Assembly.Load','Process.Start','Account','Equity','Balance'])
counts={n:len(getattr(pe.net.mdtables,n).rows) if getattr(pe.net.mdtables,n,None) else 0 for n in ['ManifestResource','ImplMap','File','ExportedType']};assert not any(counts.values())
methods=[];strings=[]
for row in pe.net.mdtables.MethodDef:
 assert not row.Flags.mdPinvokeImpl
 if not row.Rva:continue
 body=CilMethodBody(CilMethodBodyReaderBytes(pe.get_data(row.Rva,16000)))
 assert not any(str(x.opcode) in ['calli','jmp','localloc'] for x in body.instructions)
 for ins in body.instructions:
  if str(ins.opcode)=='ldstr':strings.append(pe.net.user_strings.get(ins.operand.value&0xFFFFFF).value)
 methods.append({'name':str(row.Name),'instructions':len(body.instructions),'all_CIL_decoded':True})
source=(out/'csharp/DeliveryProbe.cs').read_bytes();assert source==(r/'REVIEW_SOURCE.cs').read_bytes()
report={'schema':'mxm.whole.prepared.algo.inspection.v1','status':'WHOLE_PACKAGE_AND_COMPILED_PAYLOAD_INSPECTED_NO_DEPLOYMENT','build_head':'d084cf9043a484ea6172c865bead3ddc13ac1677','run':38051789921,'job':114212234169,'attempt':1,'result':'SUCCESS','artifact_id':11669830778,'artifact_zip_sha256':'edfbeea5a957513e5b1b5140eb1160cbd54da57bd240703897a45bdcc46330ef','algo_sha256':h(p),'algo_bytes':len(p),'compiled_dll_sha256':h((r/'MXM_DeliveryProbe_20261012.dll').read_bytes()),'source_sha256':h(source),'inspection':'Decoded entire own SDK-generated algo v2 container, inventoried every ZIP entry, compared embedded DLL/deps byte-for-byte with build outputs; decoded every method CIL; manually reviewed complete decompiled class and every reference/log operand. Not merely grep of source. SDK distribution format is not owner market-data encryption.','inventory':inventory,'metadata':metadata,'assembly_refs':assemblies,'member_refs':refs,'method_bodies':methods,'embedded_resources_native_imports_additional_modules':counts,'compiled_strings':sorted(set(strings)),'order_calls':False,'external_connections':False,'private_publication_calls':False,'financial_account_reads':False,'logs':'fixed technical counter fields and fixed symbol names only; no price, account values, credentials, exception text or position IDs','original_source_preserved':True,'actual_runtime_verified':False,'authenticity_limit':'Git source/build provenance + hashes + embedded payload equality; not broker-signed package, not proof of installed package identity or platform acceptance','startup_window_UTC':['2026-10-12T12:00:00Z','2026-10-12T12:01:00Z'],'absolute_deadline_UTC':'2026-10-12T12:30:00Z','deadline_restart_resets':False,'unconditional_wall_clock_kill_guarantee':False,'global_one_instance_proof':False,'platform_auto_restart_disabled':False,'deployment_readiness':'BLOCKED_PENDING_OWNER_APPROVAL_ACCOUNT_SYMBOL_CLOUD_CHECK_AND_PLATFORM_RESTART_POLICY_RESOLUTION','limits':['Platform automatic crash restart cannot be disabled/proven disabled through authorized capabilities here; restart within first minute could re-admit, beyond first minute it refuses collection','No cross-instance storage or service: owner must enforce exactly one instance in platform UI','Timer/event guard requests Stop at first callback, not external hard kill of frozen process','No authorized authenticated deployment provider or installed account Cloud symbol view; no login/session probing performed'],'orders':False,'cloud_deployment':False,'new_broker_calls':0,'new_science':False}
(out/'WHOLE_PACKAGE_INSPECTION_V1.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS',report['algo_sha256'],'members',len(inventory),'method_bodies',len(methods),'member_refs',len(refs),'strings',len(set(strings)))
