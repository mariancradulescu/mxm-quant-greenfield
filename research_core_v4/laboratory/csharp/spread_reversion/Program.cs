using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Research;
if(args.Length!=2)throw new ArgumentException("SPREAD_EXACT_INPUT_OUTPUT");
static IEnumerable<QuoteRow> Read(string path) {
 foreach(var line in File.ReadLines(path)) {
  using var doc=JsonDocument.Parse(line);var r=doc.RootElement;
  yield return new(r.GetProperty("t").GetInt64(),"GBPUSD",r.GetProperty("side").GetString()!,r.GetProperty("raw").GetInt64());
 }
}
using var model=new MxmSpreadReversion();var source=MxmUsdPairAlignment.Run(Read(args[0]),observer:model.Observe);
var report=new {schema="mxm.csharp.spread-widening-reversion.v1",input_sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[0]))).ToLowerInvariant(),
 assembly_sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(typeof(MxmSpreadReversion).Assembly.Location))).ToLowerInvariant(),
 source,result=model.Finish(),broker_orders=0,capital_replay=false,historical_arrival_order_proven=false,historical_costs_proven=false,
 costs_defaulted_to_zero=false,net_edge_proven=false,hard21_proven=false,native_robot_operational_reception_proven=false};
File.WriteAllText(args[1],JsonSerializer.Serialize(report)+"\n");
