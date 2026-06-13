"""Judge-supplied attack path — the strongest bias-proof source.

A judge types their own attack and the SAME five rules must still catch it. Read
from `--judge "<text>"` or piped stdin. Fails loud if nothing is supplied — we do
not silently fall back to a self-authored attack.
"""

import sys


def get_judge_attack(argv=None) -> str:
    argv = list(sys.argv if argv is None else argv)
    if "--judge" in argv:
        i = argv.index("--judge")
        if i + 1 < len(argv) and argv[i + 1].strip():
            return argv[i + 1].strip()
    piped = ""
    try:
        if not sys.stdin.isatty():
            piped = sys.stdin.read().strip()
    except (OSError, ValueError):
        piped = ""  # no usable stdin (e.g. captured) — fall through to fail loud
    if piped:
        return piped
    raise SystemExit('judge attack: provide --judge "<your attack text>" or pipe text on stdin')
