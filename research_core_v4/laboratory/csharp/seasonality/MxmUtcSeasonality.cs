using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Research;
/// <summary>Unqualified research law. Completed UTC H1 profiles only; no broker path.</summary>
public sealed class MxmUtcSeasonality {
 readonly Queue<decimal>[] slots=Enumerable.Range(0,24).Select(_=>new Queue<decimal>()).ToArray();
 DateTime last=default;
 int partialCount;
 decimal secondOpen;
 public int CompletedHours {get;private set;}
 public int ReadyForecasts {get;private set;}
 public int OnCompletedBar(DateTime time,decimal open,decimal high,decimal low,decimal close) {
  if(time.Kind!=DateTimeKind.Utc || time.Ticks%TimeSpan.TicksPerMinute!=0 || time.Minute%5!=0 ||
   time<=last || open<=0 || low<=0 || high<low || open<low || open>high || close<low || close>high)
   throw new ArgumentException("INVALID_SEASONALITY_COMPLETED_BAR");
  if(last!=default && time-last!=TimeSpan.FromMinutes(5))partialCount=0;
  if(time.Minute==0)partialCount=1;
  else if(partialCount>0)partialCount++;
  if(time.Minute==5 && partialCount==2)secondOpen=open;
  last=time;
  if(time.Minute!=55 || partialCount!=12)return 0;
  // The sample's final M5 open is known at this completed-hour boundary. It belongs to THIS elapsed hour,
  // whereas the prediction concerns the NEXT hour's slot (never the current outcome).
  decimal sample=decimal.Round((open-secondOpen)/secondOpen*10000m,8,MidpointRounding.AwayFromZero);
  var elapsed=slots[time.Hour];elapsed.Enqueue(sample);if(elapsed.Count>5)elapsed.Dequeue();
  CompletedHours++;
  var upcoming=slots[(time.Hour+1)%24];
  if(upcoming.Count<5)return 0;
  ReadyForecasts++;
  decimal sum=upcoming.Sum();return sum>50m?1:sum< -50m?-1:0;
 }
 public void Reset() {
  foreach(var slot in slots)slot.Clear();last=default;partialCount=0;secondOpen=0;
  CompletedHours=ReadyForecasts=0;
 }
}
