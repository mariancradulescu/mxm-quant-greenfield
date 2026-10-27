using System.Text.Json;
using Mxm.Replay;
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
