using System;
using cAlgo.API;
using cAlgo.API.Internals;
using Mxm.Replay;

namespace cAlgo.Robots {
// Adds read-only economic facts to the ONE evolving product, not the
// frozen backtest bot. Never estimates a EUR expectancy or sends an order.
public sealed partial class MxmReferenceProductBot {
 void ReportNativeMinimumTicketAperture() =>
  ReportNativeMinimumTicketAperture(nativeReceptionSymbol,nativeReceptionBook);
 // Reuse the SAME actual native broker-account EUR cost/capacity evaluator
 // for the selected causal portfolio symbol, never just the chart symbol.
 // Return is a necessary-only receipt, NOT an executable signal or order gate.
 string ReportNativeMinimumTicketAperture(Symbol? selectedSymbol,
  MxmBookObservation<double>? selectedBook) {
  if (!nativeRun.IsObserving) return "READ_ONLY_MODE_UNAVAILABLE";
  try {
   if (selectedSymbol==null || selectedBook==null)
    throw new ArgumentException("NATIVE_ECONOMIC_SOURCE_MISSING");
   var book=selectedBook.ReadBook(Environment.TickCount64);
   var view=book.Observation;
   if (!view.SessionOpen || view.Faulted || view.Events==0 ||
       view.Origin!=MxmObservationOrigin.NativeCallbackSnapshot ||
       !MxmBookShape.NonCrossed(view.Shape) ||
       !book.Bid.HasValue || !book.Ask.HasValue ||
       !view.BidAgeMs.HasValue || !view.AskAgeMs.HasValue ||
       view.BidAgeMs.Value>5000 || view.AskAgeMs.Value>5000 ||
       view.BidAgeMs.Value<0 || view.AskAgeMs.Value<0)
    throw new ArgumentException("NATIVE_ECONOMIC_QUOTE_STALE_OR_UNOBSERVED");
   var symbol=selectedSymbol;
   double bid=book.Bid.Value,ask=book.Ask.Value;
   if(!double.IsFinite(bid)||!double.IsFinite(ask)||bid<=0||ask<bid||
      bid!=symbol.Bid||ask!=symbol.Ask)
    throw new ArgumentException("NATIVE_ECONOMIC_BOOK_NATIVE_MISMATCH");
   double min=symbol.VolumeInUnitsMin,step=symbol.VolumeInUnitsStep,max=symbol.VolumeInUnitsMax;
   if (!double.IsFinite(min)||!double.IsFinite(step)||!double.IsFinite(max)||
       min<=0||step<=0||max<min||
       symbol.NormalizeVolumeInUnits(min,RoundingMode.Down)!=min||
       Account.Asset?.Name!="EUR"||
       !double.IsFinite(Account.Equity)||!double.IsFinite(Account.FreeMargin)||
       Account.Equity<=0||Account.FreeMargin<0||Account.FreeMargin>Account.Equity||
       StopLossPips<=0)
    throw new ArgumentException("NATIVE_ECONOMIC_MIN_TICKET_OR_ACCOUNT_INVALID");
   double buyMargin=symbol.GetEstimatedMargin(TradeType.Buy,min);
   double sellMargin=symbol.GetEstimatedMargin(TradeType.Sell,min);
   double stopRisk=symbol.AmountRisked(min,StopLossPips);
   // AmountRisked is the platform's account-currency pip-risk estimate,
   // NOT a broker commission or actual executable spread cost. Comparing a
   // cash prediction to spread bps alone is invalid for tiny minimum tickets.
   if(!double.IsFinite(symbol.PipSize) || symbol.PipSize<=0)
    throw new ArgumentException("NATIVE_ECONOMIC_PIP_SIZE_UNVERIFIED");
   double spreadPips=(ask-bid)/symbol.PipSize;
   double cashPerPip=symbol.AmountRisked(min,1.0);
   double spreadCashEstimate=symbol.AmountRisked(min,Math.Max(0d,spreadPips));
   double spreadBps=10000*(ask-bid)/((ask+bid)/2);
   if(!double.IsFinite(buyMargin)||!double.IsFinite(sellMargin)||
      !double.IsFinite(stopRisk)||!double.IsFinite(spreadBps)||
      !double.IsFinite(cashPerPip)||!double.IsFinite(spreadCashEstimate)||
      !double.IsFinite(spreadPips)||cashPerPip<=0||spreadCashEstimate<0||
      buyMargin<=0||sellMargin<=0||stopRisk<=0||spreadBps<0)
    throw new ArgumentException("NATIVE_ECONOMIC_MARGIN_STOP_OR_SPREAD_INVALID");
   string status=buyMargin<=Account.FreeMargin && sellMargin<=Account.FreeMargin
       ?"CURRENT_MIN_VOLUME_MARGIN_NECESSARY_ONLY":"ONE_OR_BOTH_MIN_DIRECTIONS_UNAVAILABLE";
   Print("MXM_NATIVE_MIN_TICKET_EUR_OBSERVATION symbol={0} minUnits={1} stepUnits={2} bid={3} ask={4} spreadBps={5:F5} minBuyMarginEUR={6:F4} minSellMarginEUR={7:F4} illustrativeStopPips={8} stopRiskEstimateEUR={9:F4} equityEUR={10:F4} freeMarginEUR={11:F4} observationAgeMs={12} necessaryMargin={13} commissionEUR=UNKNOWN slippageEUR=UNKNOWN contractMultiplier=UNVERIFIED expectedNetEUR=UNKNOWN brokerFill=false HARD21=false cloudRecovery=false accountMutation=false",
      symbol.Name,min,step,bid,ask,spreadBps,buyMargin,sellMargin,StopLossPips,
      stopRisk,Account.Equity,Account.FreeMargin,
      Math.Max(view.BidAgeMs.Value,view.AskAgeMs.Value),status);
   // Separate receipt, purpose-latched read-only: not a fee, fill or a
   // time-stamped certified EUR settlement price.
   // Native broker-declared symbol fee terms, sampled at this callback.
   // Raw current *terms* are not a charge, a verified historical commission,
   // a EUR asset conversion or a guaranteed future execution cost.
   // This adds no broker request, order, storage or network side effect.
   Print("MXM_NATIVE_MIN_TICKET_DECLARED_FEE_TERMS symbol={0} nativeCommissionType={1} nativeCommissionRate={2} nativeMinCommissionType={3} nativeMinCommission={4} nativeMinCommissionAsset={5} nativeQuoteAsset={6} nativeLotSize={7} minVolumeUnits={8} callbackUtc={9:O} historicalPeriodAligned=false commissionSettledEUR=UNKNOWN costFxLease=false accountMutation=false",
      symbol.Name,symbol.CommissionType,symbol.Commission,
      symbol.MinCommissionType,symbol.MinCommission,symbol.MinCommissionAsset?.Name??"",
      symbol.QuoteAsset?.Name??"",symbol.LotSize,min,Server.TimeInUtc);
   Print("MXM_NATIVE_MIN_TICKET_PIP_CASH_ESTIMATE symbol={0} volumeUnits={1} observedSpreadPips={2:F5} nativeCashPerPipEUR={3:F6} nativeObservedSpreadRiskEUR={4:F6} profitForecastEUR=UNKNOWN commissionEUR=UNKNOWN slippageEUR=UNKNOWN payoffVerified=false accountMutation=false",
      symbol.Name,min,spreadPips,cashPerPip,spreadCashEstimate);
   // Economic readback for ALL observed asset classes, not an instrument
   // eligibility decision and NOT a fee estimate. The coded EUR2 limit is
   // a currently conservative DIRECTOR runtime cap, not immutable OWNER law.
   if(!double.IsFinite(ExtraSlippageCushionEur) || ExtraSlippageCushionEur<0)
    throw new ArgumentException("NATIVE_SLOP_CUSHION_UNVERIFIED");
   decimal headroom=checked(MxmOwnerEntryEnvelope.MaxEstimatedNewEntryLossEur-
     (decimal)stopRisk-(decimal)spreadCashEstimate-(decimal)ExtraSlippageCushionEur);
   Print("MXM_NATIVE_MIN_TICKET_RISK_HEADROOM symbol={0} minUnits={1} codedLossCapEur={2} nativeStopRiskEur={3:F6} observedSpreadRiskEur={4:F6} additionalSlippageCushionEur={5:F6} maximumTwoSidedCommissionBudgetEur={6:F6} necessaryStopPlusSpreadRoom={7} actualCommissionEur=UNKNOWN expectedNetEur=UNKNOWN brokerFill=false",
     symbol.Name,min,MxmOwnerEntryEnvelope.MaxEstimatedNewEntryLossEur,stopRisk,
     spreadCashEstimate,ExtraSlippageCushionEur,headroom,headroom>0?"POSITIVE_NOT_SUFFICIENT":"NONPOSITIVE");
   // This first-party C# necessary-only preflight never opens a trade or
   // claims a round-trip commission, all-position stop risk, EUR NET edge or
   // executable broker fill. Distinguish an affordable *margin* from the
   // minimum ticket's combined mark-to-market/cash cost headroom.
   // It is intentionally limited to observable inputs; unknown broker fees,
   // swaps, other tickets and cloud recovery can only make admission harder.
   string necessary=MxmNativeEstimatedFrictionGuard.MinimumTicketNecessaryCapacity(
     checked((decimal)Account.Equity),checked((decimal)Account.FreeMargin),
     checked((decimal)buyMargin),checked((decimal)sellMargin),
     checked((decimal)stopRisk),checked((decimal)spreadCashEstimate),
     checked((decimal)ExtraSlippageCushionEur),
     checked((decimal)MinimumFreeMarginReserveEur),
     checked((decimal)MaxMarginFraction),
     checked((decimal)(MaxEstimatedMxmStopRiskPercent/100.0)));
   Print("MXM_NATIVE_EUR200_MIN_TICKET_JOINT_NECESSARY_ONLY symbol={0} status={1} minUnits={2} modeledVisibleSpreadCostEUR={3:F6} slippageCushionEUR={4:F6} minBuyMarginEUR={5:F6} minSellMarginEUR={6:F6} observedStopRiskEUR={7:F6} accountEquityEUR={8:F6} accountFreeMarginEUR={9:F6} accountRiskPercent={10} maxMarginFraction={11} freeMarginReserveEUR={12} actualCommissionEUR=UNKNOWN swapEUR=UNKNOWN existingTicketFullStopRisk=UNKNOWN simultaneousBrokerExecution=false cashNetEdge=UNKNOWN orderAdmission=false accountMutation=false cloudActivation=false",
     symbol.Name,necessary,min,spreadCashEstimate,ExtraSlippageCushionEur,
     buyMargin,sellMargin,stopRisk,Account.Equity,Account.FreeMargin,
     MaxEstimatedMxmStopRiskPercent,MaxMarginFraction,MinimumFreeMarginReserveEur);
   return necessary;
  } catch(Exception e) {
   // A read-only unavailable observation is never interpreted as low cost,
   // a missing position or permission to mutate an account.
   Print("MXM_NATIVE_MIN_TICKET_EUR_OBSERVATION_UNAVAILABLE reason={0} accountMutation=false",
     e.GetType().Name);
   return "SOURCE_OR_COST_UNVERIFIED_NO_ADMISSION";
  }
 }
}
}
