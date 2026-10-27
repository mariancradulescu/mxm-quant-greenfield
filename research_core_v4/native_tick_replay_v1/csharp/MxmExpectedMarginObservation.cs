using System;
namespace Mxm.Replay {
/// <summary>One protocol minimum-volume estimate, explicitly scaled in the
/// already-authenticated EUR account asset. A necessary margin-only test:
/// zero fee here is a mathematical lower bound, never a claim of free entry.</summary>
public sealed record MxmExpectedMarginView(long SymbolId,long VolumeCents,int MoneyDigits,
 decimal BuyEur,decimal SellEur,string BuyMarginOnlyGate,string SellMarginOnlyGate) {
 public bool FullEntryAdmission=>false;
 public bool HistoricalApplicability=>false;
 public bool ActualBrokerCharge=>false;
}
public static class MxmExpectedMarginObservation {
 public static MxmExpectedMarginView Decode(long symbolId,string depositAsset,long requestedMinimum,
  long returnedVolume,int? moneyDigits,long buyMargin,long sellMargin) {
  if(symbolId<=0 || depositAsset!="EUR" || requestedMinimum<=0 || returnedVolume!=requestedMinimum ||
     !moneyDigits.HasValue || moneyDigits.Value<0 || moneyDigits.Value>28 || buyMargin<=0 || sellMargin<=0)
   throw new ArgumentException("EXPECTED_MARGIN_IDENTITY_UNITS_OR_NONPOSITIVE_ESTIMATE");
  decimal scale=1m;for(int i=0;i<moneyDigits.Value;i++)scale*=10m;
  decimal buy=buyMargin/scale,sell=sellMargin/scale;
  string Gate(decimal margin) {
   // Use exactly the existing account/OWNER ceilings at one EUR200 reference,
   // not a newly funded account or a replay. Costs and exposure remain unknown.
   string capital=MxmCapitalAdmission.Check(200m,200m,margin,0m,0.4m,
    MxmOwnerEntryEnvelope.MinimumPostEntryFreeMarginEur,0,1);
   return margin>MxmOwnerEntryEnvelope.MaxTicketMarginEur || capital!=MxmCapitalAdmission.Admit
    ?"FAILS_NECESSARY_MARGIN_ONLY_BOUND":"PASSES_NECESSARY_MARGIN_ONLY_BOUND_NOT_ENTRY_ADMISSION";
  }
  return new(symbolId,returnedVolume,moneyDigits.Value,buy,sell,Gate(buy),Gate(sell));
 }
}
}
