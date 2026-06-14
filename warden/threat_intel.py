"""Threat-Intel specialist logic: check a payee account against a fraud watchlist.

The DECISION is deterministic (a watchlist lookup) — consistent with the project
rule that security calls never depend on an LLM. Featherless (an open model) is
used only to NARRATE the finding into a human-readable risk note, which is the
specialist's "reasoning" and earns the partner prize without ever making the call.
"""

import os
import re
import json
from pathlib import Path

import httpx

_DB = json.loads(
    (Path(__file__).resolve().parent.parent / "sources" / "fraud_intel.json").read_text()
)["accounts"]


def _norm(account: str) -> str:
    return re.sub(r"\s+", "", account or "").upper()


_DB_NORM = {_norm(k): v for k, v in _DB.items()}


def check_account(account: str) -> dict:
    """Look the account up on the watchlist. Returns a structured finding."""
    hit = _DB_NORM.get(_norm(account))
    if hit:
        return {"account": account, "known_fraud": True, "risk": hit["risk"],
                "reason": hit["reason"], "source": hit["source"]}
    return {"account": account, "known_fraud": False, "risk": "unverified",
            "reason": "Not on any fraud watchlist, but it is a new account never paid before.",
            "source": "threat-intel"}


def narrate(finding: dict, use_llm: bool = False) -> str:
    """One-line risk note. Featherless (open model) phrases it when use_llm; the
    verdict itself comes from the deterministic finding, never the model."""
    base = (f"Account {finding['account']}: "
            + ("KNOWN FRAUD / MULE ACCOUNT — " if finding["known_fraud"] else "no watchlist hit — ")
            + finding["reason"] + f" (source: {finding['source']})")
    if not use_llm:
        return base
    key = os.getenv("FEATHERLESS_API_KEY")
    if not key:
        return base
    try:
        prompt = ("You are a financial-crime threat-intelligence analyst. In ONE sentence, "
                  "give a crisp risk assessment for this account-screening finding. Do not change "
                  f"the verdict; just phrase it professionally.\n\nFINDING: {json.dumps(finding)}")
        r = httpx.post(
            f"{os.getenv('FEATHERLESS_BASE_URL', 'https://api.featherless.ai/v1').rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": os.getenv("FEATHERLESS_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0, "max_tokens": 90},
            timeout=40.0,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return base
