using System.Text.Json;
using System.Text.Json.Serialization;
static class SupportTopology {
 sealed record Packet(int Ordinal,int[] Slots);
 sealed record Cell(int Ordinal,int Block,int Bars,int LongestRun,int Lookback,int Hold,
  int CausalDecisions,int OutsideArchive,int InArchive,int Complete,int MissingEntry,int MissingExit,int MissingInterior);
 static void Need(bool ok){if(!ok)throw new ArgumentException("SUPPORT_TOPOLOGY_TIME_ONLY_INPUT");}
 static readonly JsonSerializerOptions Options=new(){PropertyNameCaseInsensitive=true,UnmappedMemberHandling=JsonUnmappedMemberHandling.Disallow};
 public static void Main(string[] args) {
  Need(args.Length==2);var output=new List<Cell>();var ids=new HashSet<int>();long total=0;
  foreach(string line in File.ReadLines(args[0])) {
   var p=JsonSerializer.Deserialize<Packet>(line,Options)!;
   Need(p!=null && p.Ordinal>=1 && p.Ordinal<=1576 && ids.Add(p.Ordinal) && p.Slots!=null && p.Slots.Length<=8064);
   var present=new bool[8064];int previous=-1;
   foreach(int t in p!.Slots){Need(t>previous && t>=0 && t<8064);present[t]=true;previous=t;total++;}
   var prefix=new int[8065];for(int t=0;t<8064;t++)prefix[t+1]=prefix[t]+(present[t]?1:0);
   bool Full(int lo,int hi)=>lo>=0 && hi<8064 && prefix[hi+1]-prefix[lo]==hi-lo+1;
   for(int block=0;block<4;block++) {
    int lower=block*2016,upper=lower+2016,run=0,longest=0;
    for(int t=lower;t<upper;t++){run=present[t]?run+1:0;longest=Math.Max(run,longest);}
    foreach(int horizon in new[]{1,12,288}) {
     int causal=0,outside=0,inside=0,complete=0,entry=0,exit=0,interior=0;
     for(int d=lower;d<upper;d++) {
      if(!Full(d-horizon,d-1))continue;causal++;
      int a=d+1,b=a+horizon;
      if(b>=8064){outside++;continue;}inside++;
      if(!present[a])entry++;if(!present[b])exit++;
      if(horizon>1 && !Full(a+1,b-1))interior++;
      if(Full(a,b))complete++;
     }
     output.Add(new(p.Ordinal,block+1,prefix[upper]-prefix[lower],longest,horizon,horizon,causal,outside,inside,complete,entry,exit,interior));
    }
   }
  }
  File.WriteAllText(args[1],JsonSerializer.Serialize(new{Packets=ids.Count,Rows=total,Cells=output}));
 }
}
