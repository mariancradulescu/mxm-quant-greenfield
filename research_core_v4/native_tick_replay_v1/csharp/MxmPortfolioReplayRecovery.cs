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
  MxmQuote? Latest,MxmDecisionReplayState Kernel,MxmIntentReplayState Intent,
  [property:JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingNull)] MxmExplicitPolicyState? ExplicitPolicy=null);
 sealed record PositionReplayState(string Symbol,int Direction,decimal Entry,decimal Units,decimal Margin,
  decimal StopRisk,decimal QuoteToEur,DateTime EntryUtc,decimal? StopPrice);
 sealed record AccountReplayState(int Version,string CodeIdentity,string SourceSha256,MxmReplayParameters Parameters,
  long NextEventOrdinal,DateTime LastFeed,bool Halted,decimal Balance,decimal Peak,decimal Drawdown,
  int Accepted,int Exits,SymbolReplayState[] Symbols,PositionReplayState[] Positions,
  MxmPortfolioTrade[] Ledger,string[] Rejections,Dictionary<string,int> Weeks,
  [property:JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingNull)] MxmUsdEurMark? UsdEurMark=null,
  [property:JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingDefault)] bool UsdConversionInvalid=false,
  [property:JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingNull)] MxmHistoricalSourceState? HistoricalSource=null);
 static readonly JsonSerializerOptions CapsuleJson=new(){UnmappedMemberHandling=JsonUnmappedMemberHandling.Disallow};
 static string CodeIdentity()=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(
  typeof(MxmPortfolioAccountReplay).Assembly.Location))).ToLowerInvariant();
 static bool IsDigest(string s)=>s!=null && s.Length==64 && s.All(c=>c is >= '0' and <= '9' or >= 'a' and <= 'f');
 public long NextEventOrdinal=>processedEvents;
 /// <summary>Pin the returned SHA in authenticated custody separately from payload.
 /// A checksum transported with attacker-controlled payload is not authentication.</summary>
 public MxmReplayCapsule CaptureReplay(string authenticatedSourceSha256){
  Need(started && !faulted && IsDigest(authenticatedSourceSha256),"CHECKPOINT_STATE_OR_SOURCE");
  Need(historicalSource==null || historicalSource.SourceSha256==authenticatedSourceSha256,"CHECKPOINT_HISTORICAL_SOURCE_IDENTITY");
  var value=new AccountReplayState(1,CodeIdentity(),authenticatedSourceSha256,parameters,
   processedEvents,lastFeed,halted,balance,peak,drawdown,accepted,exits,
   state.Select(p=>new SymbolReplayState(p.Key,p.Value.LastBar,p.Value.LastQuote,p.Value.Latest,
    p.Value.Kernel.CaptureReplayState(),p.Value.Intent.CaptureReplayState(),
    parameters.ExplicitPolicySha256==null?null:new MxmExplicitPolicyState(p.Value.PolicyPending,p.Value.PolicySequence,p.Value.PolicyBlockedThrough))).ToArray(),
   open.Select(p=>new PositionReplayState(p.Key,p.Value.Direction,p.Value.Entry,p.Value.Units,p.Value.Margin,
    p.Value.StopRisk,p.Value.QuoteToEur,p.Value.EntryUtc,p.Value.StopPrice)).ToArray(),
   trades.ToArray(),rejected.ToArray(),new Dictionary<string,int>(entriesByWeek),usdEurMark,usdConversionInvalid,historicalSource);
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
   if(expectedParameters.ExplicitPolicySha256==null)Need(item.ExplicitPolicy==null,"CHECKPOINT_UNREGISTERED_EXPLICIT_POLICY");
   else {
    var e=item.ExplicitPolicy;Need(e!=null && e.LastSequence>=0 &&
     (e.BlockedThrough==default || e.BlockedThrough.Kind==DateTimeKind.Utc && e.BlockedThrough<=s.LastFeed),"CHECKPOINT_POLICY_STATE");
    if(e!.Pending is MxmExplicitDecision d)Need(d.Symbol==item.Symbol && d.Sequence==e.LastSequence && d.Sequence>0 &&
     d.PolicySha256==expectedParameters.ExplicitPolicySha256 && d.Desired is >=-1 and <=1 &&
     d.Utc.Kind==DateTimeKind.Utc && d.Utc>e.BlockedThrough && d.Utc<=s.LastFeed &&
     d.ValidFromUtc.Kind==DateTimeKind.Utc && d.ExpiresUtc.Kind==DateTimeKind.Utc &&
     d.ValidFromUtc>d.Utc && d.ExpiresUtc>d.ValidFromUtc &&
     (d.ExpiresUtc-d.Utc).TotalSeconds<=expectedParameters.MaxQuoteAgeSeconds,"CHECKPOINT_POLICY_PENDING");
    st.PolicyPending=e.Pending;st.PolicySequence=e.LastSequence;st.PolicyBlockedThrough=e.BlockedThrough;
   }
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
  if(expectedParameters.UseSharedUsdConversion || expectedParameters.RequireObservedExposurePath)
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
  result.RestoreHistoricalSource(s.HistoricalSource,authenticatedSourceSha256);
  return result;
 }
}
// Historical side-clock state belongs to the SAME account capsule. It grants
// no execution authority, receipt-clock semantics, strategy decision or funding.
public sealed record MxmHistoricalQuoteGroup(long SourceMs,string Symbol,long[] Bids,long[] Asks);
public sealed record MxmHistoricalBook(string Symbol,long? Bid,long? BidMs,long? Ask,long? AskMs,
 long Groups,long Rows,long AmbiguousGroups);
public sealed record MxmHistoricalSourceState(string SourceSha256,string StreamSha256,
 long FromMs,long ToMs,long MaximumRows,long Groups,long Rows,long LastMs,string LastSymbol,
 string PrefixSha256,MxmHistoricalBook[] Books);
public sealed partial class MxmPortfolioAccountReplay {
 MxmHistoricalSourceState? historicalSource;
 bool processingHistoricalSource;
 public MxmHistoricalSourceState? HistoricalSource=>historicalSource is null?null:
  historicalSource with {Books=historicalSource.Books.ToArray()};
 public void BeginHistoricalSource(string sourceSha,string streamSha,long fromMs,long toMs,long maximumRows){
  Need(historicalSource==null && !started && !faulted && processedEvents==0 &&
   IsDigest(sourceSha) && IsDigest(streamSha) && fromMs>0 && toMs>fromMs &&
   maximumRows>0 && maximumRows<=1000000 && parameters.UseSharedUsdConversion &&
   parameters.UsdQuoteMetadataJson!=null,"HISTORICAL_SOURCE_ADMISSION");
  using var declaration=JsonDocument.Parse(parameters.UsdQuoteMetadataJson!);
  Need(declaration.RootElement.GetProperty("source_sha256").GetString()==sourceSha,"HISTORICAL_DECLARATION_SOURCE");
  historicalSource=new(sourceSha,streamSha,fromMs,toMs,maximumRows,0,0,0,"",streamSha,
   state.Keys.Select(s=>new MxmHistoricalBook(s,null,null,null,null,0,0,0)).ToArray());
  processingHistoricalSource=true;
  try {Run(Array.Empty<MxmAccountFeed>());}finally {processingHistoricalSource=false;}
 }
 public void ObserveHistoricalGroup(MxmHistoricalQuoteGroup group,long expectedGroupOrdinal){
  try {
   var h=historicalSource;
   Need(h!=null && !faulted && !halted && expectedGroupOrdinal==h.Groups &&
    balance==200m && accepted==0 && exits==0 && open.Count==0 && trades.Count==0 &&
    state.Values.All(s=>s.Kernel.CompletedBars==0 && s.PolicyPending==null),"HISTORICAL_CURSOR_OR_ACCOUNT");
   Need(group!=null && group.Bids!=null && group.Asks!=null && state.ContainsKey(group.Symbol) &&
    state.Keys.Contains(group.Symbol,StringComparer.Ordinal) &&
    group.SourceMs>=h!.FromMs && group.SourceMs<h.ToMs &&
    (h.Groups==0 || group.SourceMs>h.LastMs || group.SourceMs==h.LastMs &&
     StringComparer.Ordinal.Compare(group.Symbol,h.LastSymbol)>0),"HISTORICAL_ATOMIC_GROUP_CLOCK");
   long rows=checked((long)group.Bids.Length+group.Asks.Length);
   Need(rows>0 && rows<=h.MaximumRows-h.Rows && group.Bids.All(v=>v>0) && group.Asks.All(v=>v>0),"HISTORICAL_ROWS_OR_VALUES");
   var old=h.Books.Single(b=>b.Symbol==group.Symbol);
   long[] bids=group.Bids.Distinct().ToArray(),asks=group.Asks.Distinct().ToArray();
   // An ambiguous update poisons that side until a later unambiguous group.
   // Retaining a previous value would silently heal an unknown source state.
   var book=old with {Groups=old.Groups+1,Rows=old.Rows+rows,
    AmbiguousGroups=old.AmbiguousGroups+(bids.Length>1||asks.Length>1?1:0),
    Bid=bids.Length==0?old.Bid:bids.Length==1?bids[0]:null,
    BidMs=bids.Length==0?old.BidMs:bids.Length==1?group.SourceMs:null,
    Ask=asks.Length==0?old.Ask:asks.Length==1?asks[0]:null,
    AskMs=asks.Length==0?old.AskMs:asks.Length==1?group.SourceMs:null};
   // Advance the existing account clock and revoke any execution intent. No
   // MxmQuote, price conversion or invented margin/cost is manufactured.
   processingHistoricalSource=true;
   try {Continue(new MxmAccountFeed[]{new MxmInstrumentQuoteUnavailable(
    DateTimeOffset.FromUnixTimeMilliseconds(group.SourceMs).UtcDateTime,group.Symbol,
    "HISTORICAL_SOURCE_ONLY_NO_DATED_EXECUTION_AUTHORITY")},processedEvents);}
   finally {processingHistoricalSource=false;}
   string chain=Convert.ToHexString(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(
    new {prior=h.PrefixSha256,group}))).ToLowerInvariant();
   historicalSource=h with {Groups=h.Groups+1,Rows=h.Rows+rows,LastMs=group.SourceMs,
    LastSymbol=group.Symbol,PrefixSha256=chain,Books=h.Books.Select(b=>b.Symbol==book.Symbol?book:b).ToArray()};
  }catch {faulted=true;throw;}
 }
 void RestoreHistoricalSource(MxmHistoricalSourceState? h,string sourceSha){
  if(h==null)return;
  Need(parameters.UseSharedUsdConversion && parameters.UsdQuoteMetadataJson!=null &&
   h.SourceSha256==sourceSha && IsDigest(h.StreamSha256) && IsDigest(h.PrefixSha256) &&
   h.FromMs>0 && h.ToMs>h.FromMs && h.MaximumRows>0 && h.MaximumRows<=1000000 &&
   h.Groups>=0 && h.Rows>=h.Groups && h.Rows<=h.MaximumRows && h.Books!=null &&
   h.Books.Select(b=>b.Symbol).SequenceEqual(state.Keys,StringComparer.Ordinal) &&
   h.Books.Sum(b=>b.Groups)==h.Groups && h.Books.Sum(b=>b.Rows)==h.Rows &&
   h.Books.All(b=>b.Groups>=0 && b.Rows>=b.Groups && b.AmbiguousGroups>=0 && b.AmbiguousGroups<=b.Groups),
   "CHECKPOINT_HISTORICAL_SOURCE");
  using var doc=JsonDocument.Parse(parameters.UsdQuoteMetadataJson!);
  Need(doc.RootElement.GetProperty("source_sha256").GetString()==h.SourceSha256 &&
   balance==200m && accepted==0 && exits==0 && open.Count==0 && trades.Count==0 &&
   usdEurMark==null && !usdConversionInvalid && processedEvents==h.Groups &&
   state.Values.All(s=>s.Kernel.CompletedBars==0 && s.Latest==null && s.LastBar==default &&
    s.LastQuote==default && s.PolicyPending==null),"CHECKPOINT_HISTORICAL_ACCOUNT_BINDING");
  if(h.Groups==0)Need(h.Rows==0 && h.LastMs==0 && h.LastSymbol=="" && lastFeed==default &&
   h.PrefixSha256==h.StreamSha256,"CHECKPOINT_HISTORICAL_EMPTY");
  else Need(h.LastMs>=h.FromMs && h.LastMs<h.ToMs &&
   h.Books.Any(b=>b.Symbol==h.LastSymbol && b.Groups>0) &&
   lastFeed==DateTimeOffset.FromUnixTimeMilliseconds(h.LastMs).UtcDateTime,"CHECKPOINT_HISTORICAL_CURSOR");
  foreach(var b in h.Books) {
   bool Side(long? value,long? stamp)=>value.HasValue==stamp.HasValue &&
    (!value.HasValue || value.Value>0 && stamp>=h.FromMs && stamp<=h.LastMs && b.Groups>0);
   Need(Side(b.Bid,b.BidMs) && Side(b.Ask,b.AskMs) &&
    (b.Groups>0 || b.Rows==0 && b.AmbiguousGroups==0 && b.Bid==null && b.Ask==null),
    "CHECKPOINT_HISTORICAL_SIDE");
  }
  historicalSource=h;
 }
}
}
