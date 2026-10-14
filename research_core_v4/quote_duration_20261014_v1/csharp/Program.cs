using System;
using System.IO;
using System.Text.Json;
using Mxm.Duration;
class Program {
 static void Main(string[] args){
  using var input=File.OpenText(args[0]);using var output=new StreamWriter(args[1]);string line;
  while((line=input.ReadLine())!=null){using var d=JsonDocument.Parse(line);var r=d.RootElement;
   long[][] Rows(string key)=>JsonSerializer.Deserialize<long[][]>(r.GetProperty(key).GetRawText());
   output.WriteLine(JsonSerializer.Serialize(TimingKernel.Compute(Rows("bids"),Rows("asks"),r.GetProperty("t").GetInt64(),r.GetProperty("has_more").GetBoolean())));
  }
 }
}
