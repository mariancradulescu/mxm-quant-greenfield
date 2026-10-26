using System;
using System.Collections.Generic;
namespace Mxm.Replay {
public sealed record MxmCommissionFloor(decimal KnownPerFillFloorEur,bool CompleteFeeKnownWithoutPrice,string[] Unresolved);
// Necessary lower bound at exact broker MINIMUM wire volume. It never labels
// an unresolved fee as zero or equates passing a fee hurdle with an eligible trade.
public static class MxmCommissionFloorCalculator {
 public static MxmCommissionFloor Compute(MxmCommissionTerms terms,IReadOnlyDictionary<string,decimal> fixedCostFx){
  if(!MxmInstrumentCommission.Valid(terms) || fixedCostFx==null)throw new ArgumentException("FLOOR_TERMS_OR_FX");
  foreach(var p in fixedCostFx)if(p.Value<=0 || p.Key=="EUR" && p.Value!=1)throw new ArgumentException("FLOOR_COST_FX");
  var unresolved=new SortedSet<string>();
  decimal Convert(decimal value,string asset){
   if(value==0)return 0m;
   if(fixedCostFx.TryGetValue(asset,out var fx))return checked(value*fx);
   unresolved.Add("MISSING_COST_FX_"+asset);return 0m; // Unknown component; lower bound only.
  }
  decimal minimum=Convert(terms.Minimum,terms.MinimumAsset),basis=0m;
  if(terms.Kind==2 || terms.Kind==4)
   basis=Convert((decimal)terms.MinimumVolume/terms.LotSize*terms.Rate,terms.Kind==2?"USD":terms.QuoteAsset);
  else if(terms.Rate!=0)unresolved.Add("PRICE_DEPENDENT_BASE_FEE");
  return new(Math.Max(minimum,basis),unresolved.Count==0,System.Linq.Enumerable.ToArray(unresolved));
 }
}
}
