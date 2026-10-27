using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Replay;
if(args.Length!=2)throw new ArgumentException("OBSERVATION_EXACT_ARGUMENTS");
using var input=JsonDocument.Parse(File.ReadAllBytes(args[0]));
var root=input.RootElement;
var views=new List<MxmBookObservationView>();
void Run<T>(MxmBookObservation<T> state,Func<JsonElement,T> price) where T:struct {
 foreach(var a in root.GetProperty("actions").EnumerateArray()) {
  long now=a.GetProperty("now").GetInt64();
  switch(a.GetProperty("op").GetString()) {
   case "begin":state.BeginEpoch(now);break;
   case "end":state.EndEpoch(now);break;
   case "transport":state.ReportTransport(Enum.Parse<MxmReportedTransport>(a.GetProperty("status").GetString()!),now);break;
   case "observe":
    T? Field(string name)=>a.GetProperty(name).ValueKind==JsonValueKind.Null?null:price(a.GetProperty(name));
    long? server=a.GetProperty("server").ValueKind==JsonValueKind.Null?null:a.GetProperty("server").GetInt64();
    state.Observe(Field("bid"),Field("ask"),now,a.GetProperty("utc").GetInt64(),server);break;
   case "view":break;
   default:throw new ArgumentException("OBSERVATION_UNKNOWN_OPERATION");
  }
  views.Add(state.Snapshot(now));
 }
}
try {
 switch(root.GetProperty("origin").GetString()) {
  case "raw":Run(MxmBookObservations.RawFields(),x=>x.GetDecimal());break;
  case "native":Run(MxmBookObservations.NativeSnapshots(),x=>x.GetDouble());break;
  default:throw new ArgumentException("OBSERVATION_UNKNOWN_ORIGIN");
 }
 var options=new JsonSerializerOptions();options.Converters.Add(new JsonStringEnumConverter());
 File.WriteAllText(args[1],JsonSerializer.Serialize(views,options)+"\n");
}catch(Exception e){Console.Error.WriteLine("MXM_OBSERVATION_FAILED_"+e.GetType().Name);Environment.ExitCode=2;}
