using System;
namespace Mxm.Replay;
// Reuse the established explicit SCENARIO ledger; current displayed metadata
// does not become historical financing or an actual broker posting.
public static class MxmFinancingScenarioAdapter {
 public static MxmFinancingCashflow Bind(MxmFinancingComponent component,string expectedSourceSha256,long expectedSymbolId,string expectedQuoteAsset,
  string scenarioSha256,string symbol,DateTime bookedUtc,DateTime entryUtc,int direction,
  decimal units,DateTime startUtc,DateTime endUtc,decimal creditFx,decimal debitFx){
  if(!MxmDisplayedFinancingCalculator.Digest(expectedSourceSha256) || component.SourceSha256!=expectedSourceSha256 || component.SymbolId!=expectedSymbolId || component.Asset!=expectedQuoteAsset ||
   !MxmDisplayedFinancingCalculator.Digest(scenarioSha256) || string.IsNullOrWhiteSpace(symbol) ||
   (direction!=1 && direction!=-1) || units<=0 || component.Direction!=direction || component.VolumeCents/100m!=units || component.ActualBrokerCharge || component.HistoricalApplicability)
   throw new ArgumentException("FINANCING_SCENARIO_IDENTITY");
  decimal amount=MxmDisplayedFinancingCalculator.ConvertScenario(component,creditFx,debitFx);
  return new(bookedUtc,symbol,entryUtc,direction,units,startUtc,endUtc,amount,scenarioSha256);
 }
}
