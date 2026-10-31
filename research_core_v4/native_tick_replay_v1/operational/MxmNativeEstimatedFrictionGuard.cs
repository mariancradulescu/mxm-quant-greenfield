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
 /// <summary>
 /// EXTRA necessary margin check: reserve the conservative full modeled cash
 /// entry cost *in addition to* the broker's estimated margin. The old broker
 /// fee-only account check remains; this can only reject more new positions.
 /// Not a guarantee of future marks, live slippage or liquidation margin.
 /// </summary>
 public static bool PostEntryReserveCovers(decimal freeMarginEur,
  decimal ticketMarginEur,decimal modeledFullRoundTripCostEur,
  decimal minimumFreeMarginReserveEur) {
  if(freeMarginEur<=0m || ticketMarginEur<=0m ||
     modeledFullRoundTripCostEur<0m || minimumFreeMarginReserveEur<0m)
   return false;
  try {checked {
   decimal afterMargin=freeMarginEur-ticketMarginEur;
   if(afterMargin>=freeMarginEur)return false;
   decimal afterCost=afterMargin-modeledFullRoundTripCostEur;
   if(modeledFullRoundTripCostEur>0m && afterCost>=afterMargin)
    return false;
   return afterCost>=minimumFreeMarginReserveEur;
  }}catch(OverflowException){return false;}
 }
 public static decimal? FloorEur(decimal configuredReserveEur,
  decimal buyCommissionEstimateEur,decimal sellCommissionEstimateEur,
  decimal currentSpreadRiskEstimateEur,decimal extraSlippageAllowanceEur) {
  if(configuredReserveEur<0m || buyCommissionEstimateEur<0m ||
     sellCommissionEstimateEur<0m || currentSpreadRiskEstimateEur<0m ||
     extraSlippageAllowanceEur<0m)return null;
  // decimal is 96-bit decimal *precision*, not unbounded exact rationals.
  // At very large values a positive cent can round away without OverflowException.
  // That would silently omit spread/slippage from an advertised EUR stop budget.
  static decimal AddPositiveExactOrThrow(decimal left,decimal increment) {
   decimal sum=checked(left+increment);
   if(increment>0m && sum<=left)throw new OverflowException(
    "EUR_POSITIVE_CASH_COMPONENT_LOST_TO_DECIMAL_PRECISION");
   return sum;
  }
  try {checked {
   decimal twoSidedFees=2m*Math.Max(buyCommissionEstimateEur,sellCommissionEstimateEur);
   decimal withSpread=AddPositiveExactOrThrow(twoSidedFees,currentSpreadRiskEstimateEur);
   decimal observedCostFloor=AddPositiveExactOrThrow(withSpread,extraSlippageAllowanceEur);
   return Math.Max(configuredReserveEur,observedCostFloor);
  }}catch(OverflowException){return null;}
 }
}
}
