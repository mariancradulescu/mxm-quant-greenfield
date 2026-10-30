using System.Text.Json;
using Mxm.Replay;
if(args.Length!=2)throw new ArgumentException("INPUT_OUTPUT_REQUIRED");
using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));
var root=doc.RootElement;
var policy=new MxmRelativeStrengthPortfolio(root.GetProperty("symbols").EnumerateArray().Select(x=>x.GetString()!));
var decisions=new List<MxmPortfolioTarget>();
foreach(var row in root.GetProperty("bars").EnumerateArray()) {
 var value=policy.Observe(row.GetProperty("symbol").GetString()!,row.GetProperty("end").GetDateTime(),
  row.GetProperty("close").GetDecimal(),row.GetProperty("available").GetDateTime());
 if(value!=null)decisions.Add(value);
}
using var stream=new FileStream(args[1],FileMode.CreateNew);
JsonSerializer.Serialize(stream,decisions);
