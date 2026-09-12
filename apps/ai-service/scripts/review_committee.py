#!/usr/bin/env python3
"""Score the repo against review.md findings. Exit 0 only at 100%."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_review_committee.py", "-q"],
        cwd=AI_ROOT,
        capture_output=True,
        text=True,
    )
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    items = [
        "P0.1 rate-limit + limiter + batched signals",
        "P0.2 pinned structured-output model",
        "P0.3 publisher/listicle rejection",
        "P0.4 Database(client=None) offline",
        "P1.5 contacts migration path",
        "P1.6 run-scoped GET /discovery/{id}",
        "P1.7 reload off + stale reaper",
        "P1.8/9 crawl parallel + ranked search cap",
        "P1.10/P2.14 enrich UI + empty state + next.config",
        "P2.11 completed_with_errors",
        "P2.13 ICP + scheduled workflow",
        "P3 README + deploy configs",
    ]
    passed = proc.returncode == 0
    for item in items:
        print(f"{'PASS' if passed else 'FAIL'}: {item}")
    # Individual pytest names still report in stdout above.
    if passed:
        print(f"SCORE: 100% ({len(items)}/{len(items)})")
        return 0
    print("SCORE: incomplete — review committee tests failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
