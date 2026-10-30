# Source -> shared portfolio policy -> one funded C# account -> native observation

Continuation of OWNER's 29 October fundamental redesign and 30 October autonomous continuation. Baseline: official PR271, `c615f5c23086af19edd0404703a08165e40af0d6`. This is neither a restart nor a new authority. No LIVE/DEMO orders, Cloud activation, new provider, new credentials or changes to OWNER risk limits.

## Material architectural change

The research unit is a joint portfolio target, rather than three independent strategy PnLs added together. The same pure C# policy consumes timestamped completed H1 bars across the roster. It ranks relative directional efficiency against the cross-market median, maintains one selected inventory target, or abstains. The frozen prospective definition is `PORTFOLIO_PROGRAMME_20261030.json`; it is one new dependent V4 procedure, not a parameter grid or a retest of a closed identity.

The existing `Laboratory` now reserves this V4 policy explicitly, preserving all legacy V2 accounting. The authenticated source adapter loads four pinned encrypted Pepperstone originals and checks fixed exposure-window support before evaluating the policy. It then compares the C# decisions against an independent full-array Python implementation, binds the complete event feed and candidate identity, and uses PR271's shared account operator. A single EUR200 cash account, position slot and risk budget govern all three instruments. Previously selected inventory closes before a different selected symbol's execution quote, by the already-known target rather than future prices. Unchanged targets retain inventory; HARD21 never forces turnover.

Each account chunk runs in a fresh C# process and restores the same account capsule, positions, pending intentions and exact event ordinal. The programme registry is also restored between registration and account execution. Original policy output is encrypted before parity checks, and original account chunks are encrypted before result validation. A later failure cannot authorize replaying an already observed economic outcome. The final encrypted package preserves source proofs, policy bytes, complete scenario feed, original account chunks/capsules, programme state and independent ledger checks. Cold readback uses these saved originals without model replay.

The existing native cBot includes this exact policy through an optional **observation-only** adapter, disabled by default. It cold-builds state from H1 callbacks, emits diagnostic targets and cannot call the broker mutation or intent-storage paths. Enabling the policy outside native observation mode stops the robot. This establishes code integration, not actual Cloud reception, trading permission or cold recovery of learned native policy state.

## Economic contract and limitations

Initial cash is exactly EUR200 once. Native minimum volumes and dated margin snapshots are checked against the conserved September capture: AUDUSD 1000 base units, Copper 20 units, SpotCrude 1 unit. These are units, not EUR1000 initial capital. Existing EUR80 ticket margin, EUR120 free reserve, 1% account stop-risk estimate and EUR2 new-loss envelope remain applied by C#.

The August H1 prices are authentic data; constructed bid/ask, intrabar chronology, slippage, fixed commissions, contemporaneous EUR conversion and historical margin applicability are **scenario assumptions**. Intraday flat inventory justifies zero funding only within that declared scenario. No historical fills or complete historical trading costs are certified. The process preserves missing source cells and stops before policy evaluation if the fixed exposure windows are incomplete; it does not drop losing signals based on future availability.

The policy uses twelve-hour endpoints and at least nine truly adjacent hourly price changes. It does not replace missing hours by adjacent array elements. Thresholds, roster, session, cost assumptions, stop distances, one-hour action delay, target selection and tie-breaking are frozen before the first authentic outcome. This is distinct from the closed single-market six-bar regimes, impulse rule, residual fade, sign-context learner, pooled regression and Copper-to-AUD shock transfer; no general academic novelty is claimed.

The same EUR200 cash baseline is the comparison. Nonpositive net closes this identity without promotion or retuning. Positive net is only an exposed DEVELOPMENT scenario result, requiring sensitivity and independent validation before any claim of advantage. Weekly/monthly observations do not invent exact calendar-boundary marks. Actual broker HARD21, robust NET edge and native Cloud operational qualification remain unproven.

## Verification and execution discipline

Before custody access: freeze code hashes; compare captured minima; exercise missing-data rejection, V4 budget reservation without V2 changes, inline-source rejection, native no-order gates, independent C#/Python decisions, future-price perturbation, and a full artificial three-market account with chunked-versus-uninterrupted equality. Existing gateway CI also compiles the actual native product and runs its regressions.

The Actions programme starts only after a reviewed official merge, the two existing protected CI workflows passing, original OWNER anchor verification, exact current HEAD, and a first-run inventory showing no previous push outcome. It is bounded, read-only, uses the existing custody environment and integrated laboratory concurrency group, and does not automatically retry. Only public verdicts/provenance and encrypted economic details are uploaded. Authentic execution status is recorded separately after the first result; this document does not predeclare success.
