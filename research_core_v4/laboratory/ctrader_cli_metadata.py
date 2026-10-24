"""Native vendor CLI metadata only. No run/backtest, credentials or network access."""
import hashlib,json,os,re,resource,stat,subprocess,sys,tempfile
from pathlib import Path
EXPECTED=('PortfolioSymbols','EnableDemoTrading','StopLossPips','RegimeFamily','ExitPolicy','BarMinutes',
 'MaxMarginFraction','MaxMxmAccountPositions','MinimumFreeMarginReserveEur',
 'MaxEstimatedMxmStopRiskPercent','EstimatedRoundTripFrictionReserveEur','RequestedUnits')
TARBALL_SHA='da0f5fb0c58980be9143fafca9839de784084b6e323321d9e03e5c3e64bec562'
def need(ok,why):
    if not ok:raise ValueError('MXM_NATIVE_CLI_METADATA_'+why)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def worker(cli,artifact,kind,host_namespace,expected_uid):
    namespace=os.readlink('/proc/self/ns/net')
    status=Path('/proc/self/status').read_text()
    need(namespace!=host_namespace and os.getuid()==int(expected_uid)!=0,'NETWORK_NAMESPACE_AND_NONROOT')
    need(re.search(r'^NoNewPrivs:\s+1$',status,re.M) and re.search(r'^CapEff:\s+0+$',status,re.M) and re.search(r'^CapBnd:\s+0+$',status,re.M),'DROPPED_PRIVILEGES')
    routes=Path('/proc/net/route').read_text().splitlines()
    need(len(routes)==1,'NO_EXTERNAL_IPV4_ROUTES')
    need(set(os.environ)=={'HOME','PATH','LANG'},'CREDENTIAL_FREE_ENVIRONMENT')
    for fd in (0,1,2):need(not stat.S_ISSOCK(os.fstat(fd).st_mode),'NO_INHERITED_NETWORK_STDIO')
    need(kind in ('version','metadata','malformed'),'COMMAND_ALLOWLIST')
    command=[cli,'--version'] if kind=='version' else [cli,'metadata',artifact]
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    p=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,timeout=35)
    need(len(p.stdout)+len(p.stderr)<262144,'BOUNDED_NATIVE_OUTPUT')
    return {'kind':kind,'command':command,'returncode':p.returncode,'stdout':p.stdout.decode(errors='replace'),
      'stderr':p.stderr.decode(errors='replace'),'network_namespace':namespace,'uid':os.getuid(),
      'host_namespace':host_namespace,'external_ipv4_routes':0,'no_new_privileges':True,'effective_capabilities':0,
      'environment_keys':sorted(os.environ)}
def isolated(cli,artifact,kind,home):
    # Create a new network namespace while privileged, then irreversibly drop
    # to the original runner UID with no capabilities before touching vendor code.
    host=os.readlink('/proc/self/ns/net');uid=os.getuid();need(uid!=0,'NONROOT_PARENT_REQUIRED')
    command=['sudo','-n','/usr/bin/timeout','--kill-after=3s','45s','/usr/bin/unshare','--net','--',
      '/usr/bin/setpriv',f'--reuid={uid}',f'--regid={os.getgid()}','--clear-groups','--bounding-set=-all','--no-new-privs',
      '/usr/bin/env','-i','HOME='+str(home),'PATH=/usr/bin:/bin','LANG=C.UTF-8','/usr/bin/python3',
      str(Path(__file__).resolve()),'--worker',str(cli),str(artifact),kind,host,str(uid)]
    p=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,timeout=55)
    need(p.returncode==0,'ISOLATED_WORKER_'+kind+'_'+p.stderr.decode(errors='replace')[-1000:])
    result=json.loads(p.stdout);need(result['network_namespace']!=host,'OBSERVED_NAMESPACE_DIFFERENCE');return result

def metadata_contract(text):
    clean=re.sub(r'\x1b\[[0-9;]*m','',text)
    need(all(re.search(r'\b'+name+r'\b',clean) for name in EXPECTED),'ALL_TWELVE_PARAMETER_IDENTITIES')
    return list(EXPECTED)
def run(cli,artifact,dest):
    cli=Path(cli).resolve();artifact=Path(artifact).resolve();dest=Path(dest).resolve()
    need(cli.is_file() and artifact.is_file() and artifact.suffix=='.algo','EXACT_NATIVE_INPUTS')
    assembly=artifact.parent/'MxmReferenceBot.dll';raw=assembly.read_bytes()
    need(b'.NETCoreApp,Version=v6.0' in raw and b'MxmReferenceProductBot' in raw,'ACTUAL_CANONICAL_NET6_PRODUCT_ASSEMBLY')
    dest.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='mxm-cli-offline-') as tmp:
        home=Path(tmp);bad=home/'malformed.algo';bad.write_text('This is deliberately not an algo package.\n')
        version=isolated(cli,artifact,'version',home)
        need(version['returncode']==0 and '5.9.0' in version['stdout']+version['stderr'],'PINNED_NATIVE_VERSION')
        valid=isolated(cli,artifact,'metadata',home)
        malformed=isolated(cli,bad,'malformed',home)
        # Preserve originals even if a contract fails; failure is never a success receipt.
        for name,result in [('version',version),('metadata',valid),('malformed',malformed)]:
            (dest/(name+'.stdout.txt')).write_text(result['stdout']);(dest/(name+'.stderr.txt')).write_text(result['stderr'])
        need(valid['returncode']==0,'NATIVE_PRODUCT_METADATA_RETURN')
        parameters=metadata_contract(valid['stdout'])
        need(malformed['returncode']!=0,'NATIVE_MALFORMED_PACKAGE_REJECTED')
        summary={'schema':'mxm.ctrader-cli.offline-metadata.v1','source_sha':os.environ.get('GITHUB_SHA'),
          'native_cli_version':(version['stdout']+version['stderr']).strip(),'vendor_tar_sha256':TARBALL_SHA,
          'vendor_formula_commit':'42a7eacb26a4c28b84df39ca7e5689e4b909fa2c',
          'vendor_reference_commit':'12c6042077b6e6dd6bc0deda8fabd1be724d3059',
          'artifact_name':artifact.name,'artifact_bytes':artifact.stat().st_size,'artifact_sha256':digest(artifact.read_bytes()),
          'product_assembly_sha256':digest(raw),'product_target_framework':'net6.0',
          'metadata_stdout_sha256':digest((dest/'metadata.stdout.txt').read_bytes()),
          'native_metadata_returncode':valid['returncode'],'native_malformed_returncode':malformed['returncode'],
          'parameters_verified':parameters,'isolation':[{k:v for k,v in z.items() if k not in ('stdout','stderr','command')}
            for z in (version,valid,malformed)],'native_vendor_metadata_read':True,
          'run_command_invoked':False,'backtest_command_invoked':False,'broker_credentials_supplied':False,
          'broker_network_available':False,'broker_orders':0,'cloud_activated':False,
          'native_trading_callbacks_proven':False,'native_storage_recovery_proven':False,
          'economic_edge_proven':False,'hard21_proven':False,'new_research_trials':0}
        (dest/'receipt.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
        print('MXM_NATIVE_CTRADER_CLI_OFFLINE_METADATA '+json.dumps(summary,sort_keys=True),flush=True)
    return summary
if __name__=='__main__':
    if sys.argv[1:2]==['--worker']:
        need(len(sys.argv)==7,'WORKER_ARGUMENTS');print(json.dumps(worker(*sys.argv[2:])));sys.exit(0)
    need(len(sys.argv)==4,'ARGUMENTS');run(*sys.argv[1:])
