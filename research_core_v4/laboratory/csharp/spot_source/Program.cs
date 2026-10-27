using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Replay;
using Mxm.SpotSource;
try {
 if(args.Length==1 && args[0]=="--self-test") {
  int checks=0;
  double[] values={double.NaN,double.NegativeInfinity,double.PositiveInfinity,-1d,0d,double.Epsilon,1d,1.00001d,100d,double.MaxValue};
  foreach(var bid in values)foreach(var ask in values){
   bool old=double.IsFinite(bid)&&double.IsFinite(ask)&&bid>0&&ask>=bid;
   if(MxmBookShape.NonCrossed(MxmBookShape.ClassifyNative(bid,ask))!=old)throw new Exception("NATIVE_GEOMETRY_PARITY");checks++;
  }
  var examples=new[]{(Bid:(decimal?)null,Ask:(decimal?)100,Want:MxmBookShapeKind.Missing),
    (Bid:(decimal?)0,Ask:(decimal?)1,Want:MxmBookShapeKind.Invalid),
    (Bid:(decimal?)102,Ask:(decimal?)100,Want:MxmBookShapeKind.Crossed),
    (Bid:(decimal?)100,Ask:(decimal?)100,Want:MxmBookShapeKind.Locked),
    (Bid:(decimal?)100,Ask:(decimal?)102,Want:MxmBookShapeKind.Positive)};
  foreach(var e in examples){if(MxmBookShape.Classify(e.Bid,e.Ask)!=e.Want)throw new Exception("DECIMAL_GEOMETRY");checks++;}
  if(MxmBookShape.StrictlyPositive(MxmBookShapeKind.Locked)||!MxmBookShape.NonCrossed(MxmBookShapeKind.Locked))throw new Exception("CALLER_POLICY_SEPARATION");checks++;
  Console.WriteLine(JsonSerializer.Serialize(new {checks,native_predicate_preserved=true,caller_policy_unchanged=true,broker_orders=0,economic_model_executed=false}));
 }else {
  if(args.Length!=2)throw new ArgumentException("SPOT_SOURCE_EXACT_ARGUMENTS");
  var bytes=File.ReadAllBytes(args[0]);if(bytes.Length>5000000)throw new ArgumentException("SPOT_SOURCE_INPUT_CAP");
  using var profile=new SourceProfile();
  foreach(var line in File.ReadLines(args[0])) {
   if(Encoding.UTF8.GetByteCount(line)>512)throw new ArgumentException("SPOT_SOURCE_ROW_CAP");
   using var doc=JsonDocument.Parse(line);var e=doc.RootElement;
   string[] names={"symbol","sequence","arrival_ns","received_ms","server_ms","bid","ask"};
   if(e.ValueKind!=JsonValueKind.Object || !e.EnumerateObject().Select(x=>x.Name).OrderBy(x=>x).SequenceEqual(names.OrderBy(x=>x)))throw new ArgumentException("SPOT_SOURCE_EXACT_ROW_FIELDS");
   long? NullableLong(string key)=>e.GetProperty(key).ValueKind==JsonValueKind.Null?null:e.GetProperty(key).GetInt64();
   decimal? Price(string key)=>e.GetProperty(key).ValueKind==JsonValueKind.Null?null:e.GetProperty(key).GetDecimal();
   profile.Observe(new SourceEvent(e.GetProperty("symbol").GetInt32(),e.GetProperty("sequence").GetInt64(),
    e.GetProperty("arrival_ns").GetInt64(),e.GetProperty("received_ms").GetInt64(),NullableLong("server_ms"),Price("bid"),Price("ask")));
  }
  var report=new {schema="mxm.csharp.spot-source-program.v1",input_sha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
   assembly_sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(typeof(SourceProfile).Assembly.Location))).ToLowerInvariant(),
   source_commit=Environment.GetEnvironmentVariable("GITHUB_SHA"),result=profile.Finish()};
  File.WriteAllText(args[1],JsonSerializer.Serialize(report)+"\n");
 }
}catch(Exception e){Console.Error.WriteLine("MXM_SPOT_SOURCE_FAILED_"+e.GetType().Name);Environment.ExitCode=2;}
