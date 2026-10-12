# MXM — authenticated Pepperstone machine-side execution continuity proof
Date: 2026-10-12 UTC. Role: EXECUTOR_DIRECTOR_MXM_QUANT_GREENFIELD.
Scope: forensic read-only execution-path verification; **NOT** a new scientific gate, pilot, or source authorization.
Parent live branch HEAD: `f748244f1d736ea6fc817f68c2ea7c6007e97488`.

## 1. Historically executed native broker path (GitHub API directly checked)
| Run | Source HEAD | Job | GitHub conclusion | Function |
| --- | --- | --- | --- | --- |
| 38150775948 | ea28b538731801d8d88cce4d0021545fe8d8d76a | 114503599917 | success | Authentic catalog/H1 staged data and developmental numeric study |
| 38152844809 | 3801956d497b9d1515650bc70040d660902dd99c | 114509675112 | success | Frozen BID/ASK/FX quote complement without model replay |
| 38197915724 | 962d1afc8918afdc6ad42759c659bc54aa48023e | 114644641381 | success | Broker-native M5 and BID/ASK cost/frequency development |

The last job's **actual public progress log** has M5=3066 and BID_ASK=23996. These are machine-side request counters, not priced trades, outcomes, fills, positive NET, or independent samples. The result was encrypted.

## 2. Execution implementation (verified current byte SHA256 below)
* Workflow `.github/workflows/mxm-cost-frequency-discovery-v1.yml` injects GitHub-scoped `GH_TOKEN` and masked `CTRADER_CLIENT_ID`, `CTRADER_CLIENT_SECRET`, `CTRADER_ACCESS_TOKEN`, `MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM` as runner-only environment secrets. No key values are recovered or published.
* Broker transport: `research_core_v4/native_executable_qualification_v1/runner_v1.py:HistoryReceiptTransport`, inherited `StdlibCTraderTransport` from `research_core_v4/owner_frontier_v1/execute_historical_quotes_v1.py`.
* Broker account auth: `research_core_v4/shallow_m5_support_v2_production.py:authenticate_segment` obtains account list with pre-existing access token, enforces explicit `VIEW` permission, authenticates the stored LIVE account fingerprint, and fails closed on account/auth mismatch. The historical jobs prove this route worked **at execution time**, not that its present-day secrets/token still work.
* Requests: `research_core_v4/cost_frequency_discovery_v1/collector_v1.py` wraps the transport with per-wire request budgets and only permits `ProtoOAGetTrendbarsReq` and `ProtoOAGetTickDataReq` in its data path. Account/catalog/expected-margin requests in the earlier wide collector were likewise read-only. H1/M5 native response envelope, account, period, timestamp, pagination and prices are checked; BID and ASK are distinct sides. Unresolved quotes are never zeros.
* The cost-frequency frozen request caps were M5=4500, BID_ASK=24000, H1=0, NONHISTORY=32; its actual observed M5=3066 and BID_ASK=23996. The fixed period/horizon/selection design is preserved, not reusable as a fresh independent test.

## 3. Private evidence reuse and delivery, without public market data
* `research_core_v4/owner_recovery_v1/runtime_v1.py:load_asset` looks up an exact GitHub Release asset ID, verifies Release digest and downloaded SHA256, decrypts using the preconfigured protected owner key and verified public-key fingerprint, uncompresses in a private temporary directory, and verifies canonical bytes/optional canonical SHA256.
* `research_core_v4/aidr_cost_coverage_v1/frontier_runtime_v1.py:output` stores detailed private result, summary and attestation using authenticated encryption in GitHub prereleases. `research_core_v4/executable_coverage_diagnostic_v1/runner_v1.py:relay` uses gzip, AES-256-GCM and RSA-OAEP-SHA256 wrapping to an already bound session recipient key, posts ciphertext to a release body, and checks GitHub readback.
* Verified GitHub release asset metadata (NOT private plaintext): 409756173 / 631113587 / SHA256 `1c51d7c17deffa385a67590cbe62b75407a81d679d1d61a8a966b13d8dc26fbf` (wide research, 24,148,549 bytes); 409767833 / 631160925 / `12e151fc537e407d3980e91b7232dcf761100d40e40fbedd388e28bdb8603122` (quote completion, 2,012,516 bytes); 410189283 / 632722856 / `45c16cfeaba328f72305a176f6c988663c29895eebd75d7874d8ba2081f4e12d` (cost/frequency, 5,330,022 bytes). Existing owner/session recipients are not the conversation itself.
* Older accepted native M5 source: release 409691500 asset 630847667, ciphertext SHA256 `cf47b70f89525b4472f24c4b1301fcaa432cebe42e72c41b1bc6758c6c15c097`; current frozen cost-source: 408329317 asset 626124478. These were consumed by prior machine-side source-reuse runs and should not be reconstructed absent a necessity.

## 4. One-use proof and exact current reuse restriction
GitHub refs have been fetched as actual remote tags:
* `mxm-wide-greenfield-continuation-one-use-20261011-v1` -> ea28b538731801d8d88cce4d0021545fe8d8d76a
* `mxm-wide-quotes-completion-one-use-20261011-v1` -> 3801956d497b9d1515650bc70040d660902dd99c
* `mxm-cost-frequency-one-use-20261012-v1` -> 962d1afc8918afdc6ad42759c659bc54aa48023e
* `mxm-information-source-readback-20261012-v1` -> 6f5eff8d496d6132a05f3fb7659df8416bfef832

All four scopes are consumed; their runtime gates explicitly deny replay on `existing_ref(one_use_ref)`. Existing workflows are path-filtered to their already-frozen execution-manifest files. Changing those files would violate scientific and source preservation; creating/reusing a different trigger with expanded permissions was NOT authorized. GitHub read APIs do not test current protected secret values. The attached GitHub connector provides no authenticated Pepperstone client, job-dispatch API, or decrypting owner private key to the chat.

Hence: **historically WORKING machine-side broker = VERIFIED; present direct chat access = ABSENT; currently authorized fresh machine-side invocation = NOT ESTABLISHED / OLD ONE-USE CONSUMED; current token/secret validity = NOT TESTED**. Do not conflate these four states.

## 5. Source drift independent check (direct SHA256 of current branch bytes)
| Source file | Verified SHA256 |
| --- | --- |
| .github/workflows/mxm-wide-greenfield-continuation-v1.yml | 3867fbb5245df52d5c8c148b30eff33dae24812b9eef4896aae5eac74f2885b5 |
| research_core_v4/wide_greenfield_v1/runner_v2.py | d50e379d7624e97c4ec0ecc053c0e629f342e1515bf68eaa5783c06d1969ba41 |
| research_core_v4/wide_greenfield_v1/collect_v2.py | 4011782e6bb1cc7df405848d2aedc3ba1c58a2ec3bf44871eefa4cc17e4f21b7 |
| .github/workflows/mxm-wide-economic-completion-v1.yml | 1a104a030e07ed91cd757508576fc390cde860a830e6ad3de5be46f504befbb7 |
| .github/workflows/mxm-cost-frequency-discovery-v1.yml | 9b490d44dc9aad31d56b6d88302fa0a86cd93018d8f1892cfe0b5f2056b46c94 |
| research_core_v4/cost_frequency_discovery_v1/collector_v1.py | 9c15fc507b5f506ead86e6e6f2c09fd659fce0fb31b6f659bff0ad7558f8e48e |
| research_core_v4/cost_frequency_discovery_v1/runner_v1.py | 32388f639f1046a38347a40b06831ca6d80373d7f1f048e46ec1681139da2da1 |
| research_core_v4/owner_recovery_v1/runtime_v1.py | 6fdb8e42e2b582bd6dd14d856549b96b7f3b48f807af7ad64e3647be79a25168 |
| research_core_v4/aidr_cost_coverage_v1/frontier_runtime_v1.py | f7590464c53d61e19ab0db90bd15943c7d1baf0babda56cb25feb48f7773f7b3 |
| research_core_v4/state/V4_ADAPTIVE_SELECTION_HISTORY_V3.json | 95b3fd3a2efebc10bc2745bc7657bd57ae5a67a67051364c70a99368c5bc3664 |
| research_core_v4/state/POST_QUOTE_V4_CLOSURE_LEDGER_V2.json | d5fbfd6bf8d08621b3158cdcc843f39dd911c4af74ea6a3b81f948863ef3e25e |
| research_core_v4/native_executable_qualification_v1/runner_v1.py | 42e60d44d60be017565039fa10e9d373a26b1fa33307f5431f03289119d905c5 |

**12/12 current file bytes MATCH accepted historical frozen bindings.**

## 6. Research decision for this bounded continuation
The 51 historical nodes, subsequent negative exacts, adaptive ledger, current economic witnesses and frozen cost/frequency mechanisms are unchanged. Unlike prior source investigations, this tranche independently verified executable code, artifact objects, four consumed refs, exact logs and current bytes, **not** alternative predictor families. New broker requests 0; pilot candidates enrolled 0; new simulation 0; new quantitative gross, all-cost NET, MAE/MFE and HARD21 results are **NOT MEASURED**, never assigned zero.

The owner explicitly disallows extending the existing machine-side execution/authorization system or rewriting consumed authorities. An additional bounded **execution authority and permissible trigger** would be needed before a fresh encrypted readback or a new one-use DEVELOPMENT strategy can be legitimately started. That does not require new broker credentials, vendors, orders or Cloud deployment, but is not presumed granted. An independently justified causal hypothesis, before-entry source provenance, frozen comparator and EUR200 full risk/cost accounting are further separate preconditions to a *pilot*; no NET proof is demanded before that pilot.

Stop here: **existing machine-side continuity RECOVERED; live re-entry AUTHORITY_UNRESOLVED; no new pilot executed and no negative global Pepperstone inference**. No automatic subsequent campaign.
