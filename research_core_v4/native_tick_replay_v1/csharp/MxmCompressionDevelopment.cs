using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Replay;
static class CompressionDevelopment {
 sealed record Row([property:JsonPropertyName("time_utc")]string Time,
  [property:JsonPropertyName("open")]decimal Open,[property:JsonPropertyName("high")]decimal High,
  [property:JsonPropertyName("low")]decimal Low,[property:JsonPropertyName("close")]decimal Close);
 sealed record Packet(int Ordinal,Row[] Rows);
 sealed record Bucket(int Complete,decimal SumGrossBps);
 sealed record Result(int Ordinal,int Rows,int CandidateSignals,int Complete,int Censored,
  decimal SumGrossBps,string LedgerSha256,Dictionary<int,Bucket> BySegment,Dictionary<string,int> ByWeek);
 static readonly JsonSerializerOptions Options=new(){PropertyNameCaseInsensitive=true,
  NumberHandling=JsonNumberHandling.AllowReadingFromString};
 static void Need([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool ok,string code){if(!ok)throw new ArgumentException("MXM_COMPRESSION_"+code);}
 static DateTime Stamp(string value){
  Need(value.EndsWith("Z",StringComparison.Ordinal),"UTC_REQUIRED");
  var t=DateTimeOffset.Parse(value,CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind).UtcDateTime;
  Need(t>=new DateTime(2026,8,20,0,0,0,DateTimeKind.Utc) && t<new DateTime(2026,9,17,0,0,0,DateTimeKind.Utc) &&
   t.Ticks%TimeSpan.TicksPerMinute==0 && t.Minute%5==0,"DEVELOPMENT_M5_TIME_FENCE");return t;
 }
 static int Segment(DateTime t)=>t<new DateTime(2026,8,27)?1:t<new DateTime(2026,9,3)?2:t<new DateTime(2026,9,10)?3:4;
 static Result Evaluate(Packet packet){
  Need(packet.Ordinal>=1 && packet.Ordinal<=1576 && packet.Rows!=null,"PACKET");
  var kernel=new MxmCompressionReleaseKernel();DateTime last=default,pending=default,exitAt=default,entryTime=default;
  int pendingDirection=0,direction=0,entryIndex=-1,candidates=0,completed=0,censored=0;
  decimal entryPrice=0,gross=0;var signature=new StringBuilder();
  var segments=Enumerable.Range(1,4).ToDictionary(x=>x,x=>new Bucket(0,0));var weeks=new Dictionary<string,int>();
  for(int i=0;i<packet.Rows.Length;i++){
   var row=packet.Rows[i];DateTime now=Stamp(row.Time);
   Need(now>last && row.Open>0 && row.Low>0 && row.High>=row.Low &&
    row.Open>=row.Low && row.Open<=row.High && row.Close>=row.Low && row.Close<=row.High,"CHRONOLOGY_OHLC");
   if(last!=default && now-last!=TimeSpan.FromMinutes(5)){
    if(pending!=default || direction!=0)censored++;
    pending=exitAt=default;pendingDirection=direction=0;kernel.Reset();
   }
   if(direction!=0 && now==exitAt){
    decimal move=direction*(row.Open-entryPrice)/entryPrice*10000m;gross+=move;completed++;
    int segment=Segment(entryTime);var old=segments[segment];segments[segment]=new(old.Complete+1,old.SumGrossBps+move);
    string week=ISOWeek.GetYear(entryTime)+"-W"+ISOWeek.GetWeekOfYear(entryTime).ToString("D2",CultureInfo.InvariantCulture);
    weeks[week]=weeks.GetValueOrDefault(week)+1;
    signature.Append(entryIndex.ToString(CultureInfo.InvariantCulture)).Append(',').Append(i.ToString(CultureInfo.InvariantCulture))
     .Append(',').Append(direction.ToString(CultureInfo.InvariantCulture)).Append('\n');
    direction=0;exitAt=default;
   }
   if(pending!=default && now==pending){direction=pendingDirection;entryPrice=row.Open;entryTime=now;
    entryIndex=i;exitAt=now.AddMinutes(60);pending=default;pendingDirection=0;}
   int signal=kernel.OnCompletedBar(row.High,row.Low,row.Close);if(signal!=0)candidates++;
   if(direction==0 && pending==default && signal!=0){pending=now.AddMinutes(10);pendingDirection=signal;}
   last=now;
  }
  if(pending!=default || direction!=0)censored++;
  string digest=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(signature.ToString()))).ToLowerInvariant();
  return new(packet.Ordinal,packet.Rows.Length,candidates,completed,censored,gross,digest,segments,weeks);
 }
 static void Selftest(){
  foreach(int sign in new[]{-1,1}){
   var k=new MxmCompressionReleaseKernel();
   for(int i=0;i<42;i++)Need(k.OnCompletedBar(102m,98m,100m)==0,"WARMUP_NO_SIGNAL");
   for(int i=0;i<6;i++)Need(k.OnCompletedBar(100.1m,99.9m,100m)==0,"COMPRESSION_NO_RELEASE");
   // Prior 12-bar channel still includes earlier broad bars. A small break of
   // the tight last bar is insufficient; a TRUE prior-channel close is needed.
   Need(k.OnCompletedBar(101m,99.9m,100.5m)==0,"NO_LAST_BAR_ONLY_BREAKOUT");
   Need(k.OnCompletedBar(sign>0?103m:100m,sign>0?100m:97m,sign>0?103m:97m)==sign,"PRIOR_RANGE_RELEASE_DIRECTION");
   k.Reset();Need(k.OnCompletedBar(103m,97m,103m)==0,"RESET_COLD");
  }
  var flat=new MxmCompressionReleaseKernel();for(int i=0;i<60;i++)Need(flat.OnCompletedBar(100m,100m,100m)==0,"ZERO_RANGE_HOLD");
  Console.WriteLine("MXM_COMPRESSION_PRIOR_RANGE_CHANNEL_DIRECTION_WARMUP_RESET_PASS_ARTIFICIAL_ONLY");
 }
 public static int Main(string[] args){
  try{
   if(args.SequenceEqual(new[]{"--selftest"})){Selftest();return 0;}
   Need(args.SequenceEqual(new[]{"--development-stream"}),"EXPLICIT_MODE");
   var results=new List<Result>();int prior=0;string? line;
   while((line=Console.ReadLine())!=null){var p=JsonSerializer.Deserialize<Packet>(line,Options)!;
    Need(p.Ordinal==prior+1,"EXACT_FULL_ORDINAL_ORDER");results.Add(Evaluate(p));prior=p.Ordinal;}
   Need(results.Count==1576,"ALL_IDENTITIES_REQUIRED");
   Console.Write(JsonSerializer.Serialize(results));return 0;
  }catch(Exception e){Console.Error.WriteLine("MXM_COMPRESSION_DEVELOPMENT_FAILED_"+e.GetType().Name);return 1;}
 }
}
