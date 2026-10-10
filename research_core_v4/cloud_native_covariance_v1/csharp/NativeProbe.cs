using System;
using System.Collections.Generic;
using cAlgo.API;
using cAlgo.API.Internals;
namespace Mxm.Native {
// Compilation probe ONLY. No order API, HTTP, external storage or external signals.
[Robot(TimeZone=TimeZones.UTC,AccessRights=AccessRights.None)]
public class NativeProbe : Robot {
 [Parameter("Native Symbols",DefaultValue="EURUSD,US500")] public string NativeSymbols {get;set;}
 private sealed class State {
   public Symbol Symbol; public Ticks Ticks;
   public Queue<(long T,double P)> Bid=new(), Ask=new();
   public double LastBid=double.NaN,LastAsk=double.NaN; public long Started,LastEvent=long.MinValue;
   public long BadMs=long.MinValue; public long LastDecision=long.MinValue;
 }
 private readonly List<State> states=new();
 protected override void OnStart() {
   foreach(var name in NativeSymbols.Split(',',StringSplitOptions.RemoveEmptyEntries)) {
     if(states.Count>=32) throw new InvalidOperationException("NATIVE_SYMBOL_CAP");
     var sym=Symbols.GetSymbol(name.Trim());
     var st=new State {Symbol=sym,Ticks=MarketData.GetTicks(sym.Name),Started=UtcMs(Server.TimeInUtc)};
     // Compile-time access evidence only; values are never logged or certified here.
     var bars=MarketData.GetBars(TimeFrame.Minute5,sym.Name);
     _=bars.Count; _=bars.TickVolumes; _=sym.Commission; _=sym.CommissionType;
     _=sym.MinCommission; _=sym.MinCommissionType; _=sym.MinCommissionAsset;
     _=sym.VolumeInUnitsMin; _=sym.VolumeInUnitsStep; _=sym.LotSize;
     _=sym.GetEstimatedMargin(TradeType.Buy,sym.VolumeInUnitsMin);
     _=sym.GetEstimatedMargin(TradeType.Sell,sym.VolumeInUnitsMin);
     _=sym.SwapLong; _=sym.SwapShort; _=sym.SwapCalculationType; _=sym.Swap3DaysRollover;
     _=sym.PnLConversionFeeRate; _=sym.MarketHours.IsOpened(); _=sym.IsTradingEnabled; _=sym.TradingMode;
     _=Account.Equity; _=Account.FreeMargin; _=Account.PreciseLeverage; _=Positions.Count;
     st.Ticks.Tick+=args=>Ingest(st,args.Ticks.LastTick);
     st.Ticks.Reloaded+=args=>Reset(st);
     states.Add(st);
   }
   Timer.Start(TimeSpan.FromSeconds(1));
 }
 private static long UtcMs(DateTime d)=>new DateTimeOffset(DateTime.SpecifyKind(d,DateTimeKind.Utc)).ToUnixTimeMilliseconds();
 private void Reset(State s) {s.Bid.Clear();s.Ask.Clear();s.LastBid=s.LastAsk=double.NaN;s.LastEvent=long.MinValue;s.Started=UtcMs(Server.TimeInUtc);}
 private void Ingest(State s,Tick q) {
   long t=UtcMs(q.Time);
   if(t<s.LastEvent) {Reset(s);return;}
   if((q.Bid!=s.LastBid && s.Bid.Count>0 && LastTime(s.Bid)==t) ||
      (q.Ask!=s.LastAsk && s.Ask.Count>0 && LastTime(s.Ask)==t)) s.BadMs=t;
   if(q.Bid!=s.LastBid) {s.Bid.Enqueue((t,q.Bid));s.LastBid=q.Bid;}
   if(q.Ask!=s.LastAsk) {s.Ask.Enqueue((t,q.Ask));s.LastAsk=q.Ask;}
   s.LastEvent=t;
   while(s.Bid.Count>0 && s.Bid.Peek().T<t-75000) s.Bid.Dequeue();
   while(s.Ask.Count>0 && s.Ask.Peek().T<t-75000) s.Ask.Dequeue();
   if(s.Bid.Count>100000 || s.Ask.Count>100000) Reset(s);
 }
 private static long LastTime(Queue<(long T,double P)> q) {long t=long.MinValue;foreach(var x in q)t=x.T;return t;}
 private static bool At(Queue<(long T,double P)> q,long t,out double p) {
   long ts=long.MinValue;p=double.NaN;
   foreach(var x in q) {if(x.T>t) break;ts=x.T;p=x.P;}
   return ts!=long.MinValue && t-ts<=10000;
 }
 protected override void OnTimer() {
   long now=UtcMs(Server.TimeInUtc),t=now/1000*1000;
   // Delayed callbacks abstain, rather than pretending to execute at a past quote.
   if(now-t>250) return;
   var clock=Server.TimeInUtc;
   if(clock.Second!=0 || clock.Minute!=10 || !(clock.Hour==4 || clock.Hour==8 || clock.Hour==13 || clock.Hour==17) ||
      !(clock.DayOfWeek==DayOfWeek.Friday || clock.DayOfWeek==DayOfWeek.Monday || clock.DayOfWeek==DayOfWeek.Tuesday || clock.DayOfWeek==DayOfWeek.Wednesday)) return;
   foreach(var s in states) {
     if(t-s.Started<75000 || s.BadMs>=t-70000 || s.LastDecision==t) continue;
     s.LastDecision=t;var b=new double[13];var a=new double[13];bool ok=true;
     for(int i=0;i<13;i++) {long at=t-60000+i*5000;if(!At(s.Bid,at,out b[i]) || !At(s.Ask,at,out a[i])) {ok=false;break;}}
     if(ok) {var hypothetical=NativeKernel.Feature(b,a); _=hypothetical;}
   }
 }
}}
