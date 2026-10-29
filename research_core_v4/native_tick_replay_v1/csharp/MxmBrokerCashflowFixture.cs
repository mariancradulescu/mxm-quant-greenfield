using System;
using System.Linq;
using Mxm.Replay;

internal static class Program {
 static void Need(bool ok,string message) {if(!ok)throw new Exception(message);}
 static void Reject(Action action,string message) {
  bool rejected=false;
  try {action();} catch(ArgumentException) {rejected=true;}
  Need(rejected,message);
 }
 static void Main() {
  var now=new DateTime(2026,10,29,12,0,0,DateTimeKind.Utc);
  var t0=now.AddDays(-6);
  var deposit=new MxmBrokerCashflowFact(12,t0,"Deposit",200m,200m);
  var topUp=new MxmBrokerCashflowFact(20,t0.AddDays(1),"Deposit",50m,250m);
  var withdrawal=new MxmBrokerCashflowFact(28,t0.AddDays(2),"Withdrawal",-15m,235m);
  var a=new MxmBrokerCashflowInventory("pepperstone:europe:account-one","EUR",now,
   new[]{withdrawal,deposit,topUp,deposit});
  var b=new MxmBrokerCashflowInventory("pepperstone:europe:account-one","EUR",now,
   new[]{topUp,deposit,withdrawal});
  Need(a.Facts.Length==3,"Duplicate deposit must not count again");
  Need(a.ObservedDepositsEur==250m && a.ObservedWithdrawalsEur==15m &&
   a.ObservedNetExternalFlowEur==235m,"Cashflows must be signed by type, not raw API amount");
  Need(a.FactsSha256==b.FactsSha256,"Original fact digest must ignore source order/duplicates");
  Need(a.Facts.Select(x=>x.Id).SequenceEqual(new long[]{12,20,28}),"Chronological original facts");
  Need(!a.FullHistoryCoverageProven && !a.OriginalCapitalAnchorProven &&
   !a.CashflowNeutralStrategyNavProven && !a.CanAuthorizeOrders,
   "Observed transaction subset is never capital certification or permission");
  var other=new MxmBrokerCashflowInventory("pepperstone:europe:account-two","EUR",now,
   new[]{deposit,topUp,withdrawal});
  Need(a.FactsSha256!=other.FactsSha256,"Scope contamination");
  Reject(()=>new MxmBrokerCashflowInventory("a","USD",now,new[]{deposit}),"Not a EUR account");
  Reject(()=>new MxmBrokerCashflowInventory("a","EUR",now,
   new[]{deposit,deposit with {RawAmountEur=201m}}),"Conflicting original ID");
  Reject(()=>new MxmBrokerCashflowInventory("a","EUR",now,
   new[]{deposit with {TimeUtc=now.AddMinutes(1)}}),"Future-dated native fact");
  Reject(()=>new MxmBrokerCashflowInventory("a","EUR",now,
   new[]{deposit with {TimeUtc=DateTime.SpecifyKind(t0,DateTimeKind.Unspecified)}}),"Unqualified clock");
  Reject(()=>new MxmBrokerCashflowInventory("a","EUR",now,
   new[]{deposit with {RawAmountEur=0m}}),"Zero-amount entry");
  Console.WriteLine("MXM_BROKER_CASHFLOW_CORE_PASS: 11 scoped and causal checks; no broker connection or orders");
 }
}
