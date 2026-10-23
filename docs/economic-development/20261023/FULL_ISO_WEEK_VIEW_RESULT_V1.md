# Full requested ISO UTC week VIEW source — native result V1

Native run **39917922508 SUCCESS**, installation trigger
`e65fea6321d84acce19c0a965f7814ca6d842183`, pinned code
`120db3391ed1f4105120274b73a9259690eeeb64`, original decoder/transport
`d2fae5641b759b1c8c24161d83d62d39e104eafd`.

- Producer **120295856025 SUCCESS**, existing Pepperstone environment, explicit
  VIEW scope/account fingerprint, zero orders; 210 historical + 2 metadata calls.
- Independent custody **120296341940 SUCCESS**, other runner/environment; checked
  successful native producer, both exact checkouts, receipt in native logs, exact
  cipher, every raw message/account/correlation/page and disjoint interval tree.
- Fixed requested interval: **2026-09-07 00:00:00 inclusive to 2026-09-14 00:00:00
  exclusive UTC**, ISO **2026-W37**, strictly DEVELOPMENT.
- **342,248 BID + 343,226 ASK = 685,474 original quote events**. Complete provider
  pages for both sides under the registered interval/caps. No missing page is
  interpolated or treated as a tradable flat price.
- **277,457 same-ms cross-side groups have unknown event precedence**. Zero crossed
  snapshots under the decoder's stated causal mark convention is not fill proof.
- Current metadata is captured, not historical fee/margin/FX/swap authority.
  No new economic evaluation, strategy trial, confirmation, broker execution
  result or HARD21 certificate. EUR200 accounting and canonical ledger unchanged.

This extends the authentic BID/ASK source from the original four-hour window to
one full requested ISO interval. It does not establish continuous liquidity,
market session completeness, executable price arrival order, 21 actual entries,
robust multi-week/multi-symbol edge or native cTrader recovery.

## Durable custody (no plaintext market data)

Original GitHub producer artifact **12486315900**, `week-chronology-39917922508`:
ZIP **4,934,629 bytes**, SHA256
`dbbda51f6419b8f5d576044a034b4f28200476f9ebf9be633463ceab0a004906`.
Exact ZIP is preserved in 151 independently hashed 32KiB parts plus manifest at
`docs/economic-development/20261023/native-week-39917922508/`.
Ciphertext commitment:
`2403c74dfd81ab410f9b9c3bdabf4f3d5a5a4df0133cd0adc03933a364d539b6`.
Private decoded input commitment (not plaintext):
`8dde8355c79f3f379bf14f1fd47a8ed5815646cafbcfc287762fb68c2c2e7b51`.

Original independent custody artifact **12486460595**, ZIP SHA256
`2c5971cf7fa61cf8372c9d32e0be1d14237b71113b57c7ba18c1e17ff94f1b1e`,
is preserved exactly in `cold-artifact.zip.b64`, together with its exact public
`cold.json` (SHA256
`fff8965b686d62695ba1dfb410f3cdf4985e22ca5455f3ce76af8a394d48a1cc`).
No keys, credentials, raw account IDs or plaintext quotes are stored in Git.

Offline recovery, no token/key/network:

```
python3 -m research_core_v4.laboratory.durable_week_chronology --out verification/week-chronology
```

The byte-only decoder retains its original 2MB/16KiB defaults. The new pinned
source explicitly selects an 8MiB/256-part/32KiB budget; global hard bounds remain
finite. Original archive tests still pass; new tests check exact GitHub digest,
source/cold binding, corruption, order, self-consistent rehash replacement,
conflicting outputs and unchanged legacy default refusal. A successful offline
restore proves ciphertext/receipt preservation, not a new private replay.

## Next evidence needed

The original C# quote bridge remains pinned to its original 28,212-event source;
it has not silently accepted the new capture. A separately prospective finite
C# week evaluation must bind the new wire source, register all economic modeling
assumptions and reconcile the full EUR200 ledger independently before reporting
any modeled weekly outcome. Its costs, margin, financing and fills must retain
all unresolved classifications. The new interval is DEVELOPMENT, never an
independent confirmation period. Native cTrader callback acceptance from PR139
also remains open; this acquisition does not replace it.
