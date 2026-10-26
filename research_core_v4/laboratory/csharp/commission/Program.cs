using System.Globalization;
using System.Text.Json;
using Mxm.Replay;
if(args.Length!=2)throw new ArgumentException("COMMISSION_INPUT_OUTPUT");
using var input=JsonDocument.Parse(File.ReadAllBytes(args[0]));var output=new List<object>();
foreach(var item in input.RootElement.EnumerateArray()){
 try {
  var t=MxmInstrumentCommission.Decode(item.GetProperty("full"),item.GetProperty("symbol_id").GetInt64(),item.GetProperty("quote_asset").GetString()!);
  MxmCommissionAmount? priced=null;
  if(item.TryGetProperty("fill",out var f)){
   var fx=new Dictionary<string,decimal>();foreach(var p in f.GetProperty("cost_eur_per_asset").EnumerateObject())fx[p.Name]=decimal.Parse(p.Value.GetString()!,CultureInfo.InvariantCulture);
   priced=MxmInstrumentCommission.Price(t,f.GetProperty("volume_cents").GetInt64(),decimal.Parse(f.GetProperty("price").GetString()!,CultureInfo.InvariantCulture),
    f.TryGetProperty("usd_per_quote",out var usd) && usd.ValueKind!=JsonValueKind.Null?decimal.Parse(usd.GetString()!,CultureInfo.InvariantCulture):null,fx);
  }
  output.Add(new{status="EXPLICIT_TERMS_DECODED_NOT_HISTORICAL_CERTIFICATION",terms=t,priced});
 }catch(Exception e) when(e is ArgumentException or OverflowException or InvalidOperationException or KeyNotFoundException){
  output.Add(new{status="COST_UNRESOLVED",reason=e.GetType().Name});
 }
}
File.WriteAllText(args[1],JsonSerializer.Serialize(output));
