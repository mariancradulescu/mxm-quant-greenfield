using System.Text.Json;
using Mxm.Replay;
using var input=JsonDocument.Parse(File.ReadAllBytes(args[0]));
var states=new Dictionary<string,MxmBookObservation<decimal>>();
foreach(var source in input.RootElement.GetProperty("sources").EnumerateArray()) {
 var state=MxmBookObservations.RawFields();state.BeginEpoch(0);states.Add(source.GetString()!,state);
}
MxmNativeRiskObservationLease? lease=null;
var output=new List<object>();
foreach(var a in input.RootElement.GetProperty("actions").EnumerateArray()) {
 long now=a.GetProperty("now").GetInt64();
 MxmObservedFxBook? Read(string source){
  if(!states.TryGetValue(source,out var state))return null;
  var book=state.ReadBook(now);return new(source,book.Bid,book.Ask,book.Observation);
 }
 try {
  switch(a.GetProperty("op").GetString()) {
   case "observe":
    decimal? Price(string field)=>a.GetProperty(field).ValueKind==JsonValueKind.Null?null:a.GetProperty(field).GetDecimal();
    states[a.GetProperty("source").GetString()!].Observe(Price("bid"),Price("ask"),now,now,null);break;
   case "begin":states[a.GetProperty("source").GetString()!].BeginEpoch(now);break;
   case "end":states[a.GetProperty("source").GetString()!].EndEpoch(now);break;
   case "down":states[a.GetProperty("source").GetString()!].ReportTransport(MxmReportedTransport.Down,now);break;
   case "capture":
    lease=null;
    lease=MxmNativeRiskObservationLease.Capture(a.GetProperty("quotes").EnumerateArray().Select(x=>
     new MxmNativeRiskQuote(x.GetProperty("source").GetString()!,x.GetProperty("bid").GetDecimal(),x.GetProperty("ask").GetDecimal())),now,Read);
    output.Add(new {status="CAPTURED",expiry=lease.ExpiresAtMs,sources=lease.Sources});break;
   case "verify":
    if(lease==null)throw new ArgumentException("NO_CAPTURE");lease.Verify(now,Read);
    output.Add(new {status="VERIFIED"});break;
   default:throw new ArgumentException("UNKNOWN_ACTION");
  }
 }catch(Exception e) when(e is ArgumentException or InvalidOperationException or OverflowException) {
  output.Add(new {status="HOLD"});
 }
}
File.WriteAllText(args[1],JsonSerializer.Serialize(output));
