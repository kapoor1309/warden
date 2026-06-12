"""Phase A, test 1: prove every agent can connect to Band.

For each agent, calls GET /agent/me with its API key. A pass means the key is
valid and Band knows who the agent is. No LLM, no websocket, no room needed.

Run from the repo root:  python scripts/check_connection.py
"""

import os
import sys

# Make the repo root importable so `band_client` is found when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from band_client import BandClient

load_dotenv()

AGENTS = ["INTAKE", "MATCHER", "APPROVER", "WARDEN", "INVESTIGATOR", "ENFORCER"]

print("Checking each agent against Band (GET /agent/me)...\n")

passed, failed = 0, 0
for name in AGENTS:
    api_key = os.getenv(f"{name}_API_KEY")
    if not api_key:
        print(f"  [SKIP] {name:<13} no API key in .env")
        continue
    try:
        me = BandClient(api_key).me()
        # Band returns the agent's profile; show whatever name/handle it gives.
        label = me.get("name") or me.get("handle") or me.get("id") or "(connected)"
        print(f"  [PASS] {name:<13} -> {label}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {name:<13} -> {type(e).__name__}: {e}")
        failed += 1

print(f"\nDone. {passed} connected, {failed} failed.")
sys.exit(1 if failed else 0)
