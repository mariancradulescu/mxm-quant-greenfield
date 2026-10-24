using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Research;
static class PathStateDevelopment {
 sealed record Row([property:JsonPropertyName("time_utc")]string Time,
  [property:JsonPropertyName("open")]decimal Open,[property:JsonPropertyName("high")]decimal High,
  [property:JsonPropertyName("low")]decimal Low,[property:JsonPropertyName("close")]decimal Close);
 sealed record Packet(int Ordinal,Row[] Rows);
 sealed record Bucket(int Complete,decimal SumGrossBps);
 sealed record Result(int Ordinal,int Rows,int CandidateSignals,int TrainingLabels,int TrainingCensored,int ReadyForecasts,int Complete,int Censored,
  decimal SumGrossBps,string SignalSha256,string ForecastSha256,string TrainingSha256,string LedgerSha256,Dictionary<int,Bucket> BySegment,Dictionary<string,int> ByWeek);
 static readonly JsonSerializerOptions Options=new(){PropertyNameCaseInsensitive=true,
  NumberHandling=JsonNumberHandling.AllowReadingFromString};
 static void Need([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool ok,string code){if(!ok)throw new ArgumentException("MXM_PATH_STATE_"+code);}
 static DateTime Stamp(string value){
  Need(value.EndsWith("Z",StringComparison.Ordinal),"UTC_REQUIRED");
  var t=DateTimeOffset.Parse(value,CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind).UtcDateTime;
  Need(t>=new DateTime(2026,8,20,0,0,0,DateTimeKind.Utc) && t<new DateTime(2026,9,17,0,0,0,DateTimeKind.Utc) &&
   t.Ticks%TimeSpan.TicksPerMinute==0 && t.Minute%5==0,"DEVELOPMENT_M5_TIME_FENCE");return t;
 }
 static int Segment(DateTime t)=>t<new DateTime(2026,8,27)?1:t<new DateTime(2026,9,3)?2:t<new DateTime(2026,9,10)?3:4;
 static Result Evaluate(Packet packet){
  Need(packet.Ordinal>=1 && packet.Ordinal<=1576 && packet.Rows!=null,"PACKET");
  var kernel=new MxmDelayedPathState();DateTime last=default,pending=default,exitAt=default,entryTime=default;
  int pendingDirection=0,direction=0,entryIndex=-1,candidates=0,completed=0,censored=0;
  decimal entryPrice=0,gross=0;var signature=new StringBuilder();var signals=new StringBuilder();
  var forecasts=new StringBuilder();var training=new StringBuilder();
  var segments=Enumerable.Range(1,4).ToDictionary(x=>x,x=>new Bucket(0,0));var weeks=new Dictionary<string,int>();
  for(int i=0;i<packet.Rows.Length;i++){
   var row=packet.Rows[i];DateTime now=Stamp(row.Time);
   Need(now>last && row.Open>0 && row.Low>0 && row.High>=row.Low &&
    row.Open>=row.Low && row.Open<=row.High && row.Close>=row.Low && row.Close<=row.High,"CHRONOLOGY_OHLC");
   if(last!=default && now-last!=TimeSpan.FromMinutes(5)){
    if(pending!=default || direction!=0)censored++;
    pending=exitAt=default;pendingDirection=direction=0;
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
   int signal=kernel.OnCompletedBar(now,row.Open,row.Close);
   if(kernel.LastMatured is {} matured)training.Append(matured.Origin.ToString(CultureInfo.InvariantCulture)).Append(',')
    .Append(i.ToString(CultureInfo.InvariantCulture)).Append(',').Append(matured.Cell.ToString(CultureInfo.InvariantCulture)).Append(',')
    .Append(matured.GrossBps.ToString("F8",CultureInfo.InvariantCulture)).Append('\n');
   if(kernel.Ready)forecasts.Append(i.ToString(CultureInfo.InvariantCulture)).Append(',')
    .Append(kernel.Cell.ToString(CultureInfo.InvariantCulture)).Append(',')
    .Append(kernel.ForecastBps.ToString("F8",CultureInfo.InvariantCulture)).Append('\n');
   if(now<new DateTime(2026,8,27,0,0,0,DateTimeKind.Utc))signal=0;
   if(signal!=0){candidates++;signals.Append(i.ToString(CultureInfo.InvariantCulture)).Append(',')
    .Append(signal.ToString(CultureInfo.InvariantCulture)).Append('\n');}
   if(direction==0 && pending==default && signal!=0){pending=now.AddMinutes(10);pendingDirection=signal;}
   last=now;
  }
  if(pending!=default || direction!=0)censored++;
  string digest=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(signature.ToString()))).ToLowerInvariant();
  string signalDigest=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(signals.ToString()))).ToLowerInvariant();
  string forecastDigest=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(forecasts.ToString()))).ToLowerInvariant();
  string trainingDigest=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(training.ToString()))).ToLowerInvariant();
  return new(packet.Ordinal,packet.Rows.Length,candidates,kernel.TrainingLabels,kernel.TrainingCensored,kernel.ReadyForecasts,
   completed,censored,gross,signalDigest,forecastDigest,trainingDigest,digest,segments,weeks);
 }
 static void Selftest(){
  DateTime start=new(2026,8,20,0,0,0,DateTimeKind.Utc);
  foreach(int direction in new[]{-1,1}){
   var k=new MxmDelayedPathState();int signal=0;
   for(int i=0;i<120;i++){
    decimal price=100m+direction*i/10m;signal=k.OnCompletedBar(start.AddMinutes(i*5),price,price);
    if(i<32)Need(signal==0,"NO_IMMATURE_LABEL_WARMUP");
   }
   Need(signal==direction && k.TrainingLabels>32 && k.Ready,"MATURED_TARGET_SIGN");
   Need(k.TrainingCensored==14,"BOUNDED_PENDING_TARGETS");
   k.OnCompletedBar(start.AddDays(2),100,100);
   Need(!k.Ready && k.TrainingCensored==14,"GAP_CENSORS_PENDING_NOT_FAKE_LABELS");
   k.Reset();Need(k.CompletedBars==0 && k.TrainingLabels==0 && !k.Ready,"EXPLICIT_RESET_COLD");
  }
  var flat=new MxmDelayedPathState();
  for(int i=0;i<100;i++)Need(flat.OnCompletedBar(start.AddMinutes(5*i),100,100)==0,"FLAT_IS_NOT_BEARISH");
  Need(flat.TrainingLabels==0 && flat.TrainingCensored==0,"NO_FLAT_TARGETS");
  Console.WriteLine("MXM_DELAYED_PATH_STATE_MATURED_TARGET_CAUSAL_WARMUP_GAP_RESET_PASS_ARTIFICIAL_ONLY");
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
  }catch(Exception e){Console.Error.WriteLine("MXM_PATH_STATE_DEVELOPMENT_FAILED_"+e.GetType().Name);return 1;}
 }
}
