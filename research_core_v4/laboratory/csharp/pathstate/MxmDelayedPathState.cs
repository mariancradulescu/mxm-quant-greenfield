using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Research {
public sealed record MxmMaturedPathLabel(int Origin,int Cell,decimal GrossBps);
/// <summary>Unqualified finite DEVELOPMENT learner. Eight three-return sign contexts;
/// each target is delayed open-to-open 60m and enters memory only at its observed exit.
/// No future labels, fitted constants, trading API, fees or capital claims.</summary>
public sealed class MxmDelayedPathState {
 public const int Cells=8,Window=32,Minimum=16,Prior=16;
 public const decimal ThresholdBps=10m;
 sealed class Pending {
  public int Origin,Cell;public DateTime Entry,Exit;public decimal? Price;
 }
 readonly Queue<decimal> closes=new();
 readonly Queue<decimal>[] labels=Enumerable.Range(0,Cells).Select(_=>new Queue<decimal>()).ToArray();
 readonly List<Pending> pending=new();
 DateTime previous;
 int discarded;
 public int CompletedBars {get;private set;}
 public int TrainingLabels {get;private set;}
 public int TrainingCensored=>discarded+pending.Count;
 public int ReadyForecasts {get;private set;}
 public bool Ready {get;private set;}
 public int Cell {get;private set;}=-1;
 public decimal ForecastBps {get;private set;}
 public MxmMaturedPathLabel? LastMatured {get;private set;}
 public void Reset(){
  closes.Clear();pending.Clear();foreach(var cell in labels)cell.Clear();
  previous=default;discarded=CompletedBars=TrainingLabels=ReadyForecasts=0;
  Ready=false;Cell=-1;ForecastBps=0;LastMatured=null;
 }
 public int OnCompletedBar(DateTime openUtc,decimal open,decimal close){
  if(openUtc.Kind!=DateTimeKind.Utc || openUtc==default || open<=0 || close<=0 ||
     (previous!=default && openUtc<=previous))throw new ArgumentException("INVALID_PATH_STATE_BAR");
  Ready=false;Cell=-1;ForecastBps=0;LastMatured=null;
  if(previous!=default && openUtc-previous!=TimeSpan.FromMinutes(5)){
   // Never train across a missing bar/session jump. Legitimately matured
   // historical cells survive; incomplete future targets and close tail do not.
   discarded+=pending.Count;pending.Clear();closes.Clear();
  }
  foreach(var label in pending){
   if(openUtc==label.Entry)label.Price=open;
   if(openUtc==label.Exit){
    if(label.Price==null)throw new InvalidOperationException("MISSING_TARGET_ENTRY");
    decimal y=Math.Round((open-label.Price.Value)/label.Price.Value*10000m,8,MidpointRounding.AwayFromZero);
    var cell=labels[label.Cell];cell.Enqueue(y);if(cell.Count>Window)cell.Dequeue();
    TrainingLabels++;LastMatured=new(label.Origin,label.Cell,y);
   }
  }
  pending.RemoveAll(x=>x.Exit<=openUtc);
  closes.Enqueue(close);if(closes.Count>4)closes.Dequeue();
  int index=CompletedBars++;previous=openUtc;
  if(closes.Count!=4)return 0;
  var tail=closes.ToArray();int state=0;
  for(int i=1;i<4;i++){
   if(tail[i]==tail[i-1])return 0; // Zero return is not silently coded as bearish.
   state=state*2+(tail[i]>tail[i-1]?1:0);
  }
  Cell=state;
  pending.Add(new Pending{Origin=index,Cell=state,Entry=openUtc.AddMinutes(10),Exit=openUtc.AddMinutes(70)});
  var memory=labels[state];
  if(memory.Count<Minimum)return 0;
  Ready=true;ReadyForecasts++;
  ForecastBps=Math.Round(memory.Sum()/(memory.Count+Prior),8,MidpointRounding.AwayFromZero);
  return ForecastBps>ThresholdBps?1:ForecastBps<-ThresholdBps?-1:0;
 }
}
}
