"""Owner-private saved-result readback with exact one-use workflow identity V3."""
import os, json, sys
from datetime import datetime, timezone
from research_core_v4.pepperstone_decision_readback_20261012_v1 import runner_v1 as prior
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt

e = rt.e
P = "research_core_v4/pepperstone_decision_readback_20261012_v1/"

def gate():
    head = os.environ["GITHUB_SHA"]
    auth = json.loads((e.a.ROOT / (P + "EXECUTION_V3.json")).read_text())
    e.w.v2.runtime(head)
    prior.need(auth["authority"] == "OWNER_STANDING_PEPPERSTONE_MACHINE_SIDE_READONLY_20261012", "AUTHORITY")
    prior.need(auth["scope"] == "PREEXISTING_ENCRYPTED_METRICS_DECISION_READBACK_V3", "SCOPE")
    for flag in ("broker_requests", "orders", "protected_forward", "cloud_deployment",
                 "new_external_sources", "scientific_replay", "independent_alpha_promotion"):
        prior.need(auth[flag] is False, "READ_ONLY_SCOPE")
    expected_ref = e.w.old.REPO + "/.github/workflows/mxm-owner-private-decision-readback-20261012-v3.yml@refs/heads/" + e.w.old.BRANCH
    prior.need(os.environ.get("GITHUB_EVENT_NAME") == "push", "PUSH_ONLY")
    prior.need(os.environ.get("GITHUB_WORKFLOW_REF") == expected_ref, "WORKFLOW_IDENTITY")
    prior.need(datetime.now(timezone.utc).isoformat() < auth["expires_utc"], "EXPIRED")
    prior.need(e.w.old.api("git/ref/heads/" + e.w.old.BRANCH)["object"]["sha"] == head, "LIVE_HEAD")
    e.a.ancestor(auth["base_head"], head)
    old, newer = prior.inventory(auth["base_head"]), prior.inventory(head)
    prior.need(all(newer.get(p) == blob for p, blob in old.items()), "FROZEN_FILES")
    for p, digest in auth["bindings"].items():
        prior.need(e.w.old.filehash(p) == digest, "SHA256_SOURCE")
    e.w.old.verify_science()
    prior.need(not e.w.v2.existing_ref(auth["one_use_ref"]), "ALREADY_CONSUMED")
    e.w.old.api("git/refs", {"ref": "refs/tags/" + auth["one_use_ref"], "sha": head})
    return head, auth

if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        prior.selftest()
        print("PASS_STATIC_WORKFLOW_REF_SYNTAX_V3", flush=True)
    else:
        prior.gate = gate
        prior.main()
