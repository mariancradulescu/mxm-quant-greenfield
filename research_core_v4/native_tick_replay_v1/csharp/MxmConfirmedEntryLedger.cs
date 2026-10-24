using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Mxm.Replay {
public sealed record MxmConfirmedEntry(long PositionId,string Symbol,int Direction,decimal Units,
 DateTime EntryUtc,DateTime ObservedUtc);
public sealed record MxmRecordedWeek(string IsoWeek,DateTime StartUtc,int ConfirmedProtectedEntries,
 bool CalendarWeekElapsed,bool MeasurementStartedBeforeWeek,bool RecordedThresholdMet,
 bool BrokerHistoryCoverageProven=false,bool Hard21Proven=false);

/// <summary>Durable lower bound of positively reconciled protected entries from this adapter.
/// Not broker history, a deal ledger, a coverage certificate, or a trading target.
/// One owner/storage domain only. Missing storage cannot prove it was never erased.</summary>
public sealed class MxmConfirmedEntryLedger {
 sealed record Payload(int Version,string Scope,DateTime StartedUtc,MxmConfirmedEntry[] Entries);
 sealed record Envelope(string Payload,string Sha256);
 readonly IMxmEntryCheckpointStore store;
 readonly string scope;
 Payload? state;
 string? persisted;
 public bool Halted {get;private set;}
 public string StorageKey {get;}
 public DateTime StartedUtc=>state?.StartedUtc??throw new InvalidOperationException("LEDGER_NOT_READY");
 public int Count=>state?.Entries.Length??0;
 public MxmConfirmedEntryLedger(IMxmEntryCheckpointStore store,string accountScope){
  if(store==null || string.IsNullOrWhiteSpace(accountScope) || accountScope.Length>1024)
   throw new ArgumentException("INVALID_CONFIRMED_ENTRY_SCOPE");
  this.store=store;scope=Hash(accountScope);StorageKey="MXM Fills V1 "+scope.Substring(0,32);
 }
 static string Hash(string value)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
 static bool Utc(DateTime time)=>time.Kind==DateTimeKind.Utc && time!=default;
 // cTrader GetString documents an empty string for an absent key.
 // Translate only at the native adapter boundary; whitespace/malformed values remain corrupt.
 public static string? NormalizeNativeRead(string? value)=>string.IsNullOrEmpty(value)?null:value;
 public void Halt()=>Halted=true;
 bool Fail(){Halt();return false;}
 static string Encode(Payload value){
  string raw=JsonSerializer.Serialize(value);return JsonSerializer.Serialize(new Envelope(raw,Hash(raw)));
 }
 bool Commit(Payload next){
  string raw=Encode(next);store.Write(raw);
  if(Halted || store.Read()!=raw || Halted)return Fail();
  state=next;persisted=raw;return true;
 }
 public bool Initialize(DateTime observedUtc){
  if(Halted || state!=null || !Utc(observedUtc))return Fail();
  try {
   string? prior=store.Read();if(Halted)return Fail();
   // Null means a first measurement, including upgrade from the old adapter.
   // Empty/corrupt/noncanonical existing values are never overwritten as first use.
   if(prior==null)return Commit(new(1,scope,observedUtc,Array.Empty<MxmConfirmedEntry>()));
   var envelope=JsonSerializer.Deserialize<Envelope>(prior);
   if(envelope==null || envelope.Payload==null || envelope.Sha256!=Hash(envelope.Payload))return Fail();
   var decoded=JsonSerializer.Deserialize<Payload>(envelope.Payload);
   if(decoded==null || decoded.Version!=1 || decoded.Scope!=scope || !Utc(decoded.StartedUtc) ||
      decoded.StartedUtc>observedUtc || decoded.Entries==null || decoded.Entries.Length>100000 ||
      Encode(decoded)!=prior)return Fail();
   var ids=new HashSet<long>();DateTime last=decoded.StartedUtc;
   foreach(var entry in decoded.Entries){
    if(!Valid(entry,decoded.StartedUtc,observedUtc) || entry.ObservedUtc<last || !ids.Add(entry.PositionId))return Fail();
    last=entry.ObservedUtc;
   }
   // Reload and verify before accepting the recovered immutable snapshot.
   if(store.Read()!=prior || Halted)return Fail();
   state=decoded;persisted=prior;return true;
  }catch{return Fail();}
 }
 static bool Valid(MxmConfirmedEntry? value,DateTime start,DateTime now)=>value!=null &&
  value.PositionId>0 && !string.IsNullOrWhiteSpace(value.Symbol) && value.Symbol.Length<=128 &&
  (value.Direction==1 || value.Direction==-1) && value.Units>0 &&
  Utc(value.EntryUtc) && Utc(value.ObservedUtc) && start<=value.EntryUtc &&
  value.EntryUtc<=value.ObservedUtc && value.ObservedUtc<=now;
 public bool RecordConfirmed(MxmConfirmedEntry entry){
  if(Halted || state==null)return Fail();
  try {
   if(store.Read()!=persisted || Halted || !Valid(entry,state.StartedUtc,entry.ObservedUtc))return Fail();
   var prior=state.Entries.FirstOrDefault(x=>x.PositionId==entry.PositionId);
   // Re-reading the same acknowledged position is idempotent, including after restart.
   // A different symbol, direction, volume or broker entry time for that ID is ambiguous.
   if(prior!=null)return prior.Symbol==entry.Symbol && prior.Direction==entry.Direction &&
    prior.Units==entry.Units && prior.EntryUtc==entry.EntryUtc && entry.ObservedUtc>=prior.ObservedUtc || Fail();
   if(state.Entries.Length>=100000 || entry.ObservedUtc<
     (state.Entries.Length==0?state.StartedUtc:state.Entries[^1].ObservedUtc))return Fail();
   return Commit(state with {Entries=state.Entries.Append(entry).ToArray()});
  }catch{return Fail();}
 }
 public bool VerifyCurrent(DateTime observedUtc){
  if(Halted || state==null || !Utc(observedUtc) || observedUtc<state.StartedUtc ||
    state.Entries.Any(x=>x.ObservedUtc>observedUtc))return Fail();
  try {return store.Read()==persisted && !Halted || Fail();}catch{return Fail();}
 }
 public static DateTime WeekStart(DateTime time){
  if(!Utc(time))throw new ArgumentException("ISO_WEEK_REQUIRES_UTC");
  return time.Date.AddDays(-(((int)time.DayOfWeek+6)%7));
 }
 public static string WeekId(DateTime time){
  if(!Utc(time))throw new ArgumentException("ISO_WEEK_REQUIRES_UTC");
  return ISOWeek.GetYear(time).ToString("D4",CultureInfo.InvariantCulture)+"-W"+
   ISOWeek.GetWeekOfYear(time).ToString("D2",CultureInfo.InvariantCulture);
 }
 public MxmRecordedWeek[] Snapshot(DateTime observedUtc){
  if(!VerifyCurrent(observedUtc))throw new InvalidOperationException("UNVERIFIED_LEDGER_SNAPSHOT");
  var current=state!;
  var result=new List<MxmRecordedWeek>();
  var counts=current.Entries.GroupBy(x=>WeekId(x.EntryUtc)).ToDictionary(x=>x.Key,x=>x.Count());
  for(var start=WeekStart(current.StartedUtc);start<=WeekStart(observedUtc);start=start.AddDays(7)){
   int count=counts.TryGetValue(WeekId(start),out var value)?value:0;
   result.Add(new(WeekId(start),start,count,start.AddDays(7)<=observedUtc,current.StartedUtc<=start,count>=21));
  }
  return result.ToArray();
 }
}
}
