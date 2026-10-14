using System;
using System.Collections.Generic;
using System.Linq;
public record Ticket(string Symbol,int Side,double RiskEur,double MarginEur,string Label,bool StopKnown);
public static class EconomicContract {
 public static long? LatestClosed(long now,long[] openTimes){var closed=openTimes.Where(x=>x+305<=now).ToArray();return closed.Length==0?null:closed.Max();}
 public static bool CanAdmit(double equity,IEnumerable<Ticket> open,Ticket proposed){var all=open.Append(proposed).ToArray();if(equity<=0||all.Any(x=>!x.StopKnown||x.RiskEur<0||x.MarginEur<0||x.Label!="MXM_ECONOMIC"))return false;double risk=all.Sum(x=>x.RiskEur),margin=all.Sum(x=>x.MarginEur);return risk<=.01*equity&&margin<=.40*equity&&equity-margin>=.60*equity;}
 public static bool RestartReconciled(IEnumerable<Ticket> positions)=>positions.All(x=>x.StopKnown&&x.Label=="MXM_ECONOMIC");
}
