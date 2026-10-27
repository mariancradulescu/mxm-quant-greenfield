using System.Text.Json;
using System.Globalization;
using System.Security.Cryptography;
using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));
var root=doc.RootElement;var rows=new List<object>();var seen=new HashSet<long>();
string[] calendar={"swapPeriod","swapTime","swapRollover3Days","skipSWAPPeriods","chargeSwapAtWeekends"};
int? Integer(JsonElement p,string k)=>p.TryGetProperty(k,out var v) && v.ValueKind!=JsonValueKind.Null ? int.Parse(v.ToString(),CultureInfo.InvariantCulture):null;
bool? Boolean(JsonElement p,string k)=>p.TryGetProperty(k,out var v) && v.ValueKind!=JsonValueKind.Null ? v.GetBoolean():null;
int? account=Integer(root,"account_type");bool? swapFree=Boolean(root,"swap_free");
foreach(var item in root.GetProperty("rows").EnumerateArray()){
 long id=item.GetProperty("symbol_id").GetInt64();if(id<=0 || !seen.Add(id))throw new ArgumentException("SOURCE_IDENTITIES");
 var f=item.GetProperty("full");string classification="DATA_UNRESOLVED";int? sign=null;
 bool? enabled=Boolean(item,"enabled"),shortable=Boolean(f,"enableShortSelling");int? mode=Integer(f,"tradingMode"),kind=Integer(f,"swapCalculationType");
 if(!item.GetProperty("identity_available").GetBoolean())classification="IDENTITY_UNAVAILABLE";
 else if(enabled==false || mode is 1 or 2 or 3 || shortable==false || account is 1 or 2 || swapFree==true)classification="CURRENT_PAIR_UNAVAILABLE";
 else if(enabled==true && mode==0 && shortable==true && account==0 && swapFree==false && kind is 0 or 1 or 2 &&
  f.TryGetProperty("swapLong",out var l) && f.TryGetProperty("swapShort",out var s) &&
  double.TryParse(l.ToString(),NumberStyles.Float,CultureInfo.InvariantCulture,out double a) &&
  double.TryParse(s.ToString(),NumberStyles.Float,CultureInfo.InvariantCulture,out double b) && double.IsFinite(a) && double.IsFinite(b)){
  sign=a> -b?1:a< -b?-1:0;classification=sign>0?"POSITIVE_DISPLAYED_PAIR_RATE":"NONPOSITIVE_DISPLAYED_PAIR_RATE";
 }
 rows.Add(new {symbol_id=id,classification,pair_rate_sign=sign,calendar_fields_present=calendar.Where(k=>f.TryGetProperty(k,out _)).ToArray()});
}
string Hash(byte[] b)=>Convert.ToHexString(SHA256.HashData(b)).ToLowerInvariant();
File.WriteAllText(args[1],JsonSerializer.Serialize(new {rows,input_sha256=Hash(File.ReadAllBytes(args[0])),evaluator_sha256=Hash(File.ReadAllBytes(typeof(Program).Assembly.Location)),capital_replay=false,broker_fills=false,net_edge=false,hard21=false}));
