"""Package existing compiled Robot for review. Never import, sync, start or trade."""
import base64,hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 source=ROOT/'research_core_v4/native_tick_replay_v1/csharp/bin/Release/net6.0/native_tick_replay_v1.algo'
 if not source.is_file() or source.is_symlink():raise ValueError('NATIVE_PACKAGE_MISSING')
 raw=source.read_bytes();out=ROOT/'verification/native-observation-delivery';out.mkdir(parents=True,exist_ok=False)
 (out/'MxmNativeObservation.algo').write_bytes(raw)
 request={'schema':'mxm.native-observation-reception-request.v1','package':'MxmNativeObservation.algo','package_sha256':hashlib.sha256(raw).hexdigest(),'algorithm_type':'cAlgo.Robots.MxmReferenceProductBot','parameter_display_names':{'NativeObservationOnly':'Native Observation Only','EnableDemoTrading':'Enable DEMO Trading'},'target':'EXISTING_OWNER_PEPPERSTONE_EUR_ACCOUNT_UNCHANGED','chart_symbol':'EURUSD','chart_timeframe':'m5','parameters':{'NativeObservationOnly':True,'EnableDemoTrading':False},'instance_limit':1,'operation':'IMPORT_EXACT_PACKAGE_IF_NEEDED_THEN_ONE_CONTROLLED_CLOUD_START_AND_STOP','observation_minutes':10,'activation_authorized':False,'orders_authorized':False,'new_accounts_or_funding':False,'access_scope_extension':False,'required_runtime_resource':'LEGITIMATE_AUTHENTICATED_CTRADER_CTID_SESSION_FOR_EXISTING_ACCOUNT','acceptance':['ACTUAL_ENVIRONMENT_CLOUD_AND_REALTIME','READY_WITH_CORRECT_RUN_AND_ACCOUNT_SCOPE','ACTUAL_FIRST_TICK_AND_CLOSED_BAR_CALLBACKS','BROKER_FACTS_AVAILABLE_OR_EXPLICIT_UNAVAILABLE','EXPLICIT_STOP_FOR_SAME_RUN','ZERO_ORDER_AND_CONTROL_STORAGE_OPERATIONS'],'does_not_certify':['TRADING_RESTART_RECOVERY','LOST_ORIGINAL_INTENT','CONTINUOUS_EUR200_QUALIFICATION','HARD21','NET_EDGE']}
 (out/'reception-request.json').write_text(json.dumps(request,indent=2)+'\n')
 receipt={'schema':'mxm.compiled-observation-delivery.v1','workflow_run':os.environ.get('GITHUB_RUN_ID'),'checked_out_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'checked_out_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),'package_bytes':len(raw),'package_sha256':hashlib.sha256(raw).hexdigest(),'request_sha256':hashlib.sha256((out/'reception-request.json').read_bytes()).hexdigest(),'native_callbacks_received':False,'cloud_activated':False,'orders':0,'package_recompiled_by_this_step':False}
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('MXM_NATIVE_OBSERVATION_DELIVERY '+json.dumps(receipt,sort_keys=True),flush=True)
 if len(raw)>1500000:raise ValueError('NATIVE_PACKAGE_BOUND')
 for i in range(0,len(raw),16384):print('MXM_NATIVE_PACKAGE_PART '+str(i//16384)+' '+base64.b64encode(raw[i:i+16384]).decode(),flush=True)
if __name__=='__main__':main()
