# Durable native source and causal product reception — 23 October 2026

B–E continuation, original repository and custody. No new mandate, authority bootstrap, provider, broker request, market order or Cloud activation.

## Material execution completed
PR #132 merged as `efa914348aebf5d42cdb539a36f9d5fcdebaf12a`. Five no-secret native GitHub checks passed, including actual cTrader `.algo` compilation and shared product/replay intent tests. Protected source regression `39900816580`, job `120241958030`, SUCCESS. The separate exit-lifecycle regression `39900816596` also completed SUCCESS; its unchanged exploratory matrix is not a new scientific finding.

The source/replay model still returns **seven modeled entries, six exits, EUR198.318181818… cash, EUR199.436363636… marked equity, one open position**, zero full ISO UTC weeks. Independent Python Decimal terminal cash/equity differences are below one micro-euro. The stricter shared intent lifecycle did not alter this already-exposed four-hour source's account arithmetic. It repairs product/replay routing and bounds stale signals; no native DEMO callback/execution/recovery parity is claimed.

## Retention defect and exact-byte preservation
The existing protected portfolio workflow depended on `actions/download-artifact` from original source run `39660692230`. Its artifact expires **19 January 2027**. The PR #131 and #132 proof artifacts expire **22 November 2026**. Running the workflow before those dates did not remove the dependency.

The original source GitHub ZIP, artifact `12373706797`, is now retained as bounded base64 parts under `native-chronology-39660692230/`, with an index recording original native run/head/decoder, byte counts, per-part and per-member SHA256. Original GitHub ZIP SHA256: `354b16bd329335314996d1334cab37b7029b5aa883ea93f2bde0bbc58c38650a`. Original encrypted quote member SHA256: `f1d828d94b304e2af1f310701f92dcb31db935a8db7fc3f8772087adf5499346`. Only existing ciphertext and the already-public producer receipt are present. There was no decryption or re-encryption during archival.

The exact protected result ZIPs for `39899227676` (PR #131) and `39900816580` (PR #132) are retained under `protected-evidence/<run>/` with the same byte-preserving index/parts approach. Their native GitHub archive SHA256 values are independently pinned in the no-secret regression. Each contains the existing encrypted detailed result and its original public receipt. Detailed trades remain encrypted to the unchanged original recipient.

## Executable restoration
`python3 -m research_core_v4.laboratory.durable_native_chronology --out verification/r3-chronology` reconstructs the exact original archive offline; checks its externally pinned GitHub ZIP digest, every part/member, ciphertext digest and original receipt/run identity; writes only the two known original filenames. It refuses traversal, reordered/corrupt parts, forged source labels, digest replacement, output symlinks or conflicting existing files. It needs no key, broker, App or Actions artifact access.

The existing protected C# workflow now uses that restoration before the unchanged sealed native decoder and independent accounting verifier. It still decrypts only inside the existing authorized custody. Original market bytes, decryption key, immutable decoder source and scientific exposure are unchanged. The archival change must pass native required CI and its post-merge protected cold-to-C# execution before being described as verified end to end. Offline tests verify authentic archived bytes plus corruption/provenance negatives; they do not certify native executions.

## Current scientific status
**NO_QUALIFIED_CANDIDATE; HARD21 UNPROVEN; full product reception OPEN.** No new alpha trial or canonical V2/C033 ledger mutation. This preserves reproducibility, not profitability. It does not extend the four-hour EURUSD support to multi-symbol whole weeks, certify hypothetical cost/margin/FX inputs, or prove stop execution and DEMO/Cloud recovery. These are the next material economic/operational frontiers. OWNER actions required for this completed work: NONE.
