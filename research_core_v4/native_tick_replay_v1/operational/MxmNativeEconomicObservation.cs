using System;
using cAlgo.API;
using Mxm.Replay;

namespace cAlgo.Robots {
// Adds read-only economic facts to the ONE evolving product, not the
// frozen backtest bot. Never estimates a EUR expectancy or sends an order.
public sealed partial class MxmReferenceProductBot {
 void ReportNativeMinimumTicketAperture() {
  if (!nativeRun.IsObserving) return;
  try {
   if (nativeReceptionSymbol==null || nativeReceptionBook==null)
    throw new ArgumentException("NATIVE_ECONOMIC_SOURCE_MISSING");
   var book=nativeReceptionBook.ReadBook(Environment.TickCount64);
   var view=book.Observation;
   if (!view.SessionOpen || view.Faulted || view.Events==0 ||
       view.Origin!=MxmObservationOrigin.NativeCallbackSnapshot ||
       !MxmBookShape.NonCrossed(view.Shape) ||
       !book.Bid.HasValue || !book.Ask.HasValue ||
       !view.BidAgeMs.HasValue || !view.AskAgeMs.HasValue ||
       view.BidAgeMs.Value>5000 || view.AskAgeMs.Value>5000 ||
       view.BidAgeMs.Value<0 || view.AskAgeMs.Value<0)
    throw new ArgumentException("NATIVE_ECONOMIC_QUOTE_STALE_OR_UNOBSERVED");
   var symbol=nativeReceptionSymbol;
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
   Print("MXM_NATIVE_MIN_TICKET_PIP_CASH_ESTIMATE symbol={0} volumeUnits={1} observedSpreadPips={2:F5} nativeCashPerPipEUR={3:F6} nativeObservedSpreadRiskEUR={4:F6} profitForecastEUR=UNKNOWN commissionEUR=UNKNOWN slippageEUR=UNKNOWN payoffVerified=false accountMutation=false",
      symbol.Name,min,spreadPips,cashPerPip,spreadCashEstimate);
  } catch(Exception e) {
   // A read-only unavailable observation is never interpreted as low cost,
   // a missing position or permission to mutate an account.
   Print("MXM_NATIVE_MIN_TICKET_EUR_OBSERVATION_UNAVAILABLE reason={0} accountMutation=false",
     e.GetType().Name);
  }
 }
}
}
