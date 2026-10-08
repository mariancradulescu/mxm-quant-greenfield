"""PRIMARY145 GitHub provider preflight: fabricated bytes only; never an ARM.

Durable provider experiment on a *disposable isolated campaign identity*:
one GitHub scratch branch as an append-only record, one GitHub Release as a
verified byte store. No production archive, key, signed payload, science or
real-data path is read. An unsuccessful run leaves receipts for forensics.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

REPO = "mariancradulescu/mxm-quant-greenfield"
BRANCH = "performance-research-v3-20260922"
PREFIX = "research_core_v4/exploratory_dev_v3_provider"
ENV_DENY = ("CTRADER_CLIENT_ID", "CTRADER_CLIENT_SECRET",
            "CTRADER_ACCESS_TOKEN", "CTRADER_REFRESH_TOKEN",
            "MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM")


def run(*args, check=True):
    p = subprocess.run(args, text=True, capture_output=True)
    if check and p.returncode:
        raise RuntimeError(f"command {args[0:3]} failed exit={p.returncode}: {p.stderr[:500]}")
    return p


def gh(*args, check=True):
    return run("gh", *args, check=check)


def api(method, endpoint, *fields, check=True):
    r = gh("api", "-X", method, f"repos/{REPO}/{endpoint}", *fields, check=check)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else (None if check else r)


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def content_get(branch, name):
    obj = api("GET", f"contents/{PREFIX}/{name}?ref={branch}")
    return base64.b64decode(obj["content"]), obj["sha"]


def content_put(branch, name, data, previous_sha=None):
    args = ["-f", f"branch={branch}", "-f", f"message=PRIMARY145 synthetic provider receipt {name}",
            "-f", "content=" + base64.b64encode(data).decode()]
    if previous_sha is not None:
        args += ["-f", f"sha={previous_sha}"]
    return api("PUT", f"contents/{PREFIX}/{name}", *args)


def guard_live(head):
    current = api("GET", f"branches/{BRANCH}")["commit"]["sha"]
    if head != current:
        raise RuntimeError(f"LIVE_HEAD_DRIFT expected={head} observed={current}")


def fabricated_zips(folder, head):
    result = {}
    for part in (0, 1):
        path = folder / f"PRIMARY145_SYNTHETIC_{part+1}.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for i in range(145):
                if i % 2 == part:
                    z.writestr(f"fabricated/{i:03}.txt", f"NOT_MARKET_DATA identity={i} bound_head={head}\n")
        result[path.name] = sha(path.read_bytes())
    return result


def main():
    head = os.environ["GITHUB_SHA"]
    run_id = os.environ["GITHUB_RUN_ID"]
    destination = Path(os.environ["RUNNER_TEMP"])
    result = {"schema": "mxm.primary145.github-provider.synthetic-preflight.v1",
              "source_head": head, "workflow_run_id": run_id,
              "real_arm": False, "real_signature": False, "real_key": False,
              "real_numeric_openings": 0, "broker_requests": 0, "protected_forward_rows": 0,
              "science_modified": False, "status": "BLOCKED", "steps": []}
    branch = f"mxm-primary145-synthetic-{head[:20]}"
    tag = f"mxm-primary145-synthetic-{head[:20]}"
    result["durable_scratch_branch"] = branch
    result["durable_release_tag"] = tag
    try:
        if any(os.getenv(x) for x in ENV_DENY):
            raise RuntimeError("FORBIDDEN_REAL_CREDENTIAL_ENVIRONMENT")
        if len(head) != 40 or any(c not in "0123456789abcdef" for c in head):
            raise RuntimeError("INVALID_SOURCE_HEAD")
        guard_live(head)
        from research_core_v4.exploratory_dev_v2.gate import signed_scope
        scope = signed_scope()
        if len(scope) != 75:
            raise RuntimeError(f"WRONG_SIGNED_SCOPE_{len(scope)}")
        result["signed_dependency_sha256_count"] = 75
        result["steps"].append("LIVE_HEAD_AND_75_FROZEN_SHA256_PASS")

        # Existence of a deterministic campaign branch refuses repeated invocations.
        create = gh("api", "-X", "POST", f"repos/{REPO}/git/refs",
                    "-f", f"ref=refs/heads/{branch}", "-f", f"sha={head}", check=False)
        if create.returncode:
            raise RuntimeError("CAMPAIGN_ALREADY_RESERVED_NO_REPLAY_OR_PROVIDER_FAILURE")
        reservation = canonical({"schema": "mxm.primary145.synthetic-reservation.v1",
                                 "source_head": head, "run_id": run_id,
                                 "consumed": True, "budget_CPU_seconds": 7200,
                                 "accepted_corpus_passes": 1})
        content_put(branch, "RESERVATION_SYNTHETIC_V1.json", reservation)
        if content_get(branch, "RESERVATION_SYNTHETIC_V1.json")[0] != reservation:
            raise RuntimeError("DURABLE_RESERVATION_ROUNDTRIP")
        conflict = gh("api", "-X", "PUT",
                      f"repos/{REPO}/contents/{PREFIX}/RESERVATION_SYNTHETIC_V1.json",
                      "-f", f"branch={branch}", "-f", "message=illegal synthetic replay",
                      "-f", "content=" + base64.b64encode(reservation).decode(), check=False)
        if conflict.returncode == 0:
            raise RuntimeError("NO_REPLAY_CREATE_WITHOUT_SHA_ACCEPTED")
        result["steps"].append("GITHUB_REMOTE_RESERVATION_AND_NO_REPLAY_PASS")

        # Durable byte store: fresh release with exactly two fabricated ZIPs.
        release = gh("release", "create", tag, "--repo", REPO, "--target", head,
                     "--title", f"PRIMARY145 synthetic provider {head[:12]}",
                     "--notes", "Fabricated metadata only. NOT a real ARM or real market corpus.",
                     check=False)
        if release.returncode:
            raise RuntimeError("GITHUB_RELEASE_CREATE_BLOCKED:" + release.stderr[:250])
        digests = fabricated_zips(destination, head)
        for name, digest in digests.items():
            gh("release", "upload", tag, str(destination / name), "--repo", REPO)
            gh("release", "download", tag, "--repo", REPO, "--pattern", name,
               "--dir", str(destination / "redownload"))
            if sha((destination / "redownload" / name).read_bytes()) != digest:
                raise RuntimeError("GITHUB_RELEASE_BYTE_ROUNDTRIP_MISMATCH")
        result["fabricated_archives_sha256"] = digests
        result["steps"].append("TWO_GITHUB_RELEASE_ASSETS_SHA256_ROUNDTRIP_PASS")

        # Synthetic one-pass consumer. Commit a forensic midpoint; disallow
        # reentry, then finish in the SAME invocation. No source replay on crash.
        ids = []
        cp_sha = None
        for name in sorted(digests):
            with zipfile.ZipFile(destination / "redownload" / name) as z:
                for member in z.namelist():
                    raw = z.read(member)
                    if b"NOT_MARKET_DATA" not in raw:
                        raise RuntimeError("NONFABRICATED_INPUT")
                    ids.append(int(member.split("/")[-1].split(".")[0]))
            cp = canonical({"source_head": head, "run_id": run_id,
                            "parsed_fabricated_identities": len(ids),
                            "complete": False, "no_replay": True})
            content_put(branch, "CHECKPOINT_SYNTHETIC_V1.json", cp, cp_sha)
            observed, cp_sha = content_get(branch, "CHECKPOINT_SYNTHETIC_V1.json")
            if cp != observed:
                raise RuntimeError("DURABLE_CHECKPOINT_ROUNDTRIP")
            if content_get(branch, "RESERVATION_SYNTHETIC_V1.json")[0] != reservation:
                raise RuntimeError("RESERVATION_DISAPPEARED")
        if sorted(ids) != list(range(145)):
            raise RuntimeError("FABRICATED_145_IDENTITY_FAILURE")
        final_cp = canonical({"source_head": head, "run_id": run_id,
                              "parsed_fabricated_identities": 145, "complete": True,
                              "no_replay": True})
        content_put(branch, "CHECKPOINT_SYNTHETIC_V1.json", final_cp, cp_sha)
        if content_get(branch, "CHECKPOINT_SYNTHETIC_V1.json")[0] != final_cp:
            raise RuntimeError("FINAL_CHECKPOINT_NOT_DURABLE")
        guard_live(head)
        result["fabricated_identities"] = 145
        result["remote_checkpoint_sha256"] = sha(final_cp)
        result["steps"].append("DURABLE_CHECKPOINT_RECOVERY_AND_145_FABRICATED_IDENTITIES_PASS")
        result["status"] = "MACHINE_SIDE_SYNTHETIC_PROVIDER_PASS_NOT_REAL_ARM"
        report = canonical(result)
        content_put(branch, "PROVIDER_REPORT_SYNTHETIC_V1.json", report)
        if content_get(branch, "PROVIDER_REPORT_SYNTHETIC_V1.json")[0] != report:
            raise RuntimeError("DURABLE_REPORT_ROUNDTRIP")
    except BaseException as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        report_path = destination / "PRIMARY145_PROVIDER_SYNTHETIC_RESULT_V1.json"
        report_path.write_bytes(canonical(result))
        print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["status"] == "MACHINE_SIDE_SYNTHETIC_PROVIDER_PASS_NOT_REAL_ARM" else 1


if __name__ == "__main__":
    sys.exit(main())
