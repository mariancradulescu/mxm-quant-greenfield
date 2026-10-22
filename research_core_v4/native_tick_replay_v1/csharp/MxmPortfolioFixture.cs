using System;
using Mxm.Replay;

// Artificial deterministic multi-symbol single-account runtime checks. No fills,
// no Pepperstone data, no account equity performance or HARD21 inference.
static void Require(bool yes,string reason) {
 if(!yes)throw new Exception("MXM_PORTFOLIO_FIXTURE_FAIL_"+reason);
}
var p=new MxmPortfolioSequencer(new[]{"EURUSD","GBPUSD"});
var utc=new DateTime(2026,10,20,10,0,0,DateTimeKind.Utc);
Require(p.SymbolCount==2,"COUNT");
Require(p.TryEnter("EURUSD",utc,out _),"FIRST");
Require(!p.TryEnter("GBPUSD",utc,out var r) && r=="REENTRANT_OR_CONCURRENT_DECISION","SERIAL");
p.Exit();
Require(p.TryEnter("GBPUSD",utc,out _),"SECOND");
p.Exit();
Require(!p.TryEnter("EURUSD",utc,out r) && r=="DUPLICATE_OR_OUT_OF_ORDER_BAR","DUPLICATE");
Require(!p.TryEnter("EURUSD",utc.AddMinutes(-5),out _),"STALE");
Require(!p.TryEnter("USDJPY",utc,out r) && r=="SYMBOL_NOT_REGISTERED","ROSTER");
Require(p.TryEnter("EURUSD",utc.AddMinutes(5),out _),"NEW_BAR");
p.Exit();
bool bad=false;
try{p.Exit();}catch(InvalidOperationException){bad=true;}
Require(bad,"UNBALANCED");

var a=new MxmDecisionKernel(StrategyMode.Adaptive);
var b=new MxmDecisionKernel(StrategyMode.Adaptive);
for(int i=0;i<5;i++){
 Require(a.OnCompletedBar(1.10m+i*0.0001m)==0,"A_WARMUP");
 Require(b.OnCompletedBar(1.20m-i*0.0001m)==0,"B_WARMUP");
}
Require(a.CompletedBars==5 && b.CompletedBars==5,"INDEPENDENT_COLD_STATE");
a.OnCompletedBar(1.101m);
Require(a.CompletedBars==6 && b.CompletedBars==5,"INDEPENDENT_KERNELS");
Require(MxmCapitalAdmission.Check(200m,200m,90m,0m,.8m,0m,0,2)
 ==MxmCapitalAdmission.Admit,"FIRST_MARGIN");
Require(MxmCapitalAdmission.Check(200m,110m,90m,0m,.8m,0m,1,2)
 =="REJECT_MARGIN_FRACTION","ONE_ACCOUNT_SECOND_MARGIN");
Require(MxmStopRiskAdmission.Check(200m,2m,3m,.02m,.2m,.2m)
 =="REJECT_AGGREGATE_STOP_RISK_EXCESS","AGGREGATE_RISK");
Require(MxmCapitalAdmission.Check(200m,110m,40m,0m,.8m,0m,1,1)
 =="REJECT_ACCOUNT_POSITION_CAP","ACCOUNT_POSITION_CAP");
Console.WriteLine("MXM_ONE_ROBOT_MULTISYMBOL_SERIAL_BARS_AND_SHARED_EUR200_ADMISSION_SYNTHETIC_PASS_NO_ATOMIC_CLOUD_CLAIM");
