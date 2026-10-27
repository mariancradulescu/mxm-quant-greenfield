using System.Text.Json;
using Mxm.Replay;
// This public-receipt mode authenticates no source by itself. Its caller must
// verify the immutable receipt first; it never prices a market fill or reads FX.
if(args.Length==3 && args[0]=="--commission-components") {
 using var receipt=JsonDocument.Parse(File.ReadAllBytes(args[1]));var components=new List<object>();
 foreach(var panel in receipt.RootElement.GetProperty("panel").EnumerateArray()) {
  long id=panel.GetProperty("symbol_id").GetInt64();
  if(panel.GetProperty("terms").ValueKind==JsonValueKind.Null) {
   components.Add(new {symbol_id=id,status="COST_UNRESOLVED"});continue;
  }
  var terms=JsonSerializer.Deserialize<MxmCommissionTerms>(panel.GetProperty("terms"))!;
  if(!MxmInstrumentCommission.Valid(terms) || terms.SymbolId!=id)throw new ArgumentException("PUBLIC_MARGIN_TERMS_IDENTITY");
  decimal? declaredBase=terms.Kind is 2 or 4?(decimal)terms.MinimumVolume/terms.LotSize*terms.Rate:null;
  string? baseAsset=terms.Kind==2?"USD":terms.Kind==4?terms.QuoteAsset:null;
  var floor=MxmCommissionFloorCalculator.Compute(terms,new Dictionary<string,decimal>());
  components.Add(new {symbol_id=id,status="DECLARED_COMPONENTS_NOT_ACTUAL_CHARGES",declared_base_per_fill=declaredBase,
   declared_base_asset=baseAsset,declared_minimum_per_fill=terms.Minimum,declared_minimum_asset=terms.MinimumAsset,
   no_fx_no_price_floor=floor,source_authenticated_in_program=false,full_entry_admission=false,total_trading_cost_proven=false});
 }
 File.WriteAllText(args[2],JsonSerializer.Serialize(components)+"\n");return;
}
if(args.Length!=2)throw new ArgumentException("CURRENT_MARGIN_EXACT_ARGUMENTS");
using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));var result=new List<object>();
foreach(var i in doc.RootElement.EnumerateArray()) {
 long sid=i.GetProperty("symbol_id").GetInt64();
 object? margin=null,terms=null;string marginStatus="MARGIN_UNRESOLVED",feeStatus="COST_UNRESOLVED";
 try {
  var m=i.GetProperty("margin");int? digits=m.GetProperty("money_digits").ValueKind==JsonValueKind.Null?null:m.GetProperty("money_digits").GetInt32();
  if(i.GetProperty("full").GetProperty("minVolume").GetInt64()!=i.GetProperty("minimum_volume").GetInt64())throw new ArgumentException("MINIMUM_METADATA_MISMATCH");
  margin=MxmExpectedMarginObservation.Decode(sid,i.GetProperty("deposit_asset").GetString()!,i.GetProperty("minimum_volume").GetInt64(),
   m.GetProperty("volume").GetInt64(),digits,m.GetProperty("buy").GetInt64(),m.GetProperty("sell").GetInt64());
  marginStatus="DATED_MARGIN_ESTIMATE_ONLY";
 }catch(Exception e) when(e is ArgumentException or OverflowException or InvalidOperationException or KeyNotFoundException or FormatException){ }
 try {
  terms=MxmInstrumentCommission.Decode(i.GetProperty("full"),sid,i.GetProperty("quote_asset").GetString()!);
  feeStatus="DATED_TERMS_ONLY_FEE_EUR_UNRESOLVED";
 }catch(Exception e) when(e is ArgumentException or OverflowException or InvalidOperationException or KeyNotFoundException or FormatException){ }
 result.Add(new{symbol_id=sid,margin_status=marginStatus,margin,fee_status=feeStatus,terms,
  round_trip_fee_eur=(decimal?)null,full_entry_admission=false,stop_risk_proven=false,dated_historical_terms_proven=false});
}
File.WriteAllText(args[1],JsonSerializer.Serialize(new {runtime_version=Environment.Version.ToString(),target_framework=typeof(MxmExpectedMarginView).Assembly.GetCustomAttributes(typeof(System.Runtime.Versioning.TargetFrameworkAttribute),false).Cast<System.Runtime.Versioning.TargetFrameworkAttribute>().Single().FrameworkName,rows=result})+"\n");
