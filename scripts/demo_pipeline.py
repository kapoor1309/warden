"""Headless pipeline test — no browser, no keys needed.

Runs the SAME pipeline the Streamlit console uses, on a clean and a poisoned
invoice, and prints the full under-the-hood trace. Lets us verify the logic
instantly (and offline, via the regex Intake fallback).

Run:  python scripts/demo_pipeline.py
      python scripts/demo_pipeline.py --llm     (use the real LLM Intake)
"""

import os
import sys
import json

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("WARDEN_SIGNING_SECRET", "warden-console-demo-secret")

from warden.pipeline import run, RULE_LABELS, CLEAN_DOC, POISONED_DOC

USE_LLM = "--llm" in sys.argv


def show(name, document):
    print("\n" + "=" * 64)
    print(f"  INVOICE: {name}   (Intake = {'LLM' if USE_LLM else 'parser'})")
    print("=" * 64)
    result = run(document, use_llm=USE_LLM)
    for s in result["steps"]:
        flag = "  <-- FLAGGED" if s["state"] == "error" else ""
        print(f"\n{s['icon']}  {s['title']}{flag}")
        for line in s["lines"]:
            print(f"     {line}")
        if s["record"] is not None:
            print("     under the hood:", json.dumps(s["record"]))
        if s["violations"] is not None:
            for code, label in RULE_LABELS.items():
                mark = "RULE VIOLATED" if code in s["violations"] else "ok"
                print(f"       [{mark:13}] {label}")
    o = result["outcome"]
    print(f"\n>>> OUTCOME: {o['status']} — {o['message']}")


if __name__ == "__main__":
    show("CLEAN", CLEAN_DOC)
    show("POISONED", POISONED_DOC)
    print()
