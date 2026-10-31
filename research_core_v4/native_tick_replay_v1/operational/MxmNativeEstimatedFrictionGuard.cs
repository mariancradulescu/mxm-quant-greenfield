using System;

namespace Mxm.Replay {
/// <summary>
/// Native estimate guard: charge both modeled commission sides, the currently
/// observed spread translated by cTrader AmountRisked at the proposed volume,
/// and an explicitly declared positive slippage cushion. This is a
/// conservative ACCOUNT EUR scenario floor, not a future fill/fee guarantee.
/// No unknown, negative or overflowing input is ever silently set to zero.
/// </summary>
public static class MxmNativeEstimatedFrictionGuard {
 public static decimal? FloorEur(decimal configuredReserveEur,
  decimal buyCommissionEstimateEur,decimal sellCommissionEstimateEur,
  decimal currentSpreadRiskEstimateEur,decimal extraSlippageAllowanceEur) {
  if(configuredReserveEur<0m || buyCommissionEstimateEur<0m ||
     sellCommissionEstimateEur<0m || currentSpreadRiskEstimateEur<0m ||
     extraSlippageAllowanceEur<0m)return null;
  try {checked {
   decimal twoSidedFees=2m*Math.Max(buyCommissionEstimateEur,sellCommissionEstimateEur);
   decimal observedCostFloor=twoSidedFees+currentSpreadRiskEstimateEur+extraSlippageAllowanceEur;
   return Math.Max(configuredReserveEur,observedCostFloor);
  }}catch(OverflowException){return null;}
 }
}
}
