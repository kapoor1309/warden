"""Warden Console — FastAPI backend.

Serves a professional dashboard and exposes the REAL pipeline over JSON. All
logic lives in warden/pipeline.py (shared with the headless demo), so this is a
thin transport + presentation layer. Run:

    uvicorn web.app:app --reload      (from the repo root)
"""

import io
import os
import sys
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("WARDEN_SIGNING_SECRET", "warden-console-demo-secret")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from warden.pipeline import (run, RULE_LABELS, CLEAN_DOC, POISONED_DOC,
                             REALISTIC_CLEAN, REALISTIC_POISONED)

# Real, cited fraud figures (FBI IC3) shown on the dashboard.
STATS = [
    {"value": "$2.77B", "label": "Lost to BEC in 2024", "source": "FBI IC3 2024 (21,442 complaints)"},
    {"value": "$55.5B", "label": "Exposed losses, 2013–2023", "source": "FBI IC3 PSA240911"},
    {"value": "~$129K", "label": "Average loss per BEC incident", "source": "derived, FBI IC3 2024"},
    {"value": "~86%", "label": "Of BEC funds move via wire/ACH", "source": "inside real payment workflows"},
]
SOURCES = [
    {"name": "FBI IC3 2024 Annual Report", "url": "https://www.ic3.gov/AnnualReport/Reports/2024_IC3Report.pdf"},
    {"name": "FBI IC3 — “The $55 Billion Scam” (PSA240911)", "url": "https://www.ic3.gov/PSA/2024/PSA240911"},
]

app = FastAPI(title="Warden Console")
_INDEX = (Path(__file__).resolve().parent / "static" / "index.html").read_text(encoding="utf-8")


class RunReq(BaseModel):
    document: str
    use_llm: bool = False


@app.get("/", response_class=HTMLResponse)
def index():
    return _INDEX


@app.get("/api/meta")
def meta():
    return {
        "rule_labels": RULE_LABELS,
        "samples": {
            "clean": CLEAN_DOC, "poisoned": POISONED_DOC,
            "realistic_clean": REALISTIC_CLEAN, "realistic_poisoned": REALISTIC_POISONED,
        },
        "stats": STATS,
        "sources": SOURCES,
        "llm_available": bool(os.getenv("AIML_API_KEY")),
    }


@app.post("/api/run")
def run_pipeline(req: RunReq):
    return run(req.document, use_llm=req.use_llm)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """Accept a real invoice PDF (or text) and return its extracted text."""
    data = await file.read()
    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    else:
        text = data.decode("utf-8", errors="ignore")
    return {"document": text, "filename": file.filename}
