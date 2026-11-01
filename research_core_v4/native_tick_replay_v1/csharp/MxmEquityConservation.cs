using System;
namespace Mxm.Replay {
/// <summary>
/// Conservative, restart-invariant equity-sensitive sizing for the ONE EUR200
/// account. This is a DIRECTOR engineering safety overlay, NOT an OWNER-defined
/// immutable EUR80/EUR120 numeric ceiling, alpha strategy, fill proof or money-
/// management optimality claim. Below original EUR200 only, it shrinks both
/// margin fraction and total stop-risk fraction; it never raises baseline
/// exposure, overrides broker minima or relaxes an existing downstream gate.
///
/// Stateless by construction: a Cloud cold start cannot erase a drawdown peak
/// to re-expand the risk budget. The permanent EUR200 initial-capital anchor
/// is OWNER-authorized; stop/reserve/margin baseline remains unchanged.
/// </summary>
public readonly record struct MxmEquityBudget(decimal MarginFraction,decimal TotalStopFraction);
public static class MxmEquityConservation {
 public const decimal InitialCapitalEur=200m;
 public static bool TryBudget(decimal equity,decimal baselineMarginFraction,
  decimal baselineTotalStopFraction,out MxmEquityBudget budget){
  budget=default;
  if(equity<=0m || baselineMarginFraction<=0m ||
     baselineMarginFraction>1m || baselineTotalStopFraction<=0m ||
     baselineTotalStopFraction>1m)return false;
  try {checked {
   decimal capitalRetention=Math.Min(1m,equity/InitialCapitalEur);
   // No loss-driven leverage: dollar risk contracts faster than equity loss.
   // At EUR200: old account limits are exact. At EUR100: margin fraction
   // halves and total stop fraction quarters. Above EUR200: never lever up.
   decimal margin=baselineMarginFraction*capitalRetention;
   decimal stop=baselineTotalStopFraction*capitalRetention*capitalRetention;
   if(margin<=0m || stop<=0m || margin>baselineMarginFraction ||
      stop>baselineTotalStopFraction)return false;
   budget=new MxmEquityBudget(margin,stop);return true;
  }}catch(OverflowException){return false;}
 }
 public static bool Recheck(decimal originalEquity,decimal finalEquity,
  decimal baselineMarginFraction,decimal baselineTotalStopFraction,
  out MxmEquityBudget budget) {
  budget=default;
  if(!TryBudget(originalEquity,baselineMarginFraction,
      baselineTotalStopFraction,out var original) ||
     !TryBudget(finalEquity,baselineMarginFraction,
      baselineTotalStopFraction,out var final))return false;
  // Do not allow capital-dependent budgets to expand between preparatory
  // account sampling and the irreversible broker order request.
  if(final.MarginFraction>original.MarginFraction ||
     final.TotalStopFraction>original.TotalStopFraction)return false;
  budget=final;return true;
 }
}
