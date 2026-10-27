using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Replay {
public sealed record MxmDepthEntry(string Id,int Side,decimal Price,decimal Size);
public sealed record MxmDepthUpdate(int Action,string Id,int? Side=null,decimal? Price=null,decimal? Size=null);
public sealed record MxmSequencedDepthView(long Epoch,long Sequence,bool Ready,bool Faulted,
 decimal? Bid,decimal? Ask,decimal? DisplayedBidSize,decimal? DisplayedAskSize,
 long? BidEntryObservedMs,long? AskEntryObservedMs,long? LastBookMessageMs,long? LastSendingUtcMs,
 MxmBookShapeKind Shape,int Entries) {
 public bool ExecutabilityProven=>false;
 public bool ContinuousObservationProven=>false;
 public bool SourceAuthenticationProven=>false;
}
/// <summary>Atomic, single-symbol depth state after a caller-verified sequence
/// baseline. Every inbound session message must be supplied, including admin and
/// other-symbol messages via Advance. No socket, credentials, raw FIX parser,
/// order, historical interpolation or market-data authenticity claim.</summary>
public sealed class MxmSequencedDepthBook {
 sealed record Level(MxmDepthEntry Entry,long ObservedMs);
 const int Limit=10000;
 readonly long symbol;
 Dictionary<string,Level> levels=new(StringComparer.Ordinal);
 long epoch,sequence;long? lastAction,lastBook,sending;
 bool ready,faulted,clockFaulted,session;
 public MxmSequencedDepthBook(long symbolId){
  if(symbolId<=0)throw new ArgumentException("DEPTH_SYMBOL");symbol=symbolId;
 }
 void Clear(){levels.Clear();ready=false;lastBook=sending=null;}
 void Fault(){faulted=true;Clear();}
 void Clock(long now){
  if(clockFaulted || now<0 || lastAction.HasValue && now<lastAction.Value){
   clockFaulted=true;Fault();throw new ArgumentException("DEPTH_CLOCK_FAULT");
  }
  lastAction=now;
 }
 public void BeginVerifiedSession(long baselineSequence,long now){
  Clock(now);
  if(baselineSequence<0 || baselineSequence==long.MaxValue){Fault();throw new ArgumentException("DEPTH_BASELINE");}
  Clear();epoch=checked(epoch+1);sequence=baselineSequence;faulted=false;session=true;
 }
 void Step(long next,long now,long? sent){
  Clock(now);
  if(!session || faulted || sequence==long.MaxValue || next!=sequence+1 ||
    sent.HasValue && sent.Value<0){Fault();throw new ArgumentException("DEPTH_SESSION_SEQUENCE_OR_TIMESTAMP");}
  sequence=next;
 }
 public void Advance(long next,long now){Step(next,now,null);}
 static bool Id(string? id)=>!string.IsNullOrWhiteSpace(id) && id.Length<=128;
 static bool Valid(MxmDepthEntry? e)=>e!=null && Id(e.Id) &&
  (e.Side==1 || e.Side==-1) && e.Price>0m && e.Size>0m;
 public void Snapshot(long next,long now,long symbolId,IEnumerable<MxmDepthEntry> entries,long? sendingUtcMs=null){
  try {
   Step(next,now,sendingUtcMs);
   if(symbolId!=symbol || entries==null)throw new ArgumentException("DEPTH_SNAPSHOT_IDENTITY");
   var batch=entries.Take(Limit+1).ToArray();
   if(batch.Length>Limit || batch.Any(x=>!Valid(x)) || batch.Select(x=>x.Id).Distinct(StringComparer.Ordinal).Count()!=batch.Length)
    throw new ArgumentException("DEPTH_SNAPSHOT_ENTRIES");
   var replacement=batch.ToDictionary(x=>x.Id,x=>new Level(x,now),StringComparer.Ordinal);
   ValidateSums(replacement);
   levels=replacement;ready=true;lastBook=now;sending=sendingUtcMs;
  }catch{Fault();throw;}
 }
 public void Incremental(long next,long now,long symbolId,IEnumerable<MxmDepthUpdate> updates,long? sendingUtcMs=null){
  try {
   Step(next,now,sendingUtcMs);
   if(!ready || symbolId!=symbol || updates==null)throw new ArgumentException("DEPTH_INCREMENTAL_WITHOUT_SNAPSHOT_OR_IDENTITY");
   var batch=updates.Take(Limit+1).ToArray();
   if(batch.Length>Limit)throw new ArgumentException("DEPTH_BATCH_LIMIT");
   // Validate and apply the WHOLE server message to a private copy. A bad
   // suffix may never expose a valid-looking prefix or partial best book.
   var candidate=new Dictionary<string,Level>(levels,StringComparer.Ordinal);
   foreach(var u in batch){
    if(u==null || !Id(u.Id))throw new ArgumentException("DEPTH_UPDATE_ID");
    if(u.Action==2){
     if(!candidate.TryGetValue(u.Id,out var prior) ||
       u.Side.HasValue && u.Side.Value!=prior.Entry.Side || u.Price.HasValue || u.Size.HasValue)
      throw new ArgumentException("DEPTH_DELETE_UNKNOWN_OR_AMBIGUOUS");
     candidate.Remove(u.Id);
    }else if(u.Action==0 && u.Side.HasValue && u.Price.HasValue && u.Size.HasValue){
     var e=new MxmDepthEntry(u.Id,u.Side.Value,u.Price.Value,u.Size.Value);
     if(!Valid(e) || candidate.ContainsKey(u.Id))throw new ArgumentException("DEPTH_NEW_INVALID_OR_DUPLICATE");
     candidate.Add(u.Id,new(e,now));
    }else throw new ArgumentException("DEPTH_UNSUPPORTED_ACTION_OR_FIELDS");
    if(candidate.Count>Limit)throw new ArgumentException("DEPTH_BOOK_LIMIT");
   }
   ValidateSums(candidate);levels=candidate;lastBook=now;sending=sendingUtcMs;
  }catch{Fault();throw;}
 }
 static decimal? Best(Dictionary<string,Level> book,int side){
  var prices=book.Values.Where(x=>x.Entry.Side==side).Select(x=>x.Entry.Price).ToArray();
  return prices.Length==0?null:side==1?prices.Max():prices.Min();
 }
 static (decimal? Size,long? Observed) AtBest(Dictionary<string,Level> book,int side,decimal? price){
  if(!price.HasValue)return(null,null);
  var entries=book.Values.Where(x=>x.Entry.Side==side && x.Entry.Price==price).ToArray();
  decimal sum=0m;checked{foreach(var e in entries)sum+=e.Entry.Size;}
  return(sum,entries.Min(x=>x.ObservedMs));
 }
 static void ValidateSums(Dictionary<string,Level> book){
  AtBest(book,1,Best(book,1));AtBest(book,-1,Best(book,-1));
 }
 public MxmSequencedDepthView Read(long now){
  Clock(now);
  decimal? bid=Best(levels,1),ask=Best(levels,-1);
  var b=AtBest(levels,1,bid);var a=AtBest(levels,-1,ask);
  return new(epoch,sequence,ready && !faulted,faulted,bid,ask,b.Size,a.Size,
   b.Observed,a.Observed,lastBook,sending,MxmBookShape.Classify(bid,ask),levels.Count);
 }
 public void End(long now){Clock(now);session=false;Clear();}
}
}
