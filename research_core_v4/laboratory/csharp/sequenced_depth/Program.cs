using System.Text.Json;
using Mxm.Replay;
using var input=JsonDocument.Parse(File.ReadAllBytes(args[0]));
var book=new MxmSequencedDepthBook(1);var output=new List<object>();
foreach(var a in input.RootElement.EnumerateArray()){
 long now=a.GetProperty("now").GetInt64();string op=a.GetProperty("op").GetString()!;
 try{
  long Seq()=>a.GetProperty("seq").GetInt64();
  long? Sent()=>a.TryGetProperty("sent",out var sent)&&sent.ValueKind!=JsonValueKind.Null?sent.GetInt64():null;
  switch(op){
   case "begin":book.BeginVerifiedSession(Seq(),now);break;
   case "advance":book.Advance(Seq(),now);break;
   case "snapshot":book.Snapshot(Seq(),now,a.GetProperty("symbol").GetInt64(),JsonSerializer.Deserialize<MxmDepthEntry[]>(a.GetProperty("entries").GetRawText())!,Sent());break;
   case "delta":book.Incremental(Seq(),now,a.GetProperty("symbol").GetInt64(),JsonSerializer.Deserialize<MxmDepthUpdate[]>(a.GetProperty("updates").GetRawText())!,Sent());break;
   case "end":book.End(now);break;
   case "read":output.Add(new {status="VIEW",view=book.Read(now)});break;
   default:throw new ArgumentException("UNKNOWN_OP");
  }
 }catch(Exception e) when(e is ArgumentException or InvalidOperationException or OverflowException){output.Add(new {status="HOLD"});}
}
File.WriteAllText(args[1],JsonSerializer.Serialize(output,new JsonSerializerOptions {Converters={new System.Text.Json.Serialization.JsonStringEnumConverter()}}));
