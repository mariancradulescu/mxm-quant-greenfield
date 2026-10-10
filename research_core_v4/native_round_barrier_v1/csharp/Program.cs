using System;
using System.Text.Json;
using Mxm.Native;
while(true) {var line=Console.ReadLine();if(line==null)break;var j=JsonDocument.Parse(line).RootElement;
 var v=RoundKernel.Feature(j.GetProperty("bid").GetDouble(),j.GetProperty("ask").GetDouble(),j.GetProperty("digits").GetInt32());
 Console.WriteLine(JsonSerializer.Serialize(new {direction=v.Direction,level=v.Level,distance=v.Distance,headroom_bps=v.Headroom,stop_distance=v.StopDistance,reason=v.Reason}));}
