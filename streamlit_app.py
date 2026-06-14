"""Warden Console — type an invoice, watch the real pipeline run, see under the hood.

The whole pipeline lives in warden/pipeline.py (shared with scripts/demo_pipeline.py),
so this page only RENDERS the trace it returns. Every record and verdict is computed
live by the real backend (warden.invariants / warden.agents / warden.paygate) on
whatever invoice you type.

Run:  streamlit run streamlit_app.py
"""

import os
import time

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("WARDEN_SIGNING_SECRET", "warden-console-demo-secret")

from warden.pipeline import run, RULE_LABELS, CLEAN_DOC, POISONED_DOC

st.set_page_config(page_title="Warden — live pipeline", page_icon="🛡️", layout="wide")

st.title("🛡️ Warden — live invoice pipeline")
st.caption("Type or paste an invoice, run it through the real agent pipeline, and watch what "
           "happens under the hood. Warden catches a hijacked step before the money moves.")

c1, c2, c3 = st.columns([1, 1, 2])
if c1.button("📄 Load a clean invoice"):
    st.session_state.doc = CLEAN_DOC
if c2.button("☠️ Load a poisoned invoice"):
    st.session_state.doc = POISONED_DOC
use_llm = c3.toggle("Use the real LLM Intake agent (AI/ML API)",
                    value=bool(os.getenv("AIML_API_KEY")),
                    help="On = the actual LLM reads the document (so injection is real). "
                         "Off = an offline parser. Warden's checks are identical either way.")

doc = st.text_area("Invoice document (edit freely — this is the untrusted input Intake reads):",
                   value=st.session_state.get("doc", CLEAN_DOC), height=200)

go = st.button("▶️  Run the pipeline", type="primary")
st.divider()

if not go:
    st.info("Pick or paste an invoice above, then hit **Run the pipeline**.")
    st.stop()


def render_rules(violations):
    for code, label in RULE_LABELS.items():
        if code in violations:
            st.markdown(f"&nbsp;&nbsp;🚨 **{label} — VIOLATED**")
        else:
            st.markdown(f"&nbsp;&nbsp;✅ {label}")


result = run(doc, use_llm=use_llm)

for step in result["steps"]:
    with st.status(f"{step['icon']}  {step['title']}", state=step["state"], expanded=True):
        for line in step["lines"]:
            st.write(line)
        if step["record"] is not None:
            with st.expander("🔬 under the hood (the record)"):
                st.json(step["record"])
        if step["violations"] is not None:
            render_rules(step["violations"])
    time.sleep(0.5)  # let each stage land before the next, so it reads as a live run

o = result["outcome"]
if o["status"] == "RELEASED":
    st.success(f"### 💰 Payment RELEASED\n{o['message']}")
elif o["status"] == "BLOCKED":
    st.error(f"### 💸 Payment BLOCKED\n{o['message']}")
    st.caption("Warden never read the document as instructions — it only compared the shape and "
               "origin of what happened against the records. Hiding \"skip the checks\" in the "
               "invoice does nothing.")
elif o["status"] == "FROZEN":
    st.error(f"### 💸 Payment FROZEN\n{o['message']}")
else:
    st.warning(f"### Pipeline stopped\n{o['message']}")
