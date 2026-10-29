using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Replay;

// Offline, strategy-independent host of the existing account. No broker API.
// The custody caller must authenticate the source and the prior capsule hash.
if(args.Length!=3)throw new ArgumentException("INPUT_PRIOR_OR_DASH_OUTPUT_REQUIRED");
var options=new JsonSerializerOptions {UnmappedMemberHandling=JsonUnmappedMemberHandling.Disallow};
var request=JsonSerializer.Deserialize<Request>(File.ReadAllBytes(args[0]),options)
 ?? throw new ArgumentException("EMPTY_REQUEST");
if(request.Schema!="mxm.shared-funded-account.request.v1" || request.Events.Length==0 ||
 request.Events.Length>100000 || request.ExpectedOrdinal<0 ||
 request.Parameters.ExplicitPolicySha256==null || request.Parameters.NativeSizingScenarioSha256==null)
 throw new ArgumentException("BOUNDED_EXPLICIT_FUNDED_ACCOUNT_REQUIRED");
MxmPortfolioAccountReplay account;
if(args[1]=="-") {
 if(request.ExpectedOrdinal!=0 || request.PriorSha256!=null)throw new ArgumentException("INITIAL_FUNDING_ONLY_ONCE");
 account=new(request.Symbols,request.Parameters);
 account.Run(Array.Empty<MxmAccountFeed>());
} else {
 if(request.ExpectedOrdinal==0 || request.PriorSha256==null)throw new ArgumentException("RESUME_REQUIRES_TRUSTED_CURSOR");
 account=MxmPortfolioAccountReplay.RestoreReplay(File.ReadAllBytes(args[1]),request.PriorSha256,
  request.SourceSha256,request.Parameters,request.Symbols);
}
if(account.NextEventOrdinal!=request.ExpectedOrdinal)throw new ArgumentException("SOURCE_CURSOR_MISMATCH");
var observations=new List<object>();
foreach(var e in request.Events) {
 var before=account.NextEventOrdinal;
 var report=account.Continue(new[]{e},before);
 if(account.NextEventOrdinal!=before+1)throw new ArgumentException("PARTIAL_EVENT_CONSUMPTION");
 observations.Add(new {e.Utc,Ordinal=account.NextEventOrdinal,report.MarkedEquityEur,
  report.FinalCashEur,report.UsedMarginEur,report.AcceptedEntries,report.OpenPositions});
}
var capsule=account.CaptureReplay(request.SourceSha256);
// New paths only: caller cannot overwrite a previous completed outcome.
using(var stream=new FileStream(args[2]+".capsule",FileMode.CreateNew))stream.Write(capsule.Payload);
using(var stream=new FileStream(args[2],FileMode.CreateNew))
 JsonSerializer.Serialize(stream,new {Schema="mxm.shared-funded-account.result.v1",
  request.SourceSha256,request.ExpectedOrdinal,capsule.NextEventOrdinal,
  CheckpointSha256=capsule.Sha256,Account=account.Report(),Observations=observations,
  BrokerFillsProven=false,HistoricalCostsProven=false,Cloud=false,Orders=0},options);

record Request(string Schema,string SourceSha256,string[] Symbols,MxmReplayParameters Parameters,
 long ExpectedOrdinal,string? PriorSha256,MxmAccountFeed[] Events);
