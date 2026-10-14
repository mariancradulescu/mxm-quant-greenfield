using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Duration {
public static class TimingKernel {
 static Dictionary<string,object> State(string state)=>new Dictionary<string,object>{{"state",state}};
 public static Dictionary<string,object> Compute(long[][] bids,long[][] asks,long entry,bool more){
  if(more)return State("INCOMPLETE_PAGE");
  long lo=(entry-60)*1000,hi=(entry-1)*1000;
  (List<long[]> rows,string error) Clean(long[][] input){
   var found=new SortedDictionary<long,long>();
   foreach(var x in input){if(x[0]<lo||x[0]>hi)continue;if(x[1]<=0)return (null,"INVALID_PRICE");if(found.ContainsKey(x[0])&&found[x[0]]!=x[1])return (null,"AMBIGUOUS_SIDE_MS");found[x[0]]=x[1];}
   var output=new List<long[]>();long? last=null;long changed=-1;
   foreach(var x in found){if(last.HasValue&&last.Value!=x.Value)changed=x.Key;output.Add(new[]{x.Key,x.Value,changed});last=x.Value;}return (output,null);
  }
  var b=Clean(bids);if(b.error!=null)return State(b.error);var a=Clean(asks);if(a.error!=null)return State(a.error);
  if(b.rows.Count==0||a.rows.Count==0)return State("MISSING_SIDE");
  int ib=-1,ia=-1;var path=new List<long[]>();
  for(long sec=entry-45;sec<entry;sec++){
   long now=sec*1000;while(ib+1<b.rows.Count&&b.rows[ib+1][0]<=now)ib++;while(ia+1<a.rows.Count&&a.rows[ia+1][0]<=now)ia++;
   if(ib<0||ia<0)return State("MISSING_PATH_STATE");var bb=b.rows[ib];var aa=a.rows[ia];
   if(bb[2]<0||aa[2]<0)return State("CHANGED_SIDE_WARMUP");
   if(now-bb[2]>5000||now-aa[2]>5000||Math.Abs(bb[2]-aa[2])>2000)return State("STALE_OR_SKEWED_CHANGED_SIDE");
   if(bb[1]>aa[1])return State("CROSSED_PATH");path.Add(new[]{now,bb[1]+aa[1]});
  }
  long first=path[0][1],previous=first;long? changedAt=null;var up=new List<long>();var down=new List<long>();
  foreach(var z in path.Skip(1)){if(z[1]!=previous){if(changedAt.HasValue)(z[1]>previous?up:down).Add(z[0]-changedAt.Value);changedAt=z[0];}previous=z[1];}
  Dictionary<string,object> r;
  if(up.Count<2||down.Count<2)r=new Dictionary<string,object>{{"state","INSUFFICIENT_TWO_SIDED_DURATIONS"},{"up_n",up.Count},{"down_n",down.Count}};
  else{
   double u=up.Average(),d=down.Average(),scale=Math.Max(1.,Math.Max(u,d));double ulp=Math.BitIncrement(scale)-scale;
   double score=Math.Abs(d-u)<=64*ulp?0.:Math.Log(d/u);
   r=new Dictionary<string,object>{{"state","SUPPORTED"},{"score",score},{"model_side",Math.Sign(score)},{"count_side",Math.Sign(up.Count-down.Count)},{"momentum_side",Math.Sign(previous-first)},{"up_n",up.Count},{"down_n",down.Count},{"up_mean_ms",u},{"down_mean_ms",d}};
  }
  r["last_feature_ms"]=hi;return r;
 }
}
}
