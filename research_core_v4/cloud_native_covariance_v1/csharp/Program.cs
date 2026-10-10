using System;
using System.Text.Json;
using Mxm.Native;
// Private authentic samples enter on stdin; output is consumed privately by Python.
while(true) {
    var line=Console.ReadLine(); if(line==null) break;
    var j=JsonDocument.Parse(line).RootElement;
    var b=JsonSerializer.Deserialize<double[]>(j.GetProperty("bids"));
    var a=JsonSerializer.Deserialize<double[]>(j.GetProperty("asks"));
    var v=NativeKernel.Feature(b!,a!);
    Console.WriteLine(JsonSerializer.Serialize(new {direction=v.Direction,correlation=v.Correlation,reason=v.Reason}));
}
