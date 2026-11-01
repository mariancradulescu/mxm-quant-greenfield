using System;
using Mxm.Replay;
static class Programme {
 static void Need(bool ok,string why){if(!ok)throw new Exception("MXM_NATIVE_EQUITY_"+why);}
 static MxmEquityBudget Budget(decimal eq){
  Need(MxmEquityConservation.TryBudget(eq,.4m,.01m,out var budget),"BUDGET");
  return budget;
 }
 static void Main(){
  var original=Budget(200m);
  Need(original.MarginFraction==.4m && original.TotalStopFraction==.01m,"EUR200_PARITY");
  var half=Budget(100m);
  Need(half.MarginFraction==.2m && half.TotalStopFraction==.0025m,"EUR100_CONTRACTION");
  Need(Budget(300m)==original,"NO_LOSS_RECOUP_LEVER_UP");
  Need(Budget(150m).TotalStopFraction>Budget(100m).TotalStopFraction,
       "MONOTONIC_CAPITAL_BUDGET");
  Need(!MxmEquityConservation.TryBudget(0m,.4m,.01m,out _) &&
       !MxmEquityConservation.TryBudget(-1m,.4m,.01m,out _) &&
       !MxmEquityConservation.TryBudget(200m,1.1m,.01m,out _),
       "FAIL_CLOSED_INPUT");
  Need(!MxmEquityConservation.Recheck(100m,110m,.4m,.01m,out _),
       "PRE_SUBMISSION_NO_EXPANSION_AFTER_EQUITY_RISE");
  Need(MxmEquityConservation.Recheck(180m,160m,.4m,.01m,out var final) &&
       final==Budget(160m),"PRE_SUBMISSION_CONTRACTION");
  for(decimal e=5m;e<=500m;e+=5m){
   var limit=Budget(e);
   Need(limit.MarginFraction<=original.MarginFraction &&
        limit.TotalStopFraction<=original.TotalStopFraction,"NO_NEW_EXPOSURE_RELAX");
  }
  // A ticket admissible at EUR200 by the inherited capital/risk gates is
  // rejected at lower equity under the SAME broker marginal geometry.
  var oldCapital=MxmCapitalAdmission.Check(200m,200m,70m,.01m,
     original.MarginFraction,120m,0,1);
  Need(oldCapital==MxmCapitalAdmission.Admit,"HISTORIC_BASELINE_CAPITAL");
  var shrink=Budget(180m);
  Need(MxmCapitalAdmission.Check(180m,180m,70m,.01m,
     shrink.MarginFraction,120m,0,1)!=MxmCapitalAdmission.Admit,
     "LOWER_EQUITY_CANNOT_REUSE_ORIGINAL_VOLUME");
  Need(MxmStopRiskAdmission.Check(200m,0m,1.1m,
     original.TotalStopFraction,.1m,0m)==MxmStopRiskAdmission.Admit,
     "HISTORIC_STOP_ACCEPTS");
  Need(MxmStopRiskAdmission.Check(180m,0m,1.1m,
     shrink.TotalStopFraction,.1m,0m)!=MxmStopRiskAdmission.Admit,
     "LOWER_EQUITY_SHRINKS_TOTAL_STOP_EXPOSURE");
  Console.WriteLine("MXM_EQUITY_CONSERVATION_NATIVE_SINGLE_ACCOUNT_SUCCESS");
 }
}
