using System;
using System.Collections.Generic;
using cAlgo.API;
namespace cAlgo {
[Robot(TimeZone=TimeZones.UTC,AccessRights=AccessRights.None)]
public class LevelPressureObserver:Robot {
 [Parameter("Native symbols")]public string NativeSymbols{get;set;}="";
 readonly Dictionary<string,Bars> histories=new();long lastClock=-1;bool blocked;
 protected override void OnStart(){blocked=Positions.Count>0||PendingOrders.Count>0;foreach(string name in NativeSymbols.Split(',',StringSplitOptions.TrimEntries|StringSplitOptions.RemoveEmptyEntries))histories[name]=MarketData.GetBars(TimeFrame.Minute5,name);Timer.Start(TimeSpan.FromSeconds(1));}
 protected override void OnTimer(){if(blocked||Positions.Count>0||PendingOrders.Count>0)return;long t=new DateTimeOffset(DateTime.SpecifyKind(Server.Time,DateTimeKind.Utc)).ToUnixTimeSeconds();if(t%300!=0||t==lastClock)return;lastClock=t;
  foreach(var kv in histories){var b=kv.Value;int last=-1;for(int i=b.Count-1;i>=0;i--){long x=new DateTimeOffset(DateTime.SpecifyKind(b.OpenTimes[i],DateTimeKind.Utc)).ToUnixTimeSeconds();if(x==t-600){last=i;break;}}if(last<11)continue;var v=new double[12][];bool valid=true;for(int j=0;j<12;j++){int i=last-11+j;long x=new DateTimeOffset(DateTime.SpecifyKind(b.OpenTimes[i],DateTimeKind.Utc)).ToUnixTimeSeconds();if(x!=t-3900+j*300){valid=false;break;}v[j]=new[]{b.OpenPrices[i],b.HighPrices[i],b.LowPrices[i],b.ClosePrices[i]};}if(valid){int side=Pressure.Side(v);/* Observer only: quote-side timing, costs, FX and native execution parity remain uncertified. */}}
 }
 protected override void OnStop(){Timer.Stop();}
}
}
