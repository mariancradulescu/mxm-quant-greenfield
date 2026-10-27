using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Replay;
namespace Mxm.SpotSource {
public sealed record SourceEvent(int Symbol,long Sequence,long ArrivalNs,long ReceivedMs,long? ServerMs,decimal? Bid,decimal? Ask);
public sealed class SourceProfile:IDisposable {
 const long AgeMs=5000,AgeNs=5000000000L,SpanNs=300000000000L;
 sealed record Side(decimal Price,long Arrival,long? Server);
 sealed class Book {
  public bool First=true,PreviousHealthy;
  public Side? Bid,Ask;
  public long? ServerMax,Start,End,PreviousArrival;
  public long Events,Healthy,Unavailable,Stretches,LongStretches,Longest,BidUpdates,AskUpdates;
  public long SameBid,SameAsk,ServerFailures,Gaps,HealthyGaps,LockedBoth,CrossedBoth;
  public Dictionary<string,long> Reasons=new(),Shapes=new(),Fields=new();
 }
 readonly SortedDictionary<int,Book> books=new(){{1,new()},{2,new()},{250,new()}};
 readonly IncrementalHash states=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
 long sequence,arrival=-1,received=-1;bool finished;
 static void Need(bool yes,string why){if(!yes)throw new ArgumentException("SPOT_SOURCE_"+why);}
 static void Count(Dictionary<string,long> target,string key){target[key]=target.GetValueOrDefault(key)+1;}
 static bool Fresh(long now,long old,long age)=>now>=old && (decimal)now-old<=age;
 static void Close(Book b){
  if(b.Start.HasValue){long span=checked(b.End!.Value-b.Start.Value);b.Stretches++;if(span>=SpanNs)b.LongStretches++;b.Longest=Math.Max(b.Longest,span);}
  b.Start=b.End=null;
 }
 public void Observe(SourceEvent e){
  Need(!finished && books.ContainsKey(e.Symbol) && e.Sequence>sequence && e.ArrivalNs>=arrival && e.ReceivedMs>=received &&
    (!e.Bid.HasValue || e.Bid>=0m && e.Bid==decimal.Truncate(e.Bid.Value)) &&
    (!e.Ask.HasValue || e.Ask>=0m && e.Ask==decimal.Truncate(e.Ask.Value)),"EVENT_SCOPE_OR_CLOCK");
  sequence=e.Sequence;arrival=e.ArrivalNs;received=e.ReceivedMs;
  var b=books[e.Symbol];b.Events++;var reasons=new HashSet<string>();bool initial=b.First;b.First=false;
  if(initial)reasons.Add("INITIAL_SNAPSHOT_NOT_FRESHNESS_PROOF");
  if(!e.Bid.HasValue&&!e.Ask.HasValue)reasons.Add("NO_PRICE_SIDE");
  bool serverOk=e.ServerMs.HasValue && Fresh(e.ReceivedMs,e.ServerMs.Value,AgeMs) && (!b.ServerMax.HasValue||e.ServerMs>=b.ServerMax);
  if(!serverOk){reasons.Add("SERVER_CLOCK_MISSING_STALE_FUTURE_OR_REVERSED");b.ServerFailures++;}
  if(e.ServerMs.HasValue)b.ServerMax=b.ServerMax.HasValue?Math.Max(b.ServerMax.Value,e.ServerMs.Value):e.ServerMs;
  string field=e.Bid.HasValue?(e.Ask.HasValue?"both":"bid_only"):(e.Ask.HasValue?"ask_only":"neither");Count(b.Fields,field);
  bool gap=b.PreviousArrival.HasValue && !Fresh(e.ArrivalNs,b.PreviousArrival.Value,AgeNs);
  if(gap)b.Gaps++;
  if(e.Bid.HasValue){if(b.Bid?.Price==e.Bid)b.SameBid++;b.Bid=new(e.Bid.Value,e.ArrivalNs,serverOk&&!initial?e.ServerMs:null);b.BidUpdates++;}
  if(e.Ask.HasValue){if(b.Ask?.Price==e.Ask)b.SameAsk++;b.Ask=new(e.Ask.Value,e.ArrivalNs,serverOk&&!initial?e.ServerMs:null);b.AskUpdates++;}
  var shape=MxmBookShape.Classify(b.Bid?.Price,b.Ask?.Price);string shapeName=shape.ToString().ToUpperInvariant();Count(b.Shapes,shapeName);
  if(shape==MxmBookShapeKind.Locked && field=="both")b.LockedBoth++;
  if(shape==MxmBookShapeKind.Crossed && field=="both")b.CrossedBoth++;
  if(b.Bid==null||b.Ask==null)reasons.Add("MISSING_SIDE");
  else {
   foreach(var side in new[]{b.Bid!,b.Ask!}){
    if(side.Price<=0)reasons.Add("NONPOSITIVE_SIDE");
    if(!side.Server.HasValue||!Fresh(e.ReceivedMs,side.Server.Value,AgeMs)||!Fresh(e.ArrivalNs,side.Arrival,AgeNs))reasons.Add("UNVERIFIED_OR_STALE_SIDE");
   }
   if(b.Ask.Price<=b.Bid.Price)reasons.Add("LOCKED_OR_CROSSED_BOOK");
  }
  bool healthy=reasons.Count==0 && MxmBookShape.StrictlyPositive(shape);
  if(healthy && b.PreviousHealthy && gap)b.HealthyGaps++;
  if(healthy){
   b.Healthy++;
   if(!b.Start.HasValue||!Fresh(e.ArrivalNs,b.End!.Value,AgeNs)){Close(b);b.Start=e.ArrivalNs;}
   b.End=e.ArrivalNs;
  }else{b.Unavailable++;foreach(var reason in reasons)Count(b.Reasons,reason);Close(b);}
  b.PreviousHealthy=healthy;b.PreviousArrival=e.ArrivalNs;
  // Every event disposition, in original receipt order; no private prices/times.
  states.AppendData(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(new object[]{e.Symbol,e.Sequence,shapeName,healthy,initial,gap,field})+"\n"));
 }
 public object Finish(){
  Need(!finished,"FINALIZED_TWICE");finished=true;
  var profile=new SortedDictionary<string,object>();var causes=new SortedDictionary<string,object>();
  foreach(var pair in books){var b=pair.Value;Close(b);Need(b.Events==b.Healthy+b.Unavailable,"ALL_EVENTS");string key=pair.Key.ToString(System.Globalization.CultureInfo.InvariantCulture);
   profile[key]=new {events=b.Events,bid_updates=b.BidUpdates,ask_updates=b.AskUpdates,healthy=b.Healthy,unavailable=b.Unavailable,
    stretches=b.Stretches,stretches_at_least_5min=b.LongStretches,longest_span_bucket=b.Healthy==0?"NONE":b.Longest>=SpanNs?"AT_LEAST_5_MINUTES":"LESS_THAN_5_MINUTES",
    unavailability_reasons=new SortedDictionary<string,long>(b.Reasons),initial_snapshot_not_promoted=true,between_receipt_liquidity_proven=false,broker_fills_proven=false,economic_model_executed=false};
   causes[key]=new {book_shapes=new SortedDictionary<string,long>(b.Shapes),field_patterns=new SortedDictionary<string,long>(b.Fields),
    explicit_same_price_bid_updates=b.SameBid,explicit_same_price_ask_updates=b.SameAsk,server_clock_failures=b.ServerFailures,
    gaps_over_5s=b.Gaps,healthy_to_healthy_gap_breaks=b.HealthyGaps,locked_with_both_fields=b.LockedBoth,crossed_with_both_fields=b.CrossedBoth};
  }
  return new {schema="mxm.csharp.spot-source-cause-classification.v1",events=books.Values.Sum(b=>b.Events),profile,causes,
   event_disposition_sha256=Convert.ToHexString(states.GetHashAndReset()).ToLowerInvariant(),
   fixed_age_ms=AgeMs,fixed_observed_span_ms=SpanNs/1000000L,source_authenticated_in_program=false,
   original_consumer_policy_changed=false,economic_model_executed=false,broker_orders=0,economic_edge_proven=false,hard21_proven=false};
 }
 public void Dispose()=>states.Dispose();
}
}
