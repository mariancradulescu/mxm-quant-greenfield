using Mxm.Replay;
namespace Mxm.Research;
public sealed record IntrinsicState(string Day,int Trend,decimal Extreme,int Target,DateTime ExitDue,long Sequence,DateTime LastUtc);
// Fixed intrinsic-time continuation: five-pip reversal events, never fitted bars.
public sealed class IntrinsicKernel {
 public IntrinsicState State {get;private set;}=new("",0,0m,0,default,0,default);
 readonly string identity;
 public IntrinsicKernel(string policy,IntrinsicState? saved=null){
  identity=policy;if(saved!=null){
   if(saved.Trend is <-1 or >1 || saved.Target is <-1 or >1 || saved.Extreme<0 || saved.Sequence<0 ||
    (saved.LastUtc!=default && saved.LastUtc.Kind!=DateTimeKind.Utc) ||
    (saved.Target!=0 && (saved.ExitDue.Kind!=DateTimeKind.Utc || saved.ExitDue==default)))throw new ArgumentException("INTRINSIC_STATE");
   State=saved;
  }
 }
 public void Invalidate(DateTime utc){State=State with {Trend=0,Extreme=0,Target=0,ExitDue=default,LastUtc=utc};}
 public MxmExplicitDecision? Quote(DateTime utc,decimal mid){
  var s=State;
  if(utc.Kind!=DateTimeKind.Utc || utc<=s.LastUtc || mid<=0)throw new ArgumentException("INTRINSIC_QUOTE_CLOCK");
  string day=utc.ToString("yyyyMMdd",System.Globalization.CultureInfo.InvariantCulture);
  if(day!=s.Day)s=s with {Day=day,Trend=0,Extreme=0};
  s=s with {LastUtc=utc};State=s;
  MxmExplicitDecision Emit(int target){
   State=s with {Target=target,ExitDue=target==0?default:utc.AddMinutes(5),Sequence=s.Sequence+1};
   return new(utc,"EURUSD",State.Sequence,target,utc.AddMilliseconds(250),utc.AddSeconds(5),identity);
  }
  if(utc.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday || utc.TimeOfDay<TimeSpan.FromHours(7) || utc.TimeOfDay>=new TimeSpan(15,55,0)){
   s=s with {Trend=0,Extreme=0};State=s;
   return s.Target!=0?Emit(0):null;
  }
  if(s.Target!=0 && utc>=s.ExitDue)return Emit(0);
  if(s.Extreme==0){State=s with {Extreme=mid};return null;}
  int next=0;
  if(s.Trend==0 && Math.Abs(mid-s.Extreme)>=.0005m)next=Math.Sign(mid-s.Extreme);
  else if(s.Trend>0 && s.Extreme-mid>=.0005m)next=-1;
  else if(s.Trend<0 && mid-s.Extreme>=.0005m)next=1;
  if(next!=0){s=s with {Trend=next,Extreme=mid};State=s;return Emit(next);}
  State=s with {Extreme=s.Trend>0?Math.Max(s.Extreme,mid):s.Trend<0?Math.Min(s.Extreme,mid):s.Extreme};
  return null;
 }
}
