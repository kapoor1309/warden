"""Verify each registered Band agent's REAL handle matches {prefix}/{slug}.

A wrong slug or prefix routes every @mention into the void and the chain dies
silently — so this is the guard to run after filling .env, before any live demo.

It uses Warden to create a throwaway room, add every agent we have an id for,
read the participant list (which carries each agent's real handle), and compare
to identity.handle_for(role). Fails loud on any mismatch.

Run from repo root:  python scripts/check_handles.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from band_client import BandClient
from agents.identity import SLUGS, handle_for, agent_env, prefix


def _participants(client, chat_id):
    data = client.list_participants(chat_id)
    rows = data.get("data", data) if isinstance(data, dict) else data
    if isinstance(rows, dict):
        rows = rows.get("participants", [])
    out = {}
    for p in rows:
        if not isinstance(p, dict):
            continue
        aid = p.get("agent_id") or (p.get("agent") or {}).get("id") or p.get("id")
        handle = (p.get("handle") or "").lstrip("@")
        if aid:
            out[aid] = handle
    return out


def main():
    print(f"BAND_HANDLE_PREFIX = {prefix()!r}\n")
    warden_id, warden_key = agent_env("WARDEN")
    warden = BandClient(warden_key)

    room = warden.create_chat()
    chat_id = (room.get("data", room) if isinstance(room, dict) else room).get("id")
    print(f"temp room: {chat_id}")

    have = {}  # role -> agent_id, for roles whose id is in .env
    for role in SLUGS:
        aid = os.getenv(f"{role}_AGENT_ID")
        if aid:
            have[role] = aid
            if aid != warden_id:
                try:
                    warden.add_participant(chat_id, aid)
                except Exception as e:
                    print(f"  [WARN] could not add {role}: {e}")

    live = _participants(warden, chat_id)

    failures = 0
    for role, aid in have.items():
        expected = handle_for(role)
        actual = live.get(aid, "(not in room / no handle returned)")
        ok = actual == expected
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {role:<13} expected {expected!r}  actual {actual!r}")

    # tidy up: remove the agents we added (leave Warden; room expires in 24h anyway)
    for role, aid in have.items():
        if aid != warden_id:
            try:
                warden.remove_participant(chat_id, aid)
            except Exception:
                pass

    print(f"\n{'ALL HANDLES MATCH' if failures == 0 else str(failures) + ' MISMATCH(ES) — fix slugs/prefix in .env'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
