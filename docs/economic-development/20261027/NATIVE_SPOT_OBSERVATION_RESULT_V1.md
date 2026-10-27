# Native spot source reception and current continuation — 27 October 2026

[Run 40455704891](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/40455704891), attempt one, official source `d16db0a9e40ca2f48f8b9f0d483ca3b131d173e1` (PR #211): producer job **122028419045 SUCCESS**, separate custody job **122030445035 SUCCESS**. Fixed protocol and diagnostic partition were installed before connection, after two required CI suites passed. All fifteen artificial source-profile/scope/native protobuf tests executed successfully in CI without skips. One registered VIEW source connection, no historical request, order or model.

The exact fixed panel was authenticated as EURUSD/1, GBPUSD/2 and SpotCrude/250; native metadata and minimum-volume margin responses were captured before subscription. VIEW permission, existing account fingerprint, Pepperstone/EUR identity, source/policy/partition/correlation/duration and every recorded native event were independently read back in the custody job. The profiling algorithm is shared; this is separate native readback, not an independent scientific implementation or Robot runtime reception.

## Measured observational source result

| Instrument | Received spot messages | Consumer-valid | Unavailable | Separate healthy observation stretches | Stretches with observed span >=5 min |
|---|---:|---:|---:|---:|---:|
| EURUSD | 336 | 179 | 157 | 52 | **0** |
| GBPUSD | 482 | 440 | 42 | 41 | **0** |
| SpotCrude | 322 | 321 | 1 | 8 | **0** |
| Total | **1,140** | **940** | **200** | **101** | **0** |

The exact preregistered contract required subsequent observations of both sides after the initial snapshot, a positive book, server/receipt side age and healthy inter-event gaps <=5 seconds, and a >=300-second observed span by local monotonic time. Initial snapshots, locked/crossed books and stale/unverified sides were retained. Category counts can overlap and are not trade counts. EURUSD had153 locked/crossed-category events, GBPUSD37; those categories were not separately split. SpotCrude had only its initial unavailable event, but its healthy observations formed eight stretches because of gaps: a high fraction of valid received messages is not proof of uninterrupted observation.

This six-minute pilot and the historical W37 census measure different clocks, windows and grouping contracts. The earlier **six** historical GBPUSD five-minute stretches remain authentic and unchanged. They cannot be substituted for this pilot's **zero**, nor vice versa. Neither sample establishes a trading edge, executable liquidity, maximum stop loss, whole-week coverage or HARD21. No retrospective threshold/horizon/period/instrument selection or retest of a rejected economic model took place.

## Receipt boundary and representation limits

The registered stream duration completed. A receive deadline closed the connection, with an unfinished trailing frame possible; no unsubscribe ACK was recorded, no reconnect/retry occurred and no tail price/span was invented. The pipeline's accepted flag means bounded source receipt under this declared boundary, not proof of complete continuous feed reception. Server/host clock synchronization, receipt equivalence to native cTrader Robot callbacks and broker fills remain unproven.

The primary preserves native protobuf payloads in envelopes serialized by the pinned native transport. These are the original **saved** producer bytes, not a TCP/TLS packet capture or a claim that outer protobuf serialization preserves arbitrary network field ordering. Source values, message type and correlation are decoded from those native payloads in custody. Public source statistics do not disclose market prices/event times or account identity.

## Exact evidence conservation

`native-spot-40455704891/MANIFEST.json` binds original native run/jobs/head, policy/partition, member hashes, public receipts and both original Actions ZIP artifacts:

- Producer artifact **12712855844**,333898bytes, SHA256 `df7c5d91981340d919e2874d9c0bf2e473600cf13515fde90237cf8cd062bd1e`; contains only original `capture.mxmenc` and `producer.json`.
- Cipher332594bytes, SHA256 `705965ed186b7431963fd72a4ff3e130ccfb0e9de275a371d056be7bbf8379b9`; original private commitment `ad08d81bd89bdfe7815aea3b976275d5e8aa7be3ad6bf8d8efcd41622e5fd5f0`.
- Cold artifact **12712671158**,1238bytes, SHA256 `e2b2c681aa4a255bbacd4be6091039245da2ef6db2e79e7532a63d085d9367fd`; sole original `cold.json`.

Both ZIPs are retained byte-for-byte as Base64; both public receipt copies remain byte-exact. No primary source was decrypted in Work. `python3 -m research_core_v4.laboratory.durable_spot_observation --out <new-directory>` restores only the exact ciphertext/public receipts, without broker, key or model. Four original/corruption/substitution/symlink/conflict tests passed locally; gateway CI now verifies the result before merge. Conservation is not another source collection or research outcome.

The actual entire contact interval **2026-10-27T05:31:01.143636+00:00 through 2026-10-27T05:37:04.067853+00:00**, including all identities whose feature/response windows intersect it, is DEVELOPMENT_SOURCE_QUALITY_ONLY and excluded from confirmation. The original preregistered partition is unchanged; the result partition binds these bounds to the original cold receipt and manifest. Prior protected evidence is neither opened nor relabeled.

## Functional/economic continuation

PR #210 merged `e16049b9ab855aa4d4811d394352cea2ebeae37a` after all five final CI suites succeeded. The actual product now checks consumed-intent expiry and broker identity immediately before MarkSubmitted/ExecuteMarketOrder, after final account/fee/risk calculations. Seven compiled artificial boundary/identity checks passed, together with original cold-process recovery and cTrader package/CLI metadata checks. Earlier CI failures were structural consumers still naming the old fence call; those guards were updated to require the stronger final shared check, retaining their durable-order/recovery assertions. No native orders or callback acceptance are claimed.

The new source route actually works with receipt clocks and native contemporary terms. It does **not** support claiming five-minute continuous observability in this particular pilot. Do not relaunch long-exposure rejected models, relax the guards retrospectively or turn source statistics into a profitability claim. The next economic admission requires a distinct prospective exposure-path/response protocol and explicit dated cost/FX/margin applicability; captured current terms and estimated margins are not September historical charges or executable loss-side FX. Shorter/state-dependent mechanisms and the wider authorized universe remain open questions. A new directional capture and separate confirmation would need their own preregistration; this diagnostic's response-testing prohibition remains binding.

OWNER's continuation after #207–209 remains the same B–E delegation. No authority/custody changes, capital reset, economic trial/outcome, LIVE/DEMO order or Cloud activation. The only new broker activity was this bounded VIEW pilot (eleven business requests: three authentication, seven metadata/margin and one subscription; deadline close without unsubscribe ACK, plus bounded heartbeats). Product completion, robust after-cost edge, HARD21 and native Robot operational reception remain OPEN.
