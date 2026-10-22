using System;
namespace Mxm.Replay {
/// <summary>
/// Bounded, account-wide pre-entry stop-risk estimate in account EUR.
/// This is NOT an executable loss limit: gaps, slip, swaps, slippage, broker
/// stop activation and concurrent cBot instances remain unknown.
/// Inputs are precomputed with cTrader Symbol.AmountRisked for the actual
/// normalized executable volume of each existing MXM position and new order.
/// </summary>
public static class MxmStopRiskAdmission {
 public const string Admit="ADMIT_STOP_RISK_ESTIMATE_ONLY";
 public static string Check(decimal accountEquityEur,decimal existingMxmStopRiskEur,
  decimal proposedStopRiskEur,decimal maxAccountRiskFraction,
  decimal estimatedNewRoundTripFrictionReserveEur,decimal estimatedExistingFrictionReserveEur) {
  if(accountEquityEur<=0m || existingMxmStopRiskEur<0m ||
     proposedStopRiskEur<=0m || maxAccountRiskFraction<=0m ||
     maxAccountRiskFraction>1m || estimatedNewRoundTripFrictionReserveEur<0m ||
     estimatedExistingFrictionReserveEur<0m)
   return "REJECT_INVALID_OR_UNVERIFIED_STOP_RISK";
  decimal budget=accountEquityEur*maxAccountRiskFraction;
  if(existingMxmStopRiskEur+estimatedExistingFrictionReserveEur>=budget)
   return "REJECT_EXISTING_STOP_RISK_EXHAUSTED";
  if(proposedStopRiskEur+estimatedNewRoundTripFrictionReserveEur >
     budget-existingMxmStopRiskEur-estimatedExistingFrictionReserveEur)
   return "REJECT_AGGREGATE_STOP_RISK_EXCESS";
  return Admit;
 }
}
