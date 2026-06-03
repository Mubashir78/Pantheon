#!/usr/bin/env python3
"""consolidate.py — backwards-compat shim for the Hades Nightly cron.

The Hades Nightly cron at 9am (job `cfb065b056ac`) has its prompt
hardcoded to call `python3 consolidate.py`. The original
consolidate.py was removed in some earlier cleanup; this file is a
replacement that delegates to the modern `scripts/hades` shim so
tonight's 9am run doesn't fail at step 1.

Brittleness fix #1 (2026-06-03): the cron prompt references a
non-existent file (`consolidate.py` was deleted, the live entry point
is `scripts/hades` via the package refactor). This shim gives the
cron something to call without forcing a cron-prompt rewrite.

If you're editing the cron prompt, you can replace the
`python3 consolidate.py` line with `python3 scripts/hades` and
delete this file. Until then, this shim keeps the existing prompt
working.

For modern callers, prefer the explicit flags:
    python3 scripts/hades --health
    python3 scripts/hades --distill
    python3 scripts/hades --archive
    python3 scripts/hades                  # full sweep
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Resolve scripts/hades relative to this file
HERE = Path(__file__).resolve().parent
SHIM = HERE / "scripts" / "hades"


def main() -> int:
    if not SHIM.exists():
        print(f"ERROR: {SHIM} not found — was the package refactored?", file=sys.stderr)
        return 1

    # Default behavior: full sweep. If the cron ever needs
    # granular control, pass flags through.
    cmd = [sys.executable, str(SHIM)]

    # Pass through any flags the caller provided
    cmd.extend(sys.argv[1:])

    # Default a 25-minute hard timeout. Cron jobs shouldn't take
    # longer than that; if they do, we want to know.
    env = os.environ.copy()
    if "--timeout" not in sys.argv:
        cmd.extend(["--timeout", "1500"])

    # Delegation log goes to stderr so --json consumers can pipe stdout
    print(f"[consolidate.py] Delegating to: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, env=env)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
