using System;
using Mxm.Replay;
int tests=0;
void Eq(bool ok,string why){if(!ok)throw new Exception("MXM_AFFORDABLE_VOLUME_"+why);tests++;}
decimal? Find(decimal min,decimal max,decimal step,decimal wanted,Func<decimal,bool> permit)=>
 MxmNativeVolumeSearch.LargestAffordable(min,max,step,wanted,permit);
Eq(Find(100m,5000m,100m,1000m,v=>v<=600m)==600m,"DOWN_TO_FEASIBLE");
Eq(Find(100m,5000m,100m,1000m,v=>v<=1000m)==1000m,"MAX_REQUEST");
Eq(Find(100m,5000m,100m,999m,v=>v<=999m)==900m,"NO_ROUND_UP");
Eq(Find(100m,5000m,100m,100m,v=>v==100m)==100m,"MIN_EQUAL");
Eq(Find(100m,5000m,100m,99m,v=>true)==null,"BELOW_MIN_NEVER_RAISE");
Eq(Find(100m,5000m,100m,1000m,v=>false)==null,"NO_VALID");
Eq(Find(100m,5000m,100m,1000m,v=>v<100m)==null,"MIN_UNAFFORDABLE");
Eq(Find(100m,5000m,0m,1000m,v=>true)==null,"BAD_STEP");
Eq(Find(100m,50m,1m,100m,v=>true)==null,"BAD_MAX");
Eq(Find(0m,100m,1m,100m,v=>true)==null,"BAD_MIN");
Eq(Find(100m,500m,10m,99m,v=>true)==null,"BAD_CAP");
Eq(Find(100m,decimal.MaxValue,.000000001m,decimal.MaxValue,v=>true)==null,"HUGE_LATTICE");
Eq(Find(100.25m,105m,.25m,102.11m,v=>v<=101.5m)==101.5m,"DECIMAL_GRID");
Eq(Find(100m,5000m,100m,250m,v=>v<=500m)==200m,"PARTIAL_GRID");
decimal equity=200m,freeMargin=200m;
bool Afford(decimal volume) {
 decimal margin=volume*.1m,stop=volume*.0015m,commission=.02m;
 return MxmCapitalAdmission.Check(equity,freeMargin,margin,commission,
    .4m,120m,0,1)==MxmCapitalAdmission.Admit &&
  MxmStopRiskAdmission.Check(equity,0m,stop,.01m,.2m,0m)==MxmStopRiskAdmission.Admit &&
  MxmOwnerEntryEnvelope.Check(freeMargin,margin,commission,stop,.2m)==MxmOwnerEntryEnvelope.Admit;
}
Eq(Find(100m,1000m,100m,1000m,Afford)==700m,"STRICT_SHARED_EUR_ACCOUNT_EXACT_GRID");
Eq(!Afford(800m),"STRICT_CASH_RESERVE_REJECTS_80_PLUS_FEE");
Eq(!Afford(1300m),"OWNER_RISK_REJECTS_EXCESS");
int calls=0;
var many=Find(100m,9999999900m,100m,9999999900m,v=>{calls++;return v<=600m;});
Eq(many==600m && calls<=70,"BOUNDED_NO_FULL_SCAN");
Console.WriteLine("MXM_NATIVE_BOUNDED_VOLUME_ARTIFICIAL_GATES_PASS "+tests);
