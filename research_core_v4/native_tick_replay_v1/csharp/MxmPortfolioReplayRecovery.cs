using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
namespace Mxm.Replay {
public sealed record MxmReplayCapsule(byte[] Payload,string Sha256,long NextEventOrdinal);
/// <summary>Offline counterfactual state, never a broker order/ACK or native Robot restore.</summary>
public sealed partial class MxmPortfolioAccountReplay {
 sealed record SymbolReplayState(string Symbol,DateTime LastBar,DateTime LastQuote,
  MxmQuote? Latest,MxmDecisionReplayState Kernel,MxmIntentReplayState Intent);
 sealed record PositionReplayState(string Symbol,int Direction,decimal Entry,decimal Units,decimal Margin,
  decimal StopRisk,decimal QuoteToEur,DateTime EntryUtc,decimal? StopPrice);
 sealed record AccountReplayState(int Version,string CodeIdentity,string SourceSha256,MxmReplayParameters Parameters,
  long NextEventOrdinal,DateTime LastFeed,bool Halted,decimal Balance,decimal Peak,decimal Drawdown,
  int Accepted,int Exits,SymbolReplayState[] Symbols,PositionReplayState[] Positions,
  MxmPortfolioTrade[] Ledger,string[] Rejections,Dictionary<string,int> Weeks,
  [property:JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingNull)] MxmUsdEurMark? UsdEurMark=null,
  [property:JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingDefault)] bool UsdConversionInvalid=false);
 static readonly JsonSerializerOptions CapsuleJson=new(){UnmappedMemberHandling=JsonUnmappedMemberHandling.Disallow};
 static string CodeIdentity()=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(
  typeof(MxmPortfolioAccountReplay).Assembly.Location))).ToLowerInvariant();
 static bool IsDigest(string s)=>s!=null && s.Length==64 && s.All(c=>c is >= '0' and <= '9' or >= 'a' and <= 'f');
 public long NextEventOrdinal=>processedEvents;
 /// <summary>Pin the returned SHA in authenticated custody separately from payload.
 /// A checksum transported with attacker-controlled payload is not authentication.</summary>
 public MxmReplayCapsule CaptureReplay(string authenticatedSourceSha256){
  Need(started && !faulted && IsDigest(authenticatedSourceSha256),"CHECKPOINT_STATE_OR_SOURCE");
  var value=new AccountReplayState(1,CodeIdentity(),authenticatedSourceSha256,parameters,
   processedEvents,lastFeed,halted,balance,peak,drawdown,accepted,exits,
   state.Select(p=>new SymbolReplayState(p.Key,p.Value.LastBar,p.Value.LastQuote,p.Value.Latest,
    p.Value.Kernel.CaptureReplayState(),p.Value.Intent.CaptureReplayState())).ToArray(),
   open.Select(p=>new PositionReplayState(p.Key,p.Value.Direction,p.Value.Entry,p.Value.Units,p.Value.Margin,
    p.Value.StopRisk,p.Value.QuoteToEur,p.Value.EntryUtc,p.Value.StopPrice)).ToArray(),
   trades.ToArray(),rejected.ToArray(),new Dictionary<string,int>(entriesByWeek),usdEurMark,usdConversionInvalid);
  byte[] payload=JsonSerializer.SerializeToUtf8Bytes(value,CapsuleJson);
  Need(payload.Length<=32000000,"CHECKPOINT_TOO_LARGE");
  return new(payload,Convert.ToHexString(SHA256.HashData(payload)).ToLowerInvariant(),processedEvents);
 }
 public static MxmPortfolioAccountReplay RestoreReplay(byte[] payload,string trustedPayloadSha256,
  string authenticatedSourceSha256,MxmReplayParameters expectedParameters,IEnumerable<string> expectedSymbols){
  Need(payload!=null && payload.Length>0 && payload.Length<=32000000 &&
   IsDigest(trustedPayloadSha256) && IsDigest(authenticatedSourceSha256),"CHECKPOINT_BOUNDS_OR_DIGEST");
  Need(CryptographicOperations.FixedTimeEquals(SHA256.HashData(payload!),Convert.FromHexString(trustedPayloadSha256)),
   "CHECKPOINT_DIGEST_MISMATCH");
  var s=JsonSerializer.Deserialize<AccountReplayState>(payload!,CapsuleJson)
   ?? throw new ArgumentException("EMPTY_REPLAY_CHECKPOINT");
  Need(s.Version==1 && s.CodeIdentity==CodeIdentity() && s.SourceSha256==authenticatedSourceSha256 &&
   s.Parameters==expectedParameters,"CHECKPOINT_CODE_SOURCE_OR_SETTINGS");
  var result=new MxmPortfolioAccountReplay(expectedSymbols,expectedParameters);
  Need(s.Symbols!=null && s.Positions!=null && s.Ledger!=null && s.Rejections!=null && s.Weeks!=null &&
   s.Symbols.Length==result.state.Count && s.Symbols.Select(x=>x.Symbol).Distinct(StringComparer.OrdinalIgnoreCase).Count()==s.Symbols.Length &&
   s.Symbols.Select(x=>x.Symbol).SequenceEqual(result.state.Keys,StringComparer.OrdinalIgnoreCase) &&
   s.Positions.Select(x=>x.Symbol).Distinct(StringComparer.OrdinalIgnoreCase).Count()==s.Positions.Length &&
   s.Positions.All(x=>result.state.ContainsKey(x.Symbol)),"CHECKPOINT_ROSTER");
  decimal ledgerCash=200m;
  var liveEntries=new Dictionary<string,MxmPortfolioTrade>(StringComparer.OrdinalIgnoreCase);
  DateTime previousBooking=default;
  foreach(var item in s.Ledger){
   Need(item.Utc.Kind==DateTimeKind.Utc && item.Utc>=previousBooking && item.Utc<=s.LastFeed &&
    result.state.ContainsKey(item.Symbol),"CHECKPOINT_LEDGER_BOOKING_CLOCK");
   previousBooking=item.Utc;
   if(item.Kind=="ENTRY"){
    Need(item.Financing==null && liveEntries.TryAdd(item.Symbol,item),"CHECKPOINT_ENTRY_LIFECYCLE");
    result.financingThrough.Remove(item.Symbol);
   }else if(item.Kind=="EXIT"){
    Need(item.Financing==null && liveEntries.Remove(item.Symbol,out var prior) &&
     prior.Direction==item.Direction && prior.Units==item.Units,"CHECKPOINT_EXIT_LIFECYCLE");
    result.financingThrough.Remove(item.Symbol);
   }else if(item.Kind=="FINANCING"){
    Need(item.Financing!=null && liveEntries.TryGetValue(item.Symbol,out var prior),"CHECKPOINT_FINANCING_LIFECYCLE");
    // Need's flow annotation cannot establish definite assignment after &&.
    var entry=liveEntries[item.Symbol];var f=item.Financing!;
    CheckFinancing(f,item.Symbol,entry.Utc,entry.Direction,entry.Units,
     result.financingThrough.TryGetValue(item.Symbol,out var through)?through:null,expectedParameters.FinancingScenarioSha256);
    Need(f.Utc==item.Utc && item.Direction==entry.Direction && item.Units==entry.Units &&
     item.Price==0m && item.CommissionEur==0m && item.GrossEur==f.AmountEur &&
     item.Reason=="EXPLICIT_EUR_FINANCING_SCENARIO","CHECKPOINT_FINANCING_CASH_BINDING");
    result.financingThrough[item.Symbol]=f.AccrualEndUtc;
   }else Need(false,"CHECKPOINT_LEDGER_UNKNOWN_KIND");
   ledgerCash=item.Kind=="ENTRY"?ledgerCash-item.CommissionEur:ledgerCash+(item.GrossEur-item.CommissionEur);
   Need(ledgerCash==item.CashEur && item.CommissionEur>=0,"CHECKPOINT_LEDGER_CASH_PATH");
  }
  Need(s.NextEventOrdinal>=0 && (s.NextEventOrdinal==0?s.LastFeed==default:
   s.LastFeed.Kind==DateTimeKind.Utc && s.LastFeed!=default) && s.Accepted>=0 && s.Exits>=0 &&
   s.Ledger.Count(x=>x.Kind=="ENTRY")==s.Accepted && s.Ledger.Count(x=>x.Kind=="EXIT")==s.Exits &&
   s.Accepted-s.Exits==s.Positions.Length && liveEntries.Count==s.Positions.Length &&
   ledgerCash==s.Balance && s.Drawdown>=0,
   "CHECKPOINT_CONTINUOUS_CAPITAL_LEDGER");
  var weeks=s.Ledger.Where(x=>x.Kind=="ENTRY").GroupBy(x=>Week(x.Utc)).ToDictionary(x=>x.Key,x=>x.Count());
  Need(weeks.Count==s.Weeks.Count && weeks.All(x=>s.Weeks.GetValueOrDefault(x.Key)==x.Value),"CHECKPOINT_WEEK_COUNTS");
  foreach(var item in s.Symbols){
   Need((item.LastBar==default || item.LastBar.Kind==DateTimeKind.Utc && item.LastBar<=s.LastFeed) &&
    (item.LastQuote==default?item.Latest==null:item.LastQuote.Kind==DateTimeKind.Utc &&
     item.LastQuote<=s.LastFeed && item.Latest!=null && item.Latest.Utc==item.LastQuote &&
     string.Equals(item.Latest.Symbol,item.Symbol,StringComparison.OrdinalIgnoreCase)),"CHECKPOINT_SYMBOL_CLOCK");
   var st=result.state[item.Symbol];st.LastBar=item.LastBar;st.LastQuote=item.LastQuote;st.Latest=item.Latest;
   st.Kernel.RestoreReplayState(item.Kernel);st.Intent.RestoreReplayState(item.Intent,expectedParameters.BarMinutes);
  }
  foreach(var p in s.Positions){
   Need(liveEntries.TryGetValue(p.Symbol,out var entry) && entry.Utc==p.EntryUtc &&
    entry.Direction==p.Direction && entry.Units==p.Units && entry.Price==p.Entry,"CHECKPOINT_OPEN_POSITION_LEDGER");
   Need((p.Direction==1 || p.Direction==-1) && p.Entry>0 && p.Units>0 && p.Margin>0 && p.StopRisk>0 &&
    p.QuoteToEur>0 && (p.StopPrice==null || p.StopPrice>0) && p.EntryUtc.Kind==DateTimeKind.Utc &&
    p.EntryUtc<=s.LastFeed && result.state[p.Symbol].Latest!=null,"CHECKPOINT_POSITION");
   result.open.Add(p.Symbol,new Holding(p.Direction,p.Entry,p.Units,p.Margin,p.StopRisk,p.QuoteToEur,p.EntryUtc,p.StopPrice));
  }
  Need(expectedParameters.UseSharedUsdConversion || s.UsdEurMark==null && !s.UsdConversionInvalid,"CHECKPOINT_UNREGISTERED_FX_MODE");
  if(expectedParameters.UseSharedUsdConversion)
   foreach(var item in result.state.Values)if(item.Latest is MxmQuote q)
    Need(result.ValidInstrumentMark(q,s.LastFeed,requireFresh:result.open.ContainsKey(q.Symbol)),"CHECKPOINT_INSTRUMENT_SIDE_CLOCKS");
  if(s.UsdEurMark is MxmUsdEurMark fx){
   Need(expectedParameters.UseSharedUsdConversion && result.ValidFx(fx,s.LastFeed,requireFresh:s.Positions.Length>0),"CHECKPOINT_INVALID_SHARED_FX");
   foreach(var item in result.state.Values)if(item.Latest is MxmQuote q)
    Need(q.QuoteToEur==1m/fx.Ask && q.QuoteLossToEur==1m/fx.Bid,"CHECKPOINT_SHARED_FX_MARK_MISMATCH");
  }else Need(!expectedParameters.UseSharedUsdConversion || s.Positions.Length==0,"CHECKPOINT_OPEN_EXPOSURE_WITHOUT_FX");
  Need(!s.UsdConversionInvalid || s.Positions.Length==0,"CHECKPOINT_FUNDED_INVALID_FX");
  result.usdEurMark=s.UsdEurMark;result.usdConversionInvalid=s.UsdConversionInvalid;
  result.balance=s.Balance;result.peak=s.Peak;result.drawdown=s.Drawdown;result.accepted=s.Accepted;result.exits=s.Exits;
  result.trades.AddRange(s.Ledger);result.rejected.AddRange(s.Rejections);
  foreach(var p in s.Weeks)result.entriesByWeek.Add(p.Key,p.Value);
  result.halted=s.Halted;result.started=true;result.processedEvents=s.NextEventOrdinal;result.lastFeed=s.LastFeed;
  Need(result.peak>=Math.Max(200m,result.MarkedEquity()) && result.drawdown>=result.peak-result.MarkedEquity(),
   "CHECKPOINT_DRAWDOWN_HISTORY");
  return result;
 }
}
}
