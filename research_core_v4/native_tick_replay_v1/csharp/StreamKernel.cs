using System;
namespace Mxm.Replay {
// Bounded native-compatible state. Historical side events are not Cloud joint-tick receipts.
public sealed class StreamKernel {
 long b,a,bt=-1,at=-1,bc=-1,ac=-1,last=-1;bool ambiguous;
 public long Events,Changes,Backwards,SameTime,Resets;
 public void Reset(){b=a=0;bt=at=bc=ac=last=-1;ambiguous=false;Resets++;}
 public void Push(string side,long time,long raw){
  if(last>time){Backwards++;Reset();}if(last==time)SameTime++;last=time;Events++;
  if(side=="bid"){if(bt==time&&b!=raw)ambiguous=true;if(bt>=0&&b!=raw){bc=time;Changes++;}b=raw;bt=time;}
  else if(side=="ask"){if(at==time&&a!=raw)ambiguous=true;if(at>=0&&a!=raw){ac=time;Changes++;}a=raw;at=time;}
  else throw new ArgumentException("SIDE");
 }
 public object Snapshot(long now,bool gap){
  string reason=gap?"PAGE_GAP_OR_ERROR":ambiguous?"AMBIGUOUS_SAME_MS":bt<0||at<0?"MISSING_SIDE":bc<0||ac<0?"WARMUP_NO_CHANGED_SIDE":now<bt||now<at?"FUTURE":now-bc>5000||now-ac>5000?"STALE_CHANGED_SIDE":!(0<b&&b<a)?"INVALID_QUOTE":"VALID";
  double mid=reason=="VALID"?(b+a)/200000.0:0,spread=reason=="VALID"?10000*Math.Log((double)a/b):0;
  return new {reason,mid,spread,events=Events,changes=Changes,backwards=Backwards,sameTime=SameTime,resets=Resets};
 }
}
}
