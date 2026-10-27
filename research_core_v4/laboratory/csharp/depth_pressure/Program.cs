using System.Text.Json;
using System.Security.Cryptography;
using System.Text;
using System.Globalization;
using var input=JsonDocument.Parse(File.ReadAllBytes(args[0]));
var rows=input.RootElement.EnumerateArray().ToArray();
long last=-1,sequence=-1,bid=0,ask=0,bt=-1,at=-1,bs=-1,ass=-1,server=-1,blocked=-1;
bool first=true;long? firstDepth=null;long? decision=null,entry=null;int direction=0;long ep=0;
var flow=new Queue<(long Time,int Side,long Size)>();
var episodes=new List<object>();var censors=new List<object>();var decisions=new List<object>();
long signals=0;
bool Healthy(long t,long utc)=>bid>0 && ask>bid && bt>=0 && at>=0 && bs>=0 && ass>=0 &&
 t>=bt && t>=at && t-bt<=5000 && t-at<=5000 && utc>=bs && utc>=ass && utc-bs<=5000 && utc-ass<=5000;
void Censor(long t,string why){censors.Add(new {decision,direction,entry,t,reason=why});decision=null;entry=null;}
foreach(var r in rows){
 long t=r.GetProperty("t").GetInt64(),seq=r.GetProperty("seq").GetInt64(),utc=r.GetProperty("utc").GetInt64();
 if(t<0 || t<last || seq<=sequence)throw new ArgumentException("SOURCE_ORDER");last=t;sequence=seq;
 string kind=r.GetProperty("kind").GetString()!;
 bool priorHealthy=Healthy(t,utc);
 if(kind=="spot"){
  long? Value(string k)=>r.GetProperty(k).ValueKind==JsonValueKind.Null?null:r.GetProperty(k).GetInt64();
  var stamp=Value("server");bool valid=stamp.HasValue && stamp.Value>=server && stamp.Value<=utc && utc-stamp.Value<=5000;
  if(stamp.HasValue)server=Math.Max(server,stamp.Value);
  if(Value("bid") is long b){bid=b;bt=t;bs=valid&&!first?stamp!.Value:-1;}
  if(Value("ask") is long a){ask=a;at=t;ass=valid&&!first?stamp!.Value:-1;}
  first=false;
 }
 bool healthy=Healthy(t,utc);
 if(decision.HasValue){
  if(!healthy || !priorHealthy)Censor(t,"UNOBSERVED_OR_INVALID_PATH");
  else if(!entry.HasValue){
   if(t>decision.Value+1000)Censor(t,"ENTRY_TIMEOUT");
   else if(kind=="spot" && t>=decision.Value+250){entry=t;ep=direction>0?ask:bid;}
  }else if(t>entry.Value+2500)Censor(t,"EXIT_TIMEOUT");
  else if(kind=="spot" && t>=entry.Value+2000){
   long xp=direction>0?bid:ask;
   episodes.Add(new {decision,direction,entry,exit=t,entry_price=ep,exit_price=xp,gross_raw=checked(direction*(xp-ep))});decision=null;entry=null;
  }
 }
 while(flow.Count>0 && flow.Peek().Time<t-1000)flow.Dequeue();
 if(kind=="depth"){
  if(!firstDepth.HasValue){firstDepth=t;flow.Clear();continue;}
  var q=r.GetProperty("quotes").EnumerateArray().ToArray();var ids=new HashSet<ulong>();bool valid=q.Length<=10000;
  foreach(var x in q){int side=x.GetProperty("side").GetInt32();long size=x.GetProperty("size").GetInt64();long price=x.GetProperty("price").GetInt64();
   valid&=ids.Add(x.GetProperty("id").GetUInt64()) && (side==1||side==-1) && size>0 && price>0;}
  if(!valid){flow.Clear();if(decision.HasValue)Censor(t,"AMBIGUOUS_DEPTH_MESSAGE");}
  else {
   foreach(var x in q)flow.Enqueue((t,x.GetProperty("side").GetInt32(),x.GetProperty("size").GetInt64()));
   if(flow.Count>100000)throw new ArgumentException("FLOW_RESOURCE_CAP");
   if(!decision.HasValue && t>=blocked && t-firstDepth.Value>=5000 && healthy && flow.Count>=10){
    decimal b=flow.Where(x=>x.Side==1).Sum(x=>(decimal)x.Size),a=flow.Where(x=>x.Side==-1).Sum(x=>(decimal)x.Size);
    int sign=b>=3m*a && a>0m?1:a>=3m*b && b>0m?-1:0;
    if(sign!=0){decision=t;direction=sign;entry=null;blocked=checked(t+5000);signals++;decisions.Add(new {t,direction});}
   }
  }
 }else if(kind!="spot")throw new ArgumentException("SOURCE_KIND");
}
if(decision.HasValue)Censor(last,"TERMINAL_UNSETTLED");
var result=new {schema="mxm.depth-announcement-pressure.csharp.v1",signals,episodes,censors,decisions,
 input_sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[0]))).ToLowerInvariant(),
 evaluator_sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(typeof(Program).Assembly.Location))).ToLowerInvariant(),
 capital_replay=false,broker_fills=false,net_edge=false,hard21=false};
File.WriteAllText(args[1],JsonSerializer.Serialize(result));
