#!/usr/bin/env python3
"""Validate and summarize a returned V3 maxT14 friction evidence ZIP."""
from __future__ import annotations

import argparse
from pathlib import Path

from research_core_v3.v3_friction_evidence import assess_bundle, write_assessment

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("research_core_v3/state/MAXT14_AUTHENTIC_FRICTION_EVIDENCE_ASSESSMENT_V1.json"))
    args = parser.parse_args()
    assessment = assess_bundle(args.repo_root, args.bundle)
    write_assessment(assessment, args.output)
    print(f"V3_MAXT14_FRICTION_EVIDENCE_ACCEPTED {args.output}")
    print(f"BUNDLE_SHA256={assessment['bundle_sha256']}")
    print(f"SYMBOLS={assessment['historical_bid_ask_symbols']}")
    print(f"EXACT_WINDOWS={assessment['historical_bid_ask_exact_windows']}")
    print("CANDIDATE_FREEZE=false NET_CERTIFICATION=false PROTECTED_FORWARD=false")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
