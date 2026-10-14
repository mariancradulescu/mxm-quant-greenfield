using System;
using System.Linq;
using System.Collections.Generic;
public static class Pressure {
 public static int Side(double[][] b) {
  if(b.Length!=12)return 0;double u=b.Max(x=>x[1]),l=b.Min(x=>x[2]),r=u-l;if(r<=0)return 0;var signals=new List<int>();
  foreach(int side in new[]{1,-1}){
   bool[] contact=b.Select(x=>side==1?x[1]>=u-.1*r:x[2]<=l+.1*r).ToArray();var clusters=new List<int[]>();
   for(int i=0;i<12;i++)if(contact[i]){if(i>0&&contact[i-1])clusters[^1][1]=i;else clusters.Add(new[]{i,i});}
   if(clusters.Count<3||clusters[^1][1]!=11)continue;double[] d=new double[2];
   for(int j=0;j<2;j++){var left=clusters[clusters.Count-3+j];var right=clusters[clusters.Count-2+j];var middle=b.Skip(left[1]+1).Take(right[0]-left[1]-1);d[j]=side==1?u-middle.Min(x=>x[2]):middle.Max(x=>x[1])-l;}
   double c=b[^1][3];bool inside=side==1?u-.25*r<=c&&c<u-.02*r:l+.02*r<c&&c<=l+.25*r;
   if(d[0]>=.2*r&&d[1]>=.1*r&&d[1]<=.75*d[0]&&inside)signals.Add(side);
  }return signals.Count==1?signals[0]:0;
 }
}
