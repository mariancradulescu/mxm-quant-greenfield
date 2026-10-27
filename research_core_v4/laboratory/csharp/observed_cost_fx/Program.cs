using System.Globalization;
using System.Text.Json;
using Mxm.Replay;
try {
 if(args.Length!=3 || args[0] is not ("--fixture" or "--source"))throw new ArgumentException("FX_EXACT_ARGUMENTS");
 using var input=JsonDocument.Parse(File.ReadAllBytes(args[1]));var root=input.RootElement;
 var instruments=root.GetProperty("instruments").EnumerateArray().Select(i=>new MxmFxInstrument(i.GetProperty("Source").GetString()!,i.GetProperty("BaseAsset").GetString()!,i.GetProperty("QuoteAsset").GetString()!)).ToArray();
 var graph=new MxmObservedCostFx(instruments);
 var sources=root.TryGetProperty("sources",out var roster)?roster.EnumerateArray().Select(x=>x.GetString()!).ToArray():instruments.Select(i=>i.Source).ToArray();
 var states=sources.ToDictionary(s=>s,s=>MxmBookObservations.RawFields());
 foreach(var state in states.Values)state.BeginEpoch(0);
 MxmObservedFxBook? Book(string source,long now) {
  if(!states.TryGetValue(source,out var state))return null;
  var b=state.ReadBook(now);return new(source,b.Bid,b.Ask,b.Observation);
 }
 var output=new List<object>();
 if(args[0]=="--fixture") {
  foreach(var a in root.GetProperty("actions").EnumerateArray()) {
   long now=a.GetProperty("now").GetInt64();
   try {
    switch(a.GetProperty("op").GetString()) {
     case "observe":
      decimal? Price(string name)=>a.GetProperty(name).ValueKind==JsonValueKind.Null?null:a.GetProperty(name).GetDecimal();
      states[a.GetProperty("source").GetString()!].Observe(Price("bid"),Price("ask"),now,now,null);break;
     case "begin":states[a.GetProperty("source").GetString()!].BeginEpoch(now);break;
     case "end":states[a.GetProperty("source").GetString()!].EndEpoch(now);break;
     case "rate":
      var estimate=graph.CostRate(a.GetProperty("from").GetString()!,a.GetProperty("to").GetString()!,now,s=>Book(s,now));
      output.Add(new {status="ESTIMATE",estimate});break;
     default:throw new ArgumentException("FX_UNKNOWN_OPERATION");
    }
   }catch(ArgumentException e){output.Add(new {status="HOLD",reason=e.Message});}
  }
 }else {
  var terms=root.GetProperty("terms").EnumerateArray().ToDictionary(i=>i.GetProperty("symbol_id").GetInt32());
  foreach(var a in root.GetProperty("events").EnumerateArray()) {
   int sid=a.GetProperty("symbol").GetInt32();string source=sid.ToString(CultureInfo.InvariantCulture);
   long sequence=a.GetProperty("sequence").GetInt64(),now=a.GetProperty("arrival_ns").GetInt64()/1000000;
   decimal? Price(string name)=>a.GetProperty(name).ValueKind==JsonValueKind.Null?null:a.GetProperty(name).GetDecimal()/100000m;
   states[source].Observe(Price("bid"),Price("ask"),now,a.GetProperty("received_ms").GetInt64(),a.GetProperty("server_ms").ValueKind==JsonValueKind.Null?null:a.GetProperty("server_ms").GetInt64());
   string status="ESTIMATE";decimal? ceiling=null;
   try {
    var b=Book(source,now)!;var v=b.Observation;
    if(!b.Bid.HasValue||!b.Ask.HasValue||!v.BidAgeMs.HasValue||!v.AskAgeMs.HasValue||v.BidAgeMs>5000||v.AskAgeMs>5000||!MxmBookShape.NonCrossed(v.Shape))throw new ArgumentException("SOURCE_TICKET_BOOK_UNOBSERVED_INVALID_OR_TOO_OLD");
    var item=terms[sid];var t=MxmInstrumentCommission.Decode(item.GetProperty("full"),sid,item.GetProperty("quote_asset").GetString()!);
    var native=new MxmNativeCommissionTerms(t.Kind-1,t.MinimumKind-1,t.QuoteAsset,t.MinimumAsset,t.Rate,t.Minimum,t.LotSize/100m);
    decimal Fx(string from,string to)=>graph.CostRate(from,to,now,s=>Book(s,now)).Rate;
    decimal qUsd=t.Kind==1&&t.Rate>0?Fx(t.QuoteAsset,"USD"):0m;
    decimal usdEur=(t.Kind is 1 or 2) && t.Rate>0?Fx("USD","EUR"):0m;
    decimal qEur=((t.Kind is 3 or 4)&&t.Rate>0||t.MinimumKind==2&&t.Minimum>0)?Fx(t.QuoteAsset,"EUR"):0m;
    decimal minEur=t.MinimumKind==1&&t.Minimum>0?Fx(t.MinimumAsset,"EUR"):0m;
    var fee=MxmNativeCommission.Price(native,t.MinimumVolume/100m,b.Bid.Value,b.Ask.Value,qUsd,usdEur,qEur,minEur);
    ceiling=decimal.Round(fee.PerSideCeilingEur,18,MidpointRounding.ToPositiveInfinity);
   }catch(ArgumentException e){status=e.Message.StartsWith("FX_")||e.Message.StartsWith("SOURCE_TICKET_")?e.Message:"SOURCE_FEE_UNRESOLVED";}
   output.Add(new {sequence,symbol=sid,status,per_side_ceiling_eur=ceiling?.ToString(CultureInfo.InvariantCulture)});
  }
 }
 File.WriteAllText(args[2],JsonSerializer.Serialize(output)+"\n");
}catch(Exception e){Console.Error.WriteLine("MXM_OBSERVED_COST_FX_FAILED_"+e.GetType().Name);Environment.ExitCode=2;}
