using System;
using System.IO;
using System.Text.Json;

namespace Mxm.Replay {
/// <summary>Captured symbol specification applied as an explicit counterfactual.
/// Not dated historical fees, broker conversion rates, financing or executions.</summary>
public sealed record MxmEurUsdCapturedCosts(long MinCents,long MaxCents,long StepCents,
 long LotCents,int CommissionType,long PreciseRate,long PreciseMinimum,string MinimumAsset) {
 static void Need(bool ok,string reason) {
  if(!ok)throw new InvalidDataException("MXM_CAPTURED_COST_"+reason);
 }
 public void Validate() {
  Need(MinCents>0 && MaxCents>=MinCents && StepCents>0 && MinCents%StepCents==0,
   "VOLUME_GEOMETRY_UNKNOWN");
  Need(CommissionType>=1 && CommissionType<=3 && PreciseRate>=0 && PreciseMinimum>=0 &&
   (MinimumAsset=="USD" || MinimumAsset=="EUR"),"FEE_SEMANTICS_UNKNOWN");
  Need(CommissionType!=2 || LotCents>0,"LOT_UNITS_UNKNOWN");
 }
 public bool Allows(decimal units) {
  Validate();decimal cents=units*100m;
  return units>0 && cents==decimal.Truncate(cents) &&
   cents>=MinCents && cents<=MaxCents && cents%StepCents==0;
 }
 public static decimal ConvertSignedUsd(decimal usd,decimal bid,decimal ask) {
  Need(bid>0 && ask>=bid,"FX_QUOTE");
  // To receive EUR for positive USD, buy EUR at ASK. To fund a USD loss,
  // sell EUR at BID. These are hypothetical executable-side conversions.
  return usd>=0 ? usd/ask : usd/bid;
 }
 public decimal FeeEur(decimal units,decimal executionPrice,decimal bid,decimal ask) {
  Need(Allows(units) && executionPrice>0 && bid>0 && ask>=bid,"VOLUME_OR_PRICE");
  decimal rate=PreciseRate/(CommissionType==3?100000m:100000000m);
  decimal usd=CommissionType switch {
   1 => units*executionPrice*rate/1000000m,
   2 => units/(LotCents/100m)*rate,
   3 => units*executionPrice*rate/100m,
   _ => throw new InvalidDataException("MXM_CAPTURED_COST_FEE_TYPE")
  };
  decimal minimum=PreciseMinimum/100000000m;
  // Explicit turnover-USD convention: base EUR notional valued at modeled
  // fill price. Actual broker baseToUSD/money rounding is NOT established.
  decimal variableEur=usd/bid;
  decimal minimumEur=MinimumAsset=="EUR"?minimum:minimum/bid;
  return Math.Max(variableEur,minimumEur);
 }
 public static MxmEurUsdCapturedCosts Load(string path,bool nativeSource) {
  using var doc=JsonDocument.Parse(File.ReadAllBytes(path));var root=doc.RootElement;
  Need(root.GetProperty("schema").GetString()=="mxm.captured-native-symbol-terms.v1" &&
   root.GetProperty("symbol_id").GetInt32()==1 &&
   !root.GetProperty("historical_commission_proven").GetBoolean() &&
   !root.GetProperty("dated_historical_volume_rules_proven").GetBoolean(),"SNAPSHOT_NOT_HISTORY");
  if(nativeSource) {
   Need(root.GetProperty("source_crypto_authenticated_by_original_native_replay").GetBoolean() &&
    root.GetProperty("source_run").GetInt64()==39660692230 &&
    root.GetProperty("source_ciphertext_sha256").GetString()==
     "f1d828d94b304e2af1f310701f92dcb31db935a8db7fc3f8772087adf5499346" &&
    root.GetProperty("classification").GetString()==
     "AUTHENTICATED_CAPTURE_SNAPSHOT_NOT_DATED_HISTORICAL_EXECUTION_TERMS","SOURCE_BINDING");
  } else Need(root.GetProperty("classification").GetString()=="ARTIFICIAL_CAPTURED_TERMS_FIXTURE_ONLY",
    "EXPLICIT_ARTIFICIAL_TERMS");
  var raw=root.GetProperty("raw_optional_fields");
  // Required numeric properties must be PRESENT, never protobuf defaults.
  int kind=raw.GetProperty("commissionType").GetInt32();
  int minimumKind=raw.GetProperty("minCommissionType").GetInt32();
  string asset=minimumKind==2?"USD":minimumKind==1?
   raw.GetProperty("minCommissionAsset").GetString()??"UNKNOWN":"UNKNOWN";
  long lot=raw.TryGetProperty("lotSize",out var lots) && lots.ValueKind==JsonValueKind.Number?
   lots.GetInt64():0;
  var result=new MxmEurUsdCapturedCosts(raw.GetProperty("minVolume").GetInt64(),
   raw.GetProperty("maxVolume").GetInt64(),raw.GetProperty("stepVolume").GetInt64(),lot,kind,
   raw.GetProperty("preciseTradingCommissionRate").GetInt64(),
   raw.GetProperty("preciseMinCommission").GetInt64(),asset);
  result.Validate();return result;
 }
}
}
