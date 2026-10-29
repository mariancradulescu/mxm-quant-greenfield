using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Replay;
if(args.Length!=2)throw new ArgumentException("TRIANGLE_INPUT_OUTPUT");
using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));var root=doc.RootElement;
var terms=MxmInstrumentCommission.Decode(root.GetProperty("target_terms"),2,"USD");
if(!MxmInstrumentCommission.Valid(terms) || terms.MinimumAsset is not ("EUR" or "USD"))throw new ArgumentException("TRIANGLE_NATIVE_TERMS");
decimal units=terms.MinimumVolume/100m,margin=decimal.Parse(root.GetProperty("margin_eur").GetString()!,CultureInfo.InvariantCulture);
var snapshots=new List<Snapshot>();var books=new Dictionary<int,Book>{{1,new()},{2,new()},{9,new()}};
long sequence=0,arrival=-1,received=-1;var graph=new MxmObservedCostFx(new[]{new MxmFxInstrument("1","EUR","USD"),new MxmFxInstrument("2","GBP","USD"),new MxmFxInstrument("9","EUR","GBP")});
foreach(var row in root.GetProperty("events").EnumerateArray()){
 int sid=row.GetProperty("symbol").GetInt32();long seq=row.GetProperty("sequence").GetInt64(),ns=row.GetProperty("arrival_ns").GetInt64(),utc=row.GetProperty("received_ms").GetInt64();
 if(!books.ContainsKey(sid)||seq<=sequence||ns<arrival||utc<received)throw new ArgumentException("TRIANGLE_SOURCE_ORDER");
 sequence=seq;arrival=ns;received=utc;
 long? server=row.GetProperty("server_ms").ValueKind==JsonValueKind.Null?null:row.GetProperty("server_ms").GetInt64();
 decimal? Side(string key)=>row.GetProperty(key).ValueKind==JsonValueKind.Null?null:row.GetProperty(key).GetInt64()/100000m;
 bool priorMarkable=books[2].View(ns,utc).Markable&&books[1].View(ns,utc).Markable;
 books[sid].Observe(Side("bid"),Side("ask"),ns,utc,server);
 View V(int id)=>books[id].View(ns,utc);
 var target=V(2);var fx=V(1);var cross=V(9);
 decimal? fee=null;bool affordable=false;
 if(target.Markable && fx.Markable){
  var currencies=new Dictionary<string,decimal>{{"EUR",1m},{"USD",graph.CostRate("USD","EUR",ns/1000000,s=>s=="1"?books[1].Fx(ns):null).Rate}};
  fee=Math.Max(MxmInstrumentCommission.Price(terms,terms.MinimumVolume,target.Bid!.Value,1m,currencies).UnroundedFeeEur,
   MxmInstrumentCommission.Price(terms,terms.MinimumVolume,target.Ask!.Value,1m,currencies).UnroundedFeeEur);
  // Necessary EUR200 screen only; no actual funding/order or guaranteed stop.
  affordable=margin>0 && margin<=80m && 200m-margin-fee>=120m && 2m*fee<=.2m &&
   .0012m*units/fx.Bid!.Value+2m*fee<=2m;
 }
 decimal? synthBid=fx.Markable&&cross.Markable?fx.Bid/cross.Ask:null,synthAsk=fx.Markable&&cross.Markable?fx.Ask/cross.Bid:null;
 snapshots.Add(new(sid,seq,ns,utc,target,fx,cross,synthBid,synthAsk,fee,affordable,priorMarkable));
}
var own=snapshots.Where(s=>s.Symbol==2).ToArray();long[] clocks=own.Select(s=>s.Ns).ToArray();
int Lower(long value){int lo=0,hi=clocks.Length;while(lo<hi){int m=(lo+hi)/2;if(clocks[m]<value)lo=m+1;else hi=m;}return lo;}
bool Ready(Snapshot s)=>s.Target.Positive && s.Fx.Markable && s.Cross.Markable && s.Fee.HasValue && s.Affordable;
var locations=snapshots.Select((s,i)=>(s.Sequence,i)).ToDictionary(x=>x.Sequence,x=>x.i);
var bad=new int[snapshots.Count+1];for(int i=0;i<snapshots.Count;i++)bad[i+1]=bad[i]+(!snapshots[i].PriorExposureMarkable||!snapshots[i].Target.Markable||!snapshots[i].Fx.Markable?1:0);
int potential=0,complete=0;
foreach(var s in own.Where(Ready)){
 potential++;int j=Lower(s.Ns+250000000L);
 if(j>=own.Length||own[j].Ns>s.Ns+3000000000L||!own[j].Target.Positive||!own[j].Fx.Markable)continue;
 int k=Lower(own[j].Ns+1000000000L);
 if(k>=own.Length||own[k].Ns>own[j].Ns+4000000000L||!own[k].Target.Positive||!own[k].Fx.Markable)continue;
 // All observed target/FX marks on the prospective exposure path are checked,
 // including non-target messages. No response prices or return signs are read.
 if(bad[locations[own[k].Sequence]+1]-bad[locations[s.Sequence]+1]>0)continue;
 complete++;
}
bool admitted=potential>=100 && complete>=.8m*potential;
var journal=new List<object>();var episodes=new List<object>();long ordinal=0,identity=0,busy=-1;Episode? pending=null,active=null;
object Context(Snapshot s)=>new{source_symbol=s.Symbol,prior_exposure_markable=s.PriorExposureMarkable,target=s.Target,fx=s.Fx,synthetic=new{bid=s.SyntheticBid,ask=s.SyntheticAsk,cross=s.Cross},
 cost_state="CONTEMPORANEOUS_COMMISSION_REFERENCE_UNKNOWN_TOTAL_COST",margin_state=new{dated_estimate_eur=margin,capital_reference_eur=200,full_entry_admission=false},
 risk_state=new{estimated_stop_distance_quote=.0012m,affordable=s.Affordable,stop_fill_proven=false},fee_per_side_ceiling_eur=s.Fee};
object Fill(Snapshot s,int direction,bool exit){decimal price=(exit?direction>0?s.Target.Bid:s.Target.Ask:direction>0?s.Target.Ask:s.Target.Bid)!.Value;
 return new{price,units,commission_eur=s.Fee,fx_profit=1m/s.Fx.Ask,fx_loss=1m/s.Fx.Bid,spread_embedded=true,slippage_quote=0m,
 funding_state="UNRESOLVED_NOT_ZERO_ACTUAL_CHARGE",source_sequence=s.Sequence};}
void Log(Snapshot s,string state,string reason,int direction=0,long? id=null,object? fill=null)=>journal.Add(new{
 ordinal=++ordinal,source_sequence=s.Sequence,received_ms=s.Utc,arrival_ns=s.Ns,state,reason,direction,opportunity_id=id,context=Context(s),modeled_fill=fill});
void Censor(Snapshot s,string reason){var e=active??pending;if(e==null)return;Log(s,"CENSORED",reason,e.Direction,e.Id);
 episodes.Add(new{id=e.Id,direction=e.Direction,decision=e.Decision,entry=e.Entry,exit=(object?)null,reason,gross_eur=(decimal?)null,net_scenario_eur=(decimal?)null});active=pending=null;}
if(admitted){
 foreach(var s in snapshots){
  // Every target observation receives an audit record, including abstentions,
  // overlapping proposals and clocks/terms that cannot support a modeled fill.
  bool wrote=false;
  if(pending!=null && s.Ns>pending.Decision.Ns+3000000000L){Censor(s,"ENTRY_DEADLINE");wrote=true;}
  if(active!=null && s.Ns>active.Entry!.Ns+4000000000L){Censor(s,"EXIT_DEADLINE");wrote=true;}
  if(active!=null && (!s.PriorExposureMarkable||!s.Target.Markable||!s.Fx.Markable)){Log(s,"MARK_UNAVAILABLE","EXPOSED_PATH_UNPRICEABLE",active.Direction,active.Id);Censor(s,"EXPOSED_PATH_UNPRICEABLE");wrote=true;}
  if(pending!=null && (!s.PriorExposureMarkable||!s.Target.Markable||!s.Fx.Markable)){Censor(s,"PREENTRY_SOURCE_INVALID");wrote=true;}
  if(s.Symbol!=2)continue;
  if(active!=null && s.Ns>=active.Entry!.Ns+1000000000L && s.Target.Positive && s.Fx.Markable && s.Fee.HasValue){
   var e=active;decimal ep=e.Direction>0?e.Entry!.Target.Ask!.Value:e.Entry!.Target.Bid!.Value;
   decimal xp=e.Direction>0?s.Target.Bid!.Value:s.Target.Ask!.Value;
   decimal usd=e.Direction*(xp-ep)*units;decimal gross=usd/(usd>=0?s.Fx.Ask!.Value:s.Fx.Bid!.Value);
   decimal cost=e.Entry!.Fee!.Value+s.Fee.Value;
   Log(s,"EXIT","FIRST_ADMISSIBLE_EXIT_QUOTE",e.Direction,e.Id,Fill(s,e.Direction,true));
   episodes.Add(new{id=e.Id,direction=e.Direction,decision=e.Decision,entry=e.Entry,exit=s,reason="MODELED_QUOTE_EXIT",
    gross_eur=(decimal?)gross,net_scenario_eur=(decimal?)(gross-cost)});active=null;wrote=true;
  }
  if(pending!=null && s.Ns>=pending.Decision.Ns+250000000L && s.Target.Positive && s.Fx.Markable && s.Fee.HasValue && s.Affordable){
   active=pending with {Entry=s};pending=null;Log(s,"ENTRY","FIRST_ADMISSIBLE_STRICTLY_LATER_QUOTE",active.Direction,active.Id,Fill(s,active.Direction,false));wrote=true;
  }
  if(active!=null||pending!=null||s.Ns<busy){if(!wrote)Log(s,"OVERLAP_REJECTED","ONE_PENDING_OR_ACTIVE_EPISODE_AND_FIXED_HOLDOFF");continue;}
  if(!Ready(s)){if(!wrote)Log(s,"ABSTAIN","SOURCE_TERMS_OR_CAPITAL_REFERENCE_UNAVAILABLE");continue;}
  decimal hurdle=2m*(s.Target.Ask!.Value-s.Target.Bid!.Value)+2m*s.Fee!.Value*s.Fx.Ask!.Value/units;
  int direction=s.SyntheticBid!.Value-s.Target.Ask.Value>hurdle+.00000000000000000001m?1:s.Target.Bid.Value-s.SyntheticAsk!.Value>hurdle+.00000000000000000001m?-1:0;
  if(direction==0){if(!wrote)Log(s,"ABSTAIN","BELOW_FIXED_TRIAD_FRICTION_HURDLE");continue;}
  pending=new(++identity,direction,s,null);busy=s.Ns+8000000000L;Log(s,"PROPOSAL","STRUCTURAL_TRIAD_PRICE_DISLOCATION",direction,identity);
 }
 if(pending!=null||active!=null)Censor(snapshots[^1],"SOURCE_END_NO_FABRICATED_LIQUIDATION");
}
string hash=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[0]))).ToLowerInvariant();
File.WriteAllText(args[1],JsonSerializer.Serialize(new{schema="mxm.prospective-quote-triad-private.v1",input_sha256=hash,
 admission=new{potential,complete,admitted,geometry_uses_prices_only_for_book_validity_and_cost_admission=true,economic_responses_read=false},
 source_events=snapshots.Count,target_events=own.Length,models=admitted?1:0,journal,episodes,
 source_authenticated_in_program=false,actual_broker_fills=false,historical_total_costs_proven=false,independent_confirmation=false,
 full_capital_replay=false,hard21_proven=false,orders=0})+"\n");
sealed record View(decimal? Bid,decimal? Ask,long? BidArrival,long? AskArrival,long? BidServer,long? AskServer,bool Markable,bool Positive);
sealed class Book {
 readonly MxmBookObservation<decimal> book=MxmBookObservations.RawFields();bool first=true;long? maximum,bidNs,askNs;
 public Book(){book.BeginEpoch(0);}
 public void Observe(decimal? bid,decimal? ask,long ns,long utc,long? server){
  bool ok=server.HasValue && utc>=server && utc-server<=5000 && (!maximum.HasValue||server>=maximum);
  if(server.HasValue)maximum=maximum.HasValue?Math.Max(maximum.Value,server.Value):server;
  book.Observe(bid,ask,ns/1000000,utc,ok&&!first?server:null);first=false;if(bid.HasValue)bidNs=ns;if(ask.HasValue)askNs=ns;
 }
 public View View(long ns,long utc){var x=book.ReadBook(ns/1000000);var o=x.Observation;
  bool fresh=o.BidServerMs.HasValue&&o.AskServerMs.HasValue && utc>=o.BidServerMs&&utc>=o.AskServerMs &&
   utc-o.BidServerMs<=5000 && utc-o.AskServerMs<=5000 && ns-bidNs<=5000000000L&&ns-askNs<=5000000000L;
  bool mark=fresh&&x.Bid>0&&x.Ask>=x.Bid;
  return new(x.Bid,x.Ask,bidNs,askNs,o.BidServerMs,o.AskServerMs,mark,mark&&x.Ask>x.Bid);
 }
 public MxmObservedFxBook Fx(long ns){var x=book.ReadBook(ns/1000000);return new("1",x.Bid,x.Ask,x.Observation);}
}
sealed record Snapshot(int Symbol,long Sequence,long Ns,long Utc,View Target,View Fx,View Cross,decimal? SyntheticBid,decimal? SyntheticAsk,decimal? Fee,bool Affordable,bool PriorExposureMarkable);
sealed record Episode(long Id,int Direction,Snapshot Decision,Snapshot? Entry);
