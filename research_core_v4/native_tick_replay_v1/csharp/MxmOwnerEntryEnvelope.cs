using System;
namespace Mxm.Replay {
/// <summary>
/// Immutable OWNER absolute ceilings shared by native cTrader entry and
/// explicitly scenario-bound prospective CSharp account entry.
/// Inputs are EUR-denominated estimates from the current broker snapshot.
/// No historical funding proof, atomic multi-robot lease, actual broker fees,
/// future slippage, stop-fill limit or native operational acceptance is inferred.
/// This intentionally does NOT alter any frozen economic replay or its inputs.
/// </summary>
public static class MxmOwnerEntryEnvelope {
 public const decimal MaxTicketMarginEur=80m;
 public const decimal MinimumPostEntryFreeMarginEur=120m;
 public const decimal MaxEstimatedNewEntryLossEur=2m;
 public const string Admit="OWNER_ENTRY_ESTIMATE_ONLY";
 /// <summary>
 /// A per-side quote fee alone cannot fund two executions. For the declared
 /// current model prices, reserve 2x the higher BUY/SELL modeled fee. This
 /// does not bound future prices, swaps, broker charges or FX.
 /// Never reinterpret an unknown/negative/overflowing cost as zero.
 /// </summary>
 public static bool RoundTripFeeReserveCovers(decimal reserveEur,
  decimal estimatedBuyFeeEur,decimal estimatedSellFeeEur) {
  if(reserveEur<0m || estimatedBuyFeeEur<0m || estimatedSellFeeEur<0m)
   return false;
  try {checked {
   return reserveEur>=2m*Math.Max(estimatedBuyFeeEur,estimatedSellFeeEur);
  }} catch(OverflowException) {return false;}
 }

 public static string Check(decimal freeMarginEur,decimal ticketMarginEur,
  decimal estimatedEntryCommissionEur,decimal estimatedNewStopRiskEur,
  decimal estimatedNewRoundTripFrictionEur) {
  if(freeMarginEur<=0m || ticketMarginEur<=0m || estimatedEntryCommissionEur<0m ||
     estimatedNewStopRiskEur<=0m || estimatedNewRoundTripFrictionEur<0m)
   return "REJECT_UNVERIFIED_OWNER_INPUT";
  try {
   checked {
    if(ticketMarginEur>MaxTicketMarginEur)
     return "REJECT_OWNER_TICKET_MARGIN_GT_80";
    if(estimatedNewStopRiskEur+estimatedNewRoundTripFrictionEur>MaxEstimatedNewEntryLossEur)
     return "REJECT_OWNER_NEW_ENTRY_RISK_GT_2";
    if(freeMarginEur-ticketMarginEur-estimatedEntryCommissionEur<MinimumPostEntryFreeMarginEur)
     return "REJECT_OWNER_POST_ENTRY_RESERVE_LT_120";
   }
  } catch(OverflowException) {
   return "REJECT_UNVERIFIED_OWNER_INPUT";
  }
  return Admit;
 }
}
}
