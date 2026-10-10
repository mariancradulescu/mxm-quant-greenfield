using System;
using System.Collections.Generic;
using cAlgo.API;
using cAlgo.API.Internals;
namespace Mxm.Native {
[Robot(TimeZone=TimeZones.UTC,AccessRights=AccessRights.None)]
public class RoundProbe:Robot {
 [Parameter("Panel",DefaultValue="EURUSD")] public string Panel {get;set;}
 private sealed class S {public Symbol Symbol;public Ticks Ticks;public Queue<(long T,double P)> Bid=new(),Ask=new();public Queue<long> BadTimes=new();public double B=double.NaN,A=double.NaN;public long Last=long.MinValue,Bad=long.MinValue,BT=long.MinValue,AT=long.MinValue,Start,Decision=long.MinValue;}
 private readonly List<S> states=new();
 private static long Ms(DateTime d)=>new DateTimeOffset(DateTime.SpecifyKind(d,DateTimeKind.Utc)).ToUnixTimeMilliseconds();
 protected override void OnStart(){foreach(var name in (Panel+",EURUSD").Split(',',StringSplitOptions.RemoveEmptyEntries)) {
  if(states.Exists(x=>x.Symbol.Name==name.Trim()))continue;if(states.Count>=5)throw new InvalidOperationException("PANEL_CAP");
  var sym=Symbols.GetSymbol(name.Trim());var s=new S{Symbol=sym,Ticks=MarketData.GetTicks(sym.Name),Start=Ms(Server.TimeInUtc)};
  _=sym.Digits;_=sym.VolumeInUnitsMin;_=sym.VolumeInUnitsStep;_=sym.Commission;_=sym.GetEstimatedMargin(TradeType.Buy,sym.VolumeInUnitsMin);_=Account.FreeMargin;_=Positions.Count;
  s.Ticks.Tick+=a=>Ingest(s,a.Ticks.LastTick);s.Ticks.Reloaded+=a=>Reset(s);states.Add(s);
 }Timer.Start(TimeSpan.FromSeconds(1));}
 private void Reset(S s){s.Bid.Clear();s.Ask.Clear();s.B=s.A=double.NaN;s.BadTimes.Clear();s.Last=s.Bad=s.BT=s.AT=long.MinValue;s.Start=Ms(Server.TimeInUtc);}
 private static long Tail(Queue<(long T,double P)> q){long t=long.MinValue;foreach(var x in q)t=x.T;return t;}
 private void Ingest(S s,Tick q){long t=Ms(q.Time);if(t<s.Last){Reset(s);return;}
  if((q.Bid!=s.B && s.Bid.Count>0 && s.BT==t)||(q.Ask!=s.A && s.Ask.Count>0 && s.AT==t)){s.Bad=t;s.BadTimes.Enqueue(t);}
  // First event seeds each side; it cannot manufacture a changed-price timestamp.
  if(q.Bid!=s.B){if(!double.IsNaN(s.B))s.Bid.Enqueue((t,q.Bid));s.B=q.Bid;s.BT=t;}
  if(q.Ask!=s.A){if(!double.IsNaN(s.A))s.Ask.Enqueue((t,q.Ask));s.A=q.Ask;s.AT=t;}
  s.Last=t;while(s.BadTimes.Count>0 && s.BadTimes.Peek()<t-3700000)s.BadTimes.Dequeue();foreach(var z in new[]{s.Bid,s.Ask}){while(z.Count>0 && z.Peek().T<t-3700000)z.Dequeue();if(z.Count>250000){Reset(s);return;}}}
 private static bool At(Queue<(long T,double P)> q,long t,out double v){long ts=long.MinValue;int count=0;v=double.NaN;foreach(var x in q){if(x.T>t)break;ts=x.T;v=x.P;if(x.T>=t-70000)count++;}return count>=2 && ts!=long.MinValue && t-ts<=5000;}
 private static bool BadAt(S s,long t){foreach(long x in s.BadTimes)if(x>=t-70000 && x<=t)return true;return false;}
 protected override void OnTimer(){var clock=Server.TimeInUtc;long now=Ms(clock),t=now/1000*1000;
  if(now-t>250 || clock.Second!=0 || clock.Minute!=10 || clock.Hour<4 || clock.Hour>18 || clock.Hour%2!=0 || clock.DayOfWeek==DayOfWeek.Saturday || clock.DayOfWeek==DayOfWeek.Sunday)return;
  var fx=states.Find(x=>x.Symbol.Name=="EURUSD");if(fx==null || BadAt(fx,t) || !At(fx.Bid,t,out double eb)||!At(fx.Ask,t,out double ea)||!(0<eb && eb<ea))return;
  foreach(var s in states){if(t-s.Start<3700000 || s.Decision==t || (BadAt(s,t)||BadAt(s,t-3600000)))continue;s.Decision=t;
   if(!At(s.Bid,t,out double b)||!At(s.Ask,t,out double a)||!At(s.Bid,t-3600000,out double pb)||!At(s.Ask,t-3600000,out double pa))continue;
   var native=RoundKernel.Feature(b,a,s.Symbol.Digits);int baseline=Math.Sign(b+a-pb-pa);_=native;_=baseline;
   // Compatibility probe only. No fee approval, portfolio allocation, deployment or order method.
  }}
}}
