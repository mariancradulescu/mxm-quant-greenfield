using System;

namespace Mxm.Replay {
/// <summary>
/// One shared, conservative per-account capital admission contract.
/// Monetary inputs MUST be denominated in the same account currency.
/// This cannot certify actual historical broker margin, financing, partial fills,
/// correlated positions, or atomic exclusion between simultaneously running robots.
/// </summary>
public static class MxmCapitalAdmission {
 public const string Admit="ADMIT_ESTIMATE_ONLY";
 public static string Check(decimal accountEquity,decimal accountFreeMargin,
  decimal requestedMargin,decimal estimatedEntryCommission,
  decimal maxFractionOfFreeMargin,decimal minimumFreeMarginReserve,
  int openOwnedAccountPositions,int maxConcurrentPositions) {
  if(accountEquity<=0m || accountFreeMargin<=0m || accountFreeMargin>accountEquity ||
     requestedMargin<=0m || estimatedEntryCommission<0m ||
     maxFractionOfFreeMargin<=0m || maxFractionOfFreeMargin>1m ||
     minimumFreeMarginReserve<0m || maxConcurrentPositions<1 ||
     openOwnedAccountPositions<0)
    return "REJECT_UNVERIFIED_OR_INVALID_ACCOUNT_INPUT";
  if(openOwnedAccountPositions>=maxConcurrentPositions)
    return "REJECT_ACCOUNT_POSITION_CAP";
  if(requestedMargin>accountFreeMargin*maxFractionOfFreeMargin)
    return "REJECT_MARGIN_FRACTION";
  if(accountFreeMargin-requestedMargin-estimatedEntryCommission<minimumFreeMarginReserve)
    return "REJECT_FREE_MARGIN_RESERVE";
  return Admit;
 }
}
}
