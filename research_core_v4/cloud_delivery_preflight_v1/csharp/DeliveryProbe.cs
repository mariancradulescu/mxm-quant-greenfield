using System;
using System.Collections.Generic;
using System.Diagnostics;
using cAlgo.API;
using cAlgo.API.Internals;
namespace Mxm.Native.Preflight {
// Derived from immutable original DeliveryProbe. PREPARED ONLY; no deployment authority.
[Robot(TimeZone=TimeZones.UTC, AccessRights=AccessRights.None)]
public class DeliveryProbe:Robot {
 private static readonly DateTime WindowStart=new(2026,10,12,12,0,0,DateTimeKind.Utc);
 private static readonly DateTime Deadline=new(2026,10,12,12,30,0,DateTimeKind.Utc);
 private static readonly string[] Names={"EURUSD","GBPUSD","SpotCrude"};
 private sealed class S {
  public string Name; public Ticks Ticks;
  public long Events,Reloads,Backward,SameTimestamp,ChangedBid,ChangedAsk,Late,Invalid,FreshBoth,MissingChange;
  public double Bid=double.NaN,Ask=double.NaN;
  public DateTime Last=DateTime.MinValue,BidChanged=DateTime.MinValue,AskChanged=DateTime.MinValue;
 }
 private readonly List<S> states=new(); private readonly Stopwatch elapsed=new();
 private bool active,stopping;private DateTime highWater=DateTime.MinValue;private int timerCount;
 private bool WithinScope(bool starting=false){
  var host=DateTime.UtcNow;var server=Server.TimeInUtc;
  if(host<WindowStart||server<WindowStart||host>=Deadline||server>=Deadline)return false;
  if(Math.Abs((host-server).TotalSeconds)>5||host<highWater)return false;
  if(starting&&(host>=WindowStart.AddMinutes(1)||server>=WindowStart.AddMinutes(1)))return false;
  highWater=host;
  return elapsed.Elapsed<TimeSpan.FromMinutes(30);
 }
 private void Halt(){if(stopping)return;stopping=true;active=false;Timer.Stop();Stop();}
 protected override void OnStart(){
  if(!WithinScope(true)){Print("MXM_SCOPE_REFUSED");Halt();return;}
  elapsed.Start();
  foreach(var name in Names){var symbol=Symbols.GetSymbol(name);
   if(symbol==null||symbol.Name!=name||!symbol.MarketHours.IsOpened()){Print("MXM_SYMBOL_SCOPE_UNAVAILABLE");Halt();return;}
   if(!WithinScope()){Halt();return;}
   var s=new S{Name=name,Ticks=MarketData.GetTicks(name)};
   s.Ticks.Tick+=a=>{
    if(!active||!WithinScope()){Halt();return;}
    var q=a.Ticks.LastTick;var t=q.Time;s.Events++;
    if(t<s.Last)s.Backward++;if(t==s.Last)s.SameTimestamp++;
    if(!double.IsNaN(s.Bid)&&q.Bid!=s.Bid){s.ChangedBid++;s.BidChanged=t;}
    if(!double.IsNaN(s.Ask)&&q.Ask!=s.Ask){s.ChangedAsk++;s.AskChanged=t;}
    if((Server.TimeInUtc-t).TotalSeconds>5)s.Late++;
    if(double.IsNaN(q.Bid)||double.IsNaN(q.Ask)||double.IsInfinity(q.Bid)||double.IsInfinity(q.Ask)||!(0<q.Bid&&q.Bid<q.Ask))s.Invalid++;
    else if(s.BidChanged==DateTime.MinValue||s.AskChanged==DateTime.MinValue)s.MissingChange++;
    else {var b=(Server.TimeInUtc-s.BidChanged).TotalSeconds;var aAge=(Server.TimeInUtc-s.AskChanged).TotalSeconds;if(b>=0&&aAge>=0&&b<=5&&aAge<=5)s.FreshBoth++;}
    s.Last=t;s.Bid=q.Bid;s.Ask=q.Ask;
   };
   s.Ticks.Reloaded+=a=>{if(!active||!WithinScope()){Halt();return;}s.Reloads++;s.Last=s.BidChanged=s.AskChanged=DateTime.MinValue;s.Bid=s.Ask=double.NaN;};states.Add(s);
  }
  if(!WithinScope()){Halt();return;}active=true;Timer.Start(TimeSpan.FromSeconds(1));Print("MXM_PREPARED_PROBE_STARTED_PRIVATE_COUNTS_ONLY");
 }
 protected override void OnTimer(){if(!WithinScope()){Halt();return;}if(++timerCount%60==0)Emit();}
 private void Emit(){foreach(var s in states)Print("MXM_TECH {0} events={1} reloads={2} backwards={3} sameTimestamp={4} changedBid={5} changedAsk={6} lagGt5s={7} invalid={8} freshBoth={9} missingChange={10}",s.Name,s.Events,s.Reloads,s.Backward,s.SameTimestamp,s.ChangedBid,s.ChangedAsk,s.Late,s.Invalid,s.FreshBoth,s.MissingChange);}
 protected override void OnException(Exception exception){Print("MXM_EXCEPTION_STOP_NO_DETAILS");Halt();}
 protected override void OnStop(){active=false;Emit();Print("MXM_PROBE_STOPPED");}
}}
