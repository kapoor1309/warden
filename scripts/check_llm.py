"""Quick check that both LLM providers work (no Band needed).

Sends a tiny prompt to AI/ML API and Featherless and prints the reply.
Run:  python scripts/check_llm.py
"""

import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()


def ping(label, base_url, api_key, model):
    print(f"\n=== {label} ===")
    print(f"   url={base_url}  model={model}")
    if not api_key:
        print("   [SKIP] no API key in .env")
        return False
    try:
        r = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "max_tokens": 5,
                "temperature": 0,
            },
            timeout=60.0,
        )
        if r.status_code >= 300:
            print(f"   [FAIL] HTTP {r.status_code}: {r.text[:300]}")
            return False
        reply = r.json()["choices"][0]["message"]["content"].strip()
        print(f"   [PASS] model replied: {reply!r}")
        return True
    except Exception as e:
        print(f"   [FAIL] {type(e).__name__}: {e}")
        return False


aiml = ping(
    "AI/ML API",
    os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1"),
    os.getenv("AIML_API_KEY"),
    os.getenv("AIML_MODEL", "gpt-4o-mini"),
)
feather = ping(
    "Featherless",
    os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"),
    os.getenv("FEATHERLESS_API_KEY"),
    os.getenv("FEATHERLESS_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
)

print(f"\nResult: AI/ML API {'OK' if aiml else 'FAILED'}, Featherless {'OK' if feather else 'FAILED'}")
sys.exit(0 if (aiml and feather) else 1)
