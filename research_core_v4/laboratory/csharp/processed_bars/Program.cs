using System.Text.Json;
using Mxm.Replay;
var data=JsonDocument.Parse(File.ReadAllText(args[0])).RootElement;
var names=data.GetProperty("symbols").EnumerateArray().Select(x=>x.GetString()!).ToArray();
var sequencer=new MxmPortfolioSequencer(names);
var kernels=names.ToDictionary(x=>x,x=>new MxmDecisionKernel());
var output=new List<object>();
foreach(var a in data.GetProperty("bars").EnumerateArray()) {
 string symbol=a.GetProperty("symbol").GetString()!;
 var time=a.GetProperty("utc").GetDateTime();
 bool accepted=sequencer.TryEnter(symbol,time,5,out bool contiguous,out var reason);
 if(accepted) {
  try {
   contiguous=contiguous && a.GetProperty("platform_adjacent").GetBoolean();
   if(!contiguous)kernels[symbol].Reset();
   int decision=kernels[symbol].OnCompletedBar(a.GetProperty("close").GetDecimal());
   output.Add(new {accepted,contiguous,count=kernels[symbol].CompletedBars,decision,reason});
  } finally {sequencer.Exit();}
 } else output.Add(new {accepted,contiguous,count=kernels.TryGetValue(symbol,out var kernel)?kernel.CompletedBars:0,decision=0,reason});
}
File.WriteAllText(args[1],JsonSerializer.Serialize(output));
