using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Replay;

namespace Mxm.PortfolioNativeQuote {
 sealed record Tick(long T,string Side,long Raw);
 public static class Readback {
  const long BarMs=300000L;
  const long MaxSideAgeMs=300000L;
  const int ExpectedNativeEvents=28212;
  static void Need(bool ok,string msg) {
   if(!ok)throw new InvalidDataException("MXM_AUTHENTIC_PORTFOLIO_READBACK_"+msg);
  }
  static List<Tick> Parse(string path){
   var result=new List<Tick>();
   long prev=-1;
   foreach(var row in File.ReadLines(path)){
    using var j=JsonDocument.Parse(row);
    var root=j.RootElement;
    var t=root.GetProperty("t").GetInt64();
    var raw=root.GetProperty("raw").GetInt64();
    var side=root.GetProperty("side").GetString();
    Need(t>0 && t>=prev && raw>0 && (side=="bid"||side=="ask"),"RAW_TICK_SEQUENCE");
    prev=t;
    result.Add(new Tick(t,side!,raw));
   }
   Need(result.Count>0,"EMPTY_NATIVE_STREAM");
   return result;
  }
  public static object Run(string input,bool exactExistingSource=true){
   var bytes=File.ReadAllBytes(input);
   var hash=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
   var ticks=Parse(input);
   if(exactExistingSource)Need(ticks.Count==ExpectedNativeEvents,"ORIGINAL_EVENT_COUNT");
   int ambiguous=0,cross=0,stale=0,accepted=0,completeBarDecisions=0,zero=0;
   long bidTime=-1,askTime=-1,barBucket=-1;
   decimal bid=0,ask=0,lastBarBid=0;
   var feeds=new List<MxmAccountFeed>();
   foreach(var group in ticks.GroupBy(x=>x.T)){
    long t=group.Key;
    var inSameMs=group.ToArray();
    // Duplicate same-side revisions cannot be ordered across sides by the
    // historical API. Refuse the entire group instead of manufacturing FIFO.
    if(inSameMs.Where(z=>z.Side=="bid").Select(z=>z.Raw).Distinct().Skip(1).Any() ||
       inSameMs.Where(z=>z.Side=="ask").Select(z=>z.Raw).Distinct().Skip(1).Any()){
      ambiguous++;continue;
    }
    foreach(var quote in inSameMs){
     if(quote.Side=="bid"){bid=quote.Raw/100000m;bidTime=t;}
     else {ask=quote.Raw/100000m;askTime=t;}
    }
    if(bidTime<0 || askTime<0)continue;
    if(ask<bid){cross++;continue;}
    if(t-bidTime>MaxSideAgeMs||t-askTime>MaxSideAgeMs){stale++;continue;}
    if(ask==bid)zero++;
    var stamp=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
    long bucket=(t/BarMs)*BarMs;
    if(barBucket>=0 && bucket!=barBucket){
     // Do not join gaps into synthetic bars; six complete bars must again
     // be accumulated before the shared CSharp kernel can place an order.
     if(bucket==barBucket+BarMs && lastBarBid>0) {
      feeds.Add(new MxmBarClose(stamp,"EURUSD",lastBarBid));
      completeBarDecisions++;
     }
    }
    barBucket=bucket;
    lastBarBid=bid;
    // One quote per original millisecond, never fabricate a later timestamp.
    // All monetary terms below are explicit NON-BROKER-VERIFIED assumptions.
    feeds.Add(new MxmQuote(stamp,"EURUSD",bid,ask,1m/1.10m,
      1000m,50m,0.10m,0.00002m,1.2m));
    accepted++;
   }
   Need(feeds.Count>0 && accepted>0,"NO_REPLAYABLE_SNAPSHOTS");
   // Parameters are fixed DEVELOPMENT counterfactual, NOT a fitted edge.
   var engine=new MxmPortfolioAccountReplay(new[]{"EURUSD"},
    new MxmReplayParameters(StrategyMode.Adaptive,0.4m,1,0m,0.02m,0.2m,5,300));
   var account=engine.Run(feeds);
   return new {
    schema="mxm.csharp.native-exposed-quote-to-one-account.v1",
    classification="ORIGINAL_PEPPERSTONE_QUOTES_SINGLE_SYMBOL_MODELED_TERMS_DEVELOPMENT_EXPOSED",
    original_native_run_id=exactExistingSource?39660692230:0,
    original_source_is_independently_crypto_authenticated_here=false,
    provenance_digest_must_match_pinned_protected_bridge=true,
    derived_stream_sha256=hash,
    quote_events=ticks.Count,
    grouped_atomic_usable_snapshots=accepted,
    ambiguous_same_side_ms_revisions_skipped=ambiguous,
    crossed_snapshots_skipped=cross,
    stale_side_snapshots_skipped=stale,
    zero_spread_snapshots_unverified_liquidity=zero,
    completed_bar_decision_events=completeBarDecisions,
    actual_symbols=1,
    multi_instrument_native_data_available=false,
    synthetic_quote_events_injected=0,
    modeled_parameters=new {
      strategy="Adaptive",bar_minutes=5,max_positions=1,
      units=1000,quote_to_eur=1m/1.10m,
      margin_eur=50m,commission_eur_per_side=0.10m,
      slip_price_per_side=0.00002m,stop_risk_eur=1.2m,
      max_stop_risk_fraction=0.02m,friction_reserve_eur=0.2m,
      historical_broker_terms_verified=false
    },
    account,
    native_ctrader_backtest=false,
    historical_broker_fills_proven=false,
    historical_quote_arrival_order_proven=false,
    one_full_iso_utc_week_proven=false,
    hard21_proven=false,
    scientific_confirmation_opened=false,
    new_broker_requests=0,
    live_orders=0
   };
  }
  public static int Main(string[] args){
   try{
    Need(args.Length==3&&args[0]=="--native-exposed-eurusd",
      "EXPLICIT_NONOUTCOME_MODE_REQUIRED");
    var data=Run(args[1]);
    Directory.CreateDirectory(args[2]);
    var output=Path.Combine(args[2],"portfolio-exposed-quote-readback.json");
    File.WriteAllText(output,JsonSerializer.Serialize(data,new JsonSerializerOptions{
      WriteIndented=true,PropertyNamingPolicy=JsonNamingPolicy.SnakeCaseLower}));
    Console.WriteLine("MXM_CSHARP_AUTHENTIC_EXPOSED_EURUSD_SINGLE_ACCOUNT_MODEL_READBACK_DONE_NO_PROVEN_EDGE");
    return 0;
   }catch(Exception e){
    Console.Error.WriteLine("MXM_CSHARP_PORTFOLIO_NATIVE_READBACK_FAILED_"+e.GetType().Name);
    return 1;
   }
  }
 }
}
