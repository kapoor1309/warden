"""Canonical provenance-record helpers shared by every agent.

One place to (a) pull a JSON record out of a Band message, (b) normalize the
legacy `claimed_source` field to `origin` so Parshiv's existing Intake prompt and
the deterministic agents speak the same shape, and (c) serialize a record back
into a message body with a fenced JSON block.

`warden.invariants` only reads `facts.*.value`, so normalization is belt-and-
suspenders for consumers that care about provenance origin (the Investigator).
"""

import json
import re

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def extract(text):
    """Pull the first JSON object out of a message. Returns a dict or None.
    Tries a ```json fence first, then the first balanced {...}."""
    if not text:
        return None
    m = _JSON_FENCE.search(text)
    candidate = m.group(1) if m else None
    if candidate is None:
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    break
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def normalize(rec):
    """Map legacy `claimed_source` -> `origin` in each fact. Non-fatal on junk."""
    if not isinstance(rec, dict):
        return rec
    facts = rec.get("facts")
    if isinstance(facts, dict):
        for f in facts.values():
            if isinstance(f, dict) and "origin" not in f and "claimed_source" in f:
                f["origin"] = f["claimed_source"]
    return rec


def to_message(rec, note=""):
    """Serialize a record into a message body with a fenced JSON block."""
    body = json.dumps(rec, indent=2)
    return f"{note}\n```json\n{body}\n```" if note else f"```json\n{body}\n```"
