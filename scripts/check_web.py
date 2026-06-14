"""Smoke-test the FastAPI app in-process (no server needed)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("WARDEN_SIGNING_SECRET", "warden-console-demo-secret")

from fastapi.testclient import TestClient
from web.app import app

c = TestClient(app)
meta = c.get("/api/meta").json()
print("meta OK:", "stats" in meta, "| llm_available:", meta["llm_available"])
samples = meta["samples"]


def outcome(doc, llm):
    return c.post("/api/run", json={"document": doc, "use_llm": llm}).json()["outcome"]["status"]


print("simple clean      ->", outcome(samples["clean"], False))
print("simple poisoned   ->", outcome(samples["poisoned"], False))
print("real invoice clean    (LLM) ->", outcome(samples["realistic_clean"], True))
print("real invoice tampered (LLM) ->", outcome(samples["realistic_poisoned"], True))
