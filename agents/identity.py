"""Single source of truth for Band agent handles + per-agent env lookup.

Each developer registers their OWN 6 Band agents under their OWN handle namespace
(Yash: `yashb967`, Parshiv: `parshiv.kapoor`). Set `BAND_HANDLE_PREFIX` in `.env`;
every handle is built as `{prefix}/{slug}`. Nothing is hardcoded to one owner.

Fail loud: if `BAND_HANDLE_PREFIX` is missing we RAISE rather than silently default
to someone's handle — a wrong handle routes every @mention into the void and the
chain dies quietly, which is exactly what we refuse to allow.
"""

import os

# role NAME (env prefix) -> canonical handle slug
SLUGS = {
    "INTAKE": "invoice-intake",
    "MATCHER": "po-matcher",
    "APPROVER": "approver",
    "WARDEN": "warden",
    "INVESTIGATOR": "investigator",
    "ENFORCER": "enforcer",
    "PAYER": "payer",
    "THREAT_INTEL": "threat-intel",
}


def prefix() -> str:
    p = os.getenv("BAND_HANDLE_PREFIX")
    if not p:
        raise RuntimeError(
            "BAND_HANDLE_PREFIX is not set in .env — refusing to guess a handle owner. "
            "Set it to your Band namespace (e.g. yashb967 or parshiv.kapoor)."
        )
    return p.strip().lstrip("@").rstrip("/")


def handle_for(name: str) -> str:
    """Resolve a role NAME to its full Band handle. A `{NAME}_HANDLE` env override
    wins (for odd slugs); otherwise build `{prefix}/{slug}`. Fails loud."""
    name = name.upper()
    override = os.getenv(f"{name}_HANDLE")
    if override:
        return override.strip().lstrip("@")
    if name not in SLUGS:
        raise KeyError(f"unknown agent role {name!r}")
    return f"{prefix()}/{SLUGS[name]}"


def agent_env(name: str):
    """(agent_id, api_key) for a role NAME, from env. Fails loud if missing."""
    name = name.upper()
    aid = os.getenv(f"{name}_AGENT_ID")
    key = os.getenv(f"{name}_API_KEY")
    if not aid or not key:
        raise RuntimeError(f"{name}_AGENT_ID / {name}_API_KEY missing from .env.")
    return aid, key
