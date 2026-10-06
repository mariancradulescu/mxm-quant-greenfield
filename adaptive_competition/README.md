# ADAPTIVE_COMPETITION_POLICY_V1

This is one deterministic, causal, conditional development economic policy.
It is not a certified finalist or a trading cBot. There is no broker client,
order surface, AI call, external market feed, or runtime randomness.

Recover from `state/ADAPTIVE_COMPETITION_CURRENT_STATE.json`, then verify the
frozen spec, implementation hashes, input archive hashes, opening lock, and
raw result. Preserve exact TRIAD V7 and every historical authority.

Authorized agent execution (the user is not a GitHub operator):

1. Materialize the two primary archive identities listed in the frozen spec
   and the original task. Keep plaintext broker archives out of public Git.
2. `OPENBLAS_NUM_THREADS=1 python -m adaptive_competition.data --data DATA --cache CACHE`
   verifies original bytes and constructs the complete 145-series surface.
   If its raw-series pass is complete but context writes are interrupted,
   `python -m adaptive_competition.finish_context` resumes at the fixed local
   `../data` and `../cache` directories and proves exact context equality.
3. Run the mechanical tests. Freeze and publish all pre-outcome laws.
4. `python -m adaptive_competition.run inner --cache CACHE` uses only days
   0–91, two complete configurations, and a continuous validation account.
5. Publish the selected exact frozen spec and a separate hash-bound outer ARM.
6. `python -m adaptive_competition.run outer --cache CACHE` opens exactly once,
   replaying days 91–366 chronologically with EUR200 continuous capital.
7. Persist the raw result before `python -m adaptive_competition.interpret`.
   Publish current state and budget effect, then stop for independent audit.

An existing opening lock without a raw result is an interrupted attempt, not
permission to launch a new policy or blindly reopen the outer replay.
No protected forward, confirmation, or new acquisition is authorized.

The archived primary bytes are already durably available under persistent
file identities `file_0000000028e482109c3e700bb6cfef6c` and
`file_0000000030c88210a1d7d3bb5b80afe9`. This code and its artifacts can be
inspected or run by a subsequent authorized deterministic executor; no
ChatGPT Work runtime is part of the policy's scientific or production law.

The cost surface is evidence-limited, not selected by old profit. It uses
prefix authentic fresh-spread maximum times two, a causal range delay bound,
and an explicitly conditional current-commission/margin scenario. Neither
M5 OHLC nor current metadata is claimed as exact historical bid/ask, fills,
financing, conversion, or margin truth. Unmeasured costs permit information
learning but lock execution. Unexpected financing or conversion gaps are
explicit limitations and cannot certify realizable alpha.

HARD21 is a floor for final certification only. There is no upper trade cap,
count-dependent threshold adjustment, or filler-trade mechanism.
