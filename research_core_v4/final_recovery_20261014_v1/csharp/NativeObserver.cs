using System;
using System.Collections.Generic;
using cAlgo.API;
using cAlgo.API.Internals;
namespace cAlgo {
[Robot(TimeZone=TimeZones.UTC,AccessRights=AccessRights.None)]
public class NativeOrderObserver:Robot {
 Bars bars;bool reconciliationBlocked;
 protected override void OnStart(){bars=MarketData.GetBars(TimeFrame.Minute5,SymbolName);reconciliationBlocked=Positions.Count>0;Timer.Start(TimeSpan.FromSeconds(1));}
 protected override void OnTimer(){if(reconciliationBlocked||Positions.Count>0)return;long t=new DateTimeOffset(DateTime.SpecifyKind(Server.Time,DateTimeKind.Utc)).ToUnixTimeSeconds();if(t%300!=0)return;var rr=new List<double>();int last=-1;for(int i=bars.Count-1;i>=0;i--){long b=new DateTimeOffset(DateTime.SpecifyKind(bars.OpenTimes[i],DateTimeKind.Utc)).ToUnixTimeSeconds();if(b+305<=t){last=i;break;}}if(last<11)return;for(int i=last-11;i<=last;i++){long b=new DateTimeOffset(DateTime.SpecifyKind(bars.OpenTimes[i],DateTimeKind.Utc)).ToUnixTimeSeconds();if(b!=t-3900+(i-(last-11))*300||bars.OpenPrices[i]<=0||bars.ClosePrices[i]<=0)return;rr.Add(Math.Log(bars.ClosePrices[i]/bars.OpenPrices[i]));}int side=OrderKernel.Side(rr.ToArray());/* Observer only. Pure native closed-bar information. No orders or position mutation. */}
 protected override void OnStop(){Timer.Stop();}
}
}
