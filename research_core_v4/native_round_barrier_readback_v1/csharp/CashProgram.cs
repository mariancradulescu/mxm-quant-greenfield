using System;
using System.Text.Json;
using Mxm.Native;
while(true){var line=Console.ReadLine();if(line==null)break;var j=JsonDocument.Parse(line).RootElement;
double Get(string k)=>j.GetProperty(k).GetDouble();
var value=CashKernel.Scenario(j.GetProperty("direction").GetInt32(),Get("quantity"),Get("entry_bid"),Get("entry_ask"),Get("exit_bid"),Get("exit_ask"),Get("fx_bid"),Get("fx_ask"),Get("fee_bps"),j.GetProperty("quote").GetString()!);
Console.WriteLine(JsonSerializer.Serialize(new {cash_EUR=value}));}
