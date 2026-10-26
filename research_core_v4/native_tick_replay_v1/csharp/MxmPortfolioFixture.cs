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
// Native OWNER absolute caps: the replay law above remains unchanged.
Require(MxmOwnerEntryEnvelope.Check(200m,80m,0m,1.8m,0.2m)==MxmOwnerEntryEnvelope.Admit,"OWNER_ALL_THREE_LIMITS_EQUALITY");
Require(MxmOwnerEntryEnvelope.Check(200m,80.01m,0m,1m,0.2m)=="REJECT_OWNER_TICKET_MARGIN_GT_80","OWNER_ABSOLUTE_MARGIN_NOT_CONFIG_FRACTION");
Require(MxmOwnerEntryEnvelope.Check(200m,80m,0.01m,1m,0.2m)=="REJECT_OWNER_POST_ENTRY_RESERVE_LT_120","OWNER_RESERVE_POST_COMMISSION");
Require(MxmOwnerEntryEnvelope.Check(200m,80m,0m,1.81m,0.2m)=="REJECT_OWNER_NEW_ENTRY_RISK_GT_2","OWNER_RISK_INCLUDES_FRICTION");
Require(MxmOwnerEntryEnvelope.Check(250m,80m,0m,2m,0.01m)=="REJECT_OWNER_NEW_ENTRY_RISK_GT_2","OWNER_RISK_CAP_NOT_EQUITY_RELATIVE");
Require(MxmOwnerEntryEnvelope.Check(250m,80m,0m,2m,0m)==MxmOwnerEntryEnvelope.Admit,"OWNER_COMPOUNDING_EQUITY_NO_NEW_RESET");
Require(MxmOwnerEntryEnvelope.Check(200m,0m,0m,1m,0.2m)=="REJECT_UNVERIFIED_OWNER_INPUT","OWNER_ZERO_MARGIN");
Require(MxmOwnerEntryEnvelope.Check(200m,80m,-0.01m,1m,0.2m)=="REJECT_UNVERIFIED_OWNER_INPUT","OWNER_NEGATIVE_FEE");
Require(MxmOwnerEntryEnvelope.Check(200m,80m,0m,decimal.MaxValue,1m)=="REJECT_UNVERIFIED_OWNER_INPUT","OWNER_OVERFLOW");
// Current native broker-account observations are sampled, never atomic.
var baseBook=new MxmNativeEntrySnapshot(200m,200m,60m,1m);
Require(MxmNativeFinalAccountFence.Check(baseBook,baseBook)==MxmNativeFinalAccountFence.Admit,"FINAL_SNAPSHOT_EQUAL");
Require(MxmNativeFinalAccountFence.Check(baseBook,baseBook with {EquityEur=205m,FreeMarginEur=203m})==MxmNativeFinalAccountFence.Admit,"FINAL_ACCOUNT_IMPROVED_NO_RECAPITALIZATION");
Require(MxmNativeFinalAccountFence.Check(baseBook,baseBook with {EquityEur=199.99m,FreeMarginEur=199.99m})=="REJECT_ACCOUNT_EQUITY_DECLINED_BEFORE_ORDER","FINAL_EQUITY_DRIFT");
Require(MxmNativeFinalAccountFence.Check(baseBook,baseBook with {FreeMarginEur=199.99m})=="REJECT_ACCOUNT_FREE_MARGIN_DECLINED_BEFORE_ORDER","FINAL_FREE_MARGIN_DRIFT_WITH_AMPLE_RESERVE");
Require(MxmNativeFinalAccountFence.Check(baseBook,baseBook with {TicketMarginEur=60.01m})=="REJECT_TICKET_MARGIN_INCREASED_BEFORE_ORDER","FINAL_TICKET_MARGIN_DRIFT");
Require(MxmNativeFinalAccountFence.Check(baseBook,baseBook with {ProposedStopRiskEur=1.01m})=="REJECT_PROPOSED_STOP_RISK_INCREASED_BEFORE_ORDER","FINAL_STOP_RISK_DRIFT");
Require(MxmNativeFinalAccountFence.Check(baseBook,baseBook with {FreeMarginEur=201m})=="REJECT_INVALID_OR_UNVERIFIED_FINAL_ACCOUNT_SNAPSHOT","FINAL_BAD_ACCOUNT_RELATION");
Require(MxmNativeFinalAccountFence.Check(baseBook,baseBook with {EquityEur=0m})=="REJECT_INVALID_OR_UNVERIFIED_FINAL_ACCOUNT_SNAPSHOT","FINAL_BAD_EQUITY");
Require(MxmNativeFinalAccountFence.Check(baseBook,null!)=="REJECT_INVALID_OR_UNVERIFIED_FINAL_ACCOUNT_SNAPSHOT","FINAL_MISSING");
Require(MxmNativeFinalAccountFence.Check(baseBook,baseBook with {TicketMarginEur=0m})=="REJECT_INVALID_OR_UNVERIFIED_FINAL_ACCOUNT_SNAPSHOT","FINAL_NO_MARGIN");
Require(MxmAccountIsolation.Check(0,0,0)==MxmAccountIsolation.Admit,"FLAT_ACCOUNT");
Require(MxmAccountIsolation.Check(2,2,0)==MxmAccountIsolation.Admit,"ALL_OWNED_POSITIONS");
Require(MxmAccountIsolation.Check(2,1,0)=="REJECT_FOREIGN_ACCOUNT_POSITION","FOREIGN_POSITION");
Require(MxmAccountIsolation.Check(1,0,0)=="REJECT_FOREIGN_ACCOUNT_POSITION","UNMANAGED_POSITION");
Require(MxmAccountIsolation.Check(0,0,1)=="REJECT_ACCOUNT_PENDING_ORDER","PENDING_BROKER_ORDER");
Require(MxmAccountIsolation.Check(1,2,0)=="REJECT_INCONSISTENT_ACCOUNT_BOOK","PHANTOM_OWNED_COUNT");
Require(MxmAccountIsolation.Check(-1,0,0)=="REJECT_INCONSISTENT_ACCOUNT_BOOK","INVALID_BOOK");

// Actual shared product/replay gate: artificial callback arrival ordering,
// no broker calls. Equal-time ticks may arrive before OR after BarClosed.
var intentA=new MxmCausalIntent();
var intentB=new MxmCausalIntent();
Require(!intentA.TryConsume(utc,out _),"NO_COLD_START_INTENT");
intentA.Publish(1,true,6,utc,utc.AddMilliseconds(113),5);
intentB.Publish(-1,true,6,utc,utc.AddMilliseconds(113),5);
Require(!intentA.TryConsume(utc,out _),"NO_EARLIER_QUOTE");
Require(!intentA.TryConsume(utc.AddMilliseconds(113),out _),"NO_SAME_CALLBACK_FILL");
Require(intentB.TryConsume(utc.AddMilliseconds(114),out var sell) && sell!.Desired==-1,
 "SYMBOL_B_INDEPENDENT_LATER_QUOTE");
Require(intentA.TryConsume(utc.AddMilliseconds(115),out var buy) && buy!.Desired==1,
 "SYMBOL_A_INDEPENDENT_LATER_QUOTE");
Require(!intentA.TryConsume(utc.AddSeconds(1),out _),"REJECTED_OR_UNKNOWN_ACK_CANNOT_RETRY_INTENT");
Require(!intentB.TryConsume(utc.AddSeconds(1),out _),"ONE_CONSUMPTION_PER_SYMBOL");
intentA.Publish(1,true,7,utc.AddMinutes(5),utc.AddMinutes(5),5);
Require(!intentA.TryConsume(utc.AddMinutes(10),out _),"EXPIRE_BEFORE_NEXT_BAR_CALLBACK");
Require(!intentA.TryConsume(utc.AddMinutes(10).AddSeconds(1),out _),"EXPIRED_STAYS_CLEARED");
intentA.Publish(1,true,8,utc.AddMinutes(10),utc.AddMinutes(10),5);
intentA.Clear();
Require(!intentA.TryConsume(utc.AddMinutes(10).AddSeconds(1),out _),"STOP_OR_GAP_CLEARS_INTENT");
intentA.Publish(1,true,9,utc.AddMinutes(15),utc.AddMinutes(15),5);
intentA.Publish(0,true,10,utc.AddMinutes(20),utc.AddMinutes(20),5);
Require(intentA.TryConsume(utc.AddMinutes(20).AddSeconds(1),out var neutral) && neutral!.Desired==0,
 "NEW_NEUTRAL_REPLACES_OLD_DIRECTION");
bool invalidIntent=false;
try{intentA.Publish(1,true,11,utc.AddMinutes(25),utc.AddMinutes(30),5);}
catch(ArgumentException){invalidIntent=true;}
Require(invalidIntent,"NO_DELAYED_SESSION_REOPEN_INTENT");
invalidIntent=false;
try{intentA.Publish(1,true,11,utc.AddMinutes(25),utc.AddMinutes(24),5);}
catch(ArgumentException){invalidIntent=true;}
Require(invalidIntent,"NO_FUTURE_BOUNDARY_INTENT");
invalidIntent=false;
try{intentA.TryConsume(DateTime.SpecifyKind(utc,DateTimeKind.Unspecified),out _);}
catch(ArgumentException){invalidIntent=true;}
Require(invalidIntent,"NO_UNKNOWN_QUOTE_TIMEZONE");
Console.WriteLine("MXM_SHARED_PRODUCT_REPLAY_LATER_QUOTE_ONCE_ONLY_INTENT_AND_EXPIRY_SYNTHETIC_PASS");
Console.WriteLine("MXM_ONE_ROBOT_MULTISYMBOL_SERIAL_BARS_AND_SHARED_EUR200_ADMISSION_SYNTHETIC_PASS_NO_ATOMIC_CLOUD_CLAIM");
