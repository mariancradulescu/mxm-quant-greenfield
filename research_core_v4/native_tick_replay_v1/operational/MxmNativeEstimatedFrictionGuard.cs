using System;
using System.Collections.Generic;

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
 /// <summary>
 /// Current, order-free observation of NECESSARY broker minimum-ticket capacity
 /// on one EUR account. The only cost inputs are observed spread-cash and an
 /// explicit slippage cushion; commission, swaps, other open ticket risk,
 /// broker BIDASK execution and Cloud persistence remain UNKNOWN.
 /// A pass never constitutes admission and cannot authorize an order.
 /// A failure is decisive even before adding any missing positive cost.
 /// </summary>
 public static string MinimumTicketNecessaryCapacity(
  decimal equityEur,decimal freeMarginEur,
  decimal buyMarginEur,decimal sellMarginEur,
  decimal nativeStopRiskEur,decimal observedSpreadCostEur,
  decimal slippageCushionEur,decimal minFreeMarginReserveEur,
  decimal maxMarginFraction,decimal maxStopRiskFraction) {
  const string unknown="UNVERIFIED_NO_ADMISSION";
  if(equityEur<=0m || freeMarginEur<0m || freeMarginEur>equityEur ||
     buyMarginEur<=0m || sellMarginEur<=0m ||
     nativeStopRiskEur<=0m || observedSpreadCostEur<0m ||
     slippageCushionEur<0m || minFreeMarginReserveEur<0m ||
     maxMarginFraction<=0m || maxMarginFraction>1m ||
     maxStopRiskFraction<=0m || maxStopRiskFraction>1m)
   return unknown;
  try {checked {
   decimal cost=observedSpreadCostEur+slippageCushionEur;
   if((observedSpreadCostEur>0m || slippageCushionEur>0m) &&
      cost<=Math.Max(observedSpreadCostEur,slippageCushionEur))
    return unknown;
   decimal stopPlusKnownCost=nativeStopRiskEur+cost;
   if(cost>0m && stopPlusKnownCost<=nativeStopRiskEur)return unknown;
   // Risk and margin are BOTH necessary even before unknown broker fees,
   // other existing positions and finite after-stop account valuation.
   if(stopPlusKnownCost>equityEur*maxStopRiskFraction)
    return "STOP_PLUS_VISIBLE_COST_NECESSARY_FAIL";
   decimal marginLimit=equityEur*maxMarginFraction;
   if(buyMarginEur>marginLimit || sellMarginEur>marginLimit ||
      !PostEntryReserveCovers(freeMarginEur,buyMarginEur,cost,minFreeMarginReserveEur) ||
      !PostEntryReserveCovers(freeMarginEur,sellMarginEur,cost,minFreeMarginReserveEur))
    return "MIN_VOLUME_MARGIN_AND_CASH_RESERVE_NECESSARY_FAIL";
   return "PASSES_VISIBLE_NECESSARY_ONLY_NO_ADMISSION";
  }}catch(OverflowException){return unknown;}
 }
 /// <summary>Cost floors for ACTUAL existing MXM broker tickets, one per
 /// symbol/volume. Never substitute proposed-ticket cost times position count.
 /// Missing cost, negative cost or decimal precision loss blocks admission.
 /// </summary>
 public static decimal? SumExistingPositionCostFloors(IReadOnlyList<decimal?> costs) {
  if(costs==null)return null;
  decimal total=0m;
  try {checked {
   foreach(decimal? cost in costs) {
    if(!cost.HasValue || cost.Value<0m)return null;
    decimal updated=total+cost.Value;
    if(cost.Value>0m && updated<=total)return null;
    total=updated;
   }
   return total;
  }}catch(OverflowException){return null;}
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
