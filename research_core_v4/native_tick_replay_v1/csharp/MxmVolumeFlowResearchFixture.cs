using System;
using Mxm.Replay;
static class Program {
 static void Require(bool v,string m){if(!v)throw new Exception("FLOW_RESEARCH_FAIL_"+m);}
 static int Run(int sign) {
  var k=new MxmVolumeFlowKernel();
  var t=new DateTime(2026,8,25,10,0,0,DateTimeKind.Utc);
  int last=0;
  for(int i=0;i<12;i++){
   decimal o=100m+sign*(decimal)i*0.03m;
   decimal c=o+sign*(i<6?0.01m:0.25m);
   last=k.OnCompletedBar(t.AddMinutes(5*i),o,Math.Max(o,c)+0.01m,Math.Min(o,c)-0.01m,c,i<6?10:30);
   if(i<11)Require(last==0,"WARMUP");
  }
  Require(k.CompletedBars==12,"COUNT");
  Require(last==sign,"FLOW_DIRECTION");
  k.OnCompletedBar(t.AddMinutes(65),100m,100m,100m,100m,10);
  Require(k.CompletedBars==1 && k.LastSignal==0,"DISCONTINUITY_COLD_REWARM");
  return last;
 }
 static void Main(){
  Require(Run(1)==1 && Run(-1)==-1,"DIRECTIONS");
  var k=new MxmVolumeFlowKernel();
  DateTime t=new(2026,8,25,10,0,0,DateTimeKind.Utc);
  k.OnCompletedBar(t,100m,101m,99m,100m,1);
  try{k.OnCompletedBar(t,100m,101m,99m,100m,1);throw new Exception("DUPLICATE_ADMITTED");}
  catch(ArgumentException){}
  try{k.OnCompletedBar(t.AddMinutes(5),100m,100m,100m,101m,1);throw new Exception("BAD_OHLC_ADMITTED");}
  catch(ArgumentException){}
  Require(k.CompletedBars==1,"INVALID_BAR_NOT_ADVANCING_STATE");
  Console.WriteLine("MXM_VOLUME_FLOW_SINGLE_CBOT_RESEARCH_FIXTURE_SUCCESS");
 }
}