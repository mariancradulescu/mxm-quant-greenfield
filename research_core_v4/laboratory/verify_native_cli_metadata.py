"""Offline exact native artifact/output preservation. Does not execute the CLI or cBot."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path('docs/economic-development/20261024/native-cli-metadata-40108355359')
ZIP='6606c0054a79e24651abeb99ec9f1cbda0bd56570c5e781ab03ae1bbcf5b44e4'
ALGO='ec54c98c6a38e1bcd7683e3f20042d7aca20e6abe7de7575e71275bfb8c0a254'
DLL='c8143df65db11efd7cdbdf5b49094f99135f351e38b0c81f8d9aee4cfdcb0d08'
META='095789065d0b5c3cbac2683daefaaa31709efa28ff92539b0f6d9e7ef60eb090'
TYPES={'PortfolioSymbols':'String','EnableDemoTrading':'Boolean','StopLossPips':'Integer','RegimeFamily':'String',
 'ExitPolicy':'String','BarMinutes':'Integer','MaxMarginFraction':'Double','MaxMxmAccountPositions':'Integer',
 'MinimumFreeMarginReserveEur':'Double','MaxEstimatedMxmStopRiskPercent':'Double',
 'EstimatedRoundTripFrictionReserveEur':'Double','RequestedUnits':'Double'}
DEFAULTS={'EnableDemoTrading':False,'StopLossPips':12,'RegimeFamily':'Adaptive','ExitPolicy':'ReverseOnly',
 'BarMinutes':5,'MaxMarginFraction':.4,'MaxMxmAccountPositions':1,'MaxEstimatedMxmStopRiskPercent':2.,
 'EstimatedRoundTripFrictionReserveEur':.2,'RequestedUnits':1000.}
def need(ok,why):
    if not ok:raise ValueError('MXM_NATIVE_CLI_EVIDENCE_'+why)
def sha(b):return hashlib.sha256(b).hexdigest()
def verify(root=ROOT):
    root=Path(root);m=json.loads((root/'MANIFEST.json').read_bytes());need(len(m['parts'])==3,'PART_COUNT')
    pieces=[]
    for i,p in enumerate(m['parts']):
        need(p['index']==i and p['path']==f'part-{i:02d}.b64','PART_ORDER')
        path=root/p['path'];need(not path.is_symlink() and path.stat().st_size<45000,'PART_BOUNDS')
        b=base64.b64decode(path.read_text().strip(),validate=True)
        need(len(b)==p['bytes'] and len(b)<=32768 and sha(b)==p['sha256'],'PART_DIGEST');pieces.append(b)
    raw=b''.join(pieces);need(len(raw)==65555==m['archive_bytes'] and sha(raw)==ZIP==m['archive_sha256'],'ORIGINAL_ZIP')
    prefix='verification/ctrader-cli-metadata/'
    source='research_core_v4/native_tick_replay_v1/csharp/bin/Release/net6.0/'
    names={prefix+x for x in ('receipt.json','metadata.stdout.txt','metadata.stderr.txt','version.stdout.txt',
        'version.stderr.txt','malformed.stdout.txt','malformed.stderr.txt')}|{source+'native_tick_replay_v1.algo',source+'MxmReferenceBot.dll'}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(len(z.infolist())==9 and set(z.namelist())==names and sum(x.file_size for x in z.infolist())<200000,'BOUNDED_ORIGINAL_MEMBERS')
        members={name:z.read(name) for name in names}
    need(set(m['members'])==names,'MEMBER_MANIFEST')
    for name,data in members.items():need(len(data)==m['members'][name]['bytes'] and sha(data)==m['members'][name]['sha256'],'MEMBER_DIGEST')
    receipt=members[prefix+'receipt.json'];metadata=members[prefix+'metadata.stdout.txt'];v=json.loads(receipt);meta=json.loads(metadata)
    need((root/'receipt.json').read_bytes()==receipt and (root/'metadata.stdout.txt').read_bytes()==metadata,'EXACT_ORIGINAL_COPIES')
    need(sha(members[source+'native_tick_replay_v1.algo'])==ALGO==v['artifact_sha256'] and v['artifact_bytes']==31897 and
         sha(members[source+'MxmReferenceBot.dll'])==DLL==v['product_assembly_sha256'] and sha(metadata)==META==v['metadata_stdout_sha256'],
         'ACTUAL_PRODUCT_AND_NATIVE_OUTPUT')
    need(b'.NETCoreApp,Version=v6.0' in members[source+'MxmReferenceBot.dll'] and v['product_target_framework']==m['product_target_framework']=='net6.0' and
         not m['net8_packaging_accepted'],'NO_NET8_MIGRATION_CLAIM')
    need(v['source_sha']==m['pr_test_merge_sha']=='ee483763c99025dc0df6eae041eeedff46219723' and m['run_id']==40108355359 and
         m['job_id']==120914663196 and m['artifact_id']==12565388290 and m['source_pr']==171 and m['required_checks']==3 and
         m['pr_source_head']=='f841e12be9b4f064e0395b70f6a997d70c7759c1' and
         m['integration_sha']=='ae50372b50f2894ba3f20f10c279d94bc7ec1c5e' and m['source_tree']=='689be32ae9e3cb743df2cdbc4dcc3237a451584b','PROVENANCE')
    need(v['native_metadata_returncode']==0 and v['native_malformed_returncode']==1 and 'Version: 5.9.0.28' in v['native_cli_version'] and
         v['vendor_tar_sha256']=='da0f5fb0c58980be9143fafca9839de784084b6e323321d9e03e5c3e64bec562' and
         v['vendor_formula_commit']=='42a7eacb26a4c28b84df39ca7e5689e4b909fa2c' and
         v['vendor_reference_commit']=='12c6042077b6e6dd6bc0deda8fabd1be724d3059','PINNED_VENDOR_NATIVE_RESULTS')
    need(meta['Name']=='native_tick_replay_v1' and meta['Type']=='cBot' and meta['AccessRights']=='None' and
         len(meta['Parameters'])==12 and set(v['parameters_verified'])==set(TYPES),'NATIVE_METADATA_IDENTITY')
    params={p['PropertyName']:p for p in meta['Parameters']};need(set(params)==set(TYPES),'TWELVE_UNIQUE_PARAMETERS')
    for key,kind in TYPES.items():need(params[key]['Type']==kind,'NATIVE_PARAMETER_TYPES')
    for key,value in DEFAULTS.items():
        actual=params[key]['DefaultValue'];need(type(actual) is type(value) or isinstance(actual,(int,float)) and not isinstance(actual,bool) and not isinstance(value,bool),'DEFAULT_VALUE_TYPE')
        need(actual==value,'EXPORTED_NATIVE_DEFAULTS')
    need([p['PropertyName'] for p in meta['Parameters'] if 'DefaultValue' not in p]==['PortfolioSymbols','MinimumFreeMarginReserveEur'],'NO_INVENTED_MISSING_DEFAULTS')
    need([x['kind'] for x in v['isolation']]==['version','metadata','malformed'],'COMMAND_SCOPE')
    for x in v['isolation']:
        need(x['network_namespace']!=x['host_namespace'] and x['uid']==1001 and x['effective_capabilities']==0 and
             x['no_new_privileges'] and x['external_ipv4_routes']==0 and x['environment_keys']==['HOME','LANG','PATH'],'OBSERVED_ISOLATION')
    need(v['native_vendor_metadata_read'] and m['package_metadata_accepted'] and not v['run_command_invoked'] and not v['backtest_command_invoked'] and
         not v['broker_credentials_supplied'] and not v['broker_network_available'] and v['broker_orders']==m['broker_orders']==0 and
         not v['cloud_activated'] and not m['cloud_activated'] and not v['native_trading_callbacks_proven'] and not v['native_storage_recovery_proven'] and
         not m['native_operational_accepted'] and not m['native_storage_recovery_proven'] and not v['economic_edge_proven'] and
         not m['economic_edge_proven'] and not v['hard21_proven'] and not m['hard21_proven'] and v['new_research_trials']==m['new_market_reads']==0,'NO_PROMOTION_OR_ACCOUNT_USE')
    return dict(archive_sha256=ZIP,algo_sha256=ALGO,native_package_metadata_accepted=True,explicit_native_defaults_verified=10,
        native_operational_accepted=False,economic_edge_proven=False,orders=0,cli_executed_by_verifier=False)
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
