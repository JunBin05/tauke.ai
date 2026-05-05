"""
llm_router.py — Multi-provider LLM fallback chain.

Priority order:
  1. Groq          (fastest, free tier)
  2. Cerebras      (fast inference, free tier)
  3. OpenRouter    (multi-model gateway, free tier)
  4. Gemini        (Google, free tier)
  5. ILMU          (last resort, slow but reliable)

Add your keys to .env:
  GROQ_API_KEY=...
  CEREBRAS_API_KEY=...
  OPENROUTER_API_KEY=...
  GEMINI_API_KEY=...
  ILMU_API_KEY=...

Usage in vision_service.py:
  from llm_router import call_llm

  text = call_llm(system_prompt, user_prompt, temperature=0.2)
"""

import os
import time
import requests
from typing import Optional

# ---------------------------------------------------------------------------
# Provider configurations
# ---------------------------------------------------------------------------

PROVIDERS = [
    {
        "name": "Groq",
        "env_key": "GROQ_API_KEY",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.3-70b-versatile", 
        "max_tokens": 4000,
        "headers_fn": lambda key: {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    },
    {
        "name": "Cerebras",
        "env_key": "CEREBRAS_API_KEY",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama-3.3-70b",       
        "max_tokens": 4000,
        "headers_fn": lambda key: {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    },
    {
        "name": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "meta-llama/llama-3.3-70b-instruct:free", 
        "max_tokens": 4000,
        "headers_fn": lambda key: {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://tauke-ai.vercel.app",
            "X-Title": "TaukeAI",
        },
    },
    {
        "name": "Gemini",
        "env_key": "GEMINI_API_KEY",
        "url": None,  # Built differently — see _call_gemini()
        "model": "gemini-2.5-flash",         
        "max_tokens": 4000,
        "headers_fn": None,
    },
    {
        "name": "ILMU",
        "env_key": "ILMU_API_KEY",
        "url": "https://api.ilmu.ai/v1/chat/completions",
        "model": os.getenv("ILMU_MODEL"),
        "max_tokens": 1500,                 
        "headers_fn": lambda key: {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    },
]


# ---------------------------------------------------------------------------
# Generic OpenAI-compatible caller
# ---------------------------------------------------------------------------

def _call_openai_compatible(
    provider: dict,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> Optional[str]:
    """Call any OpenAI-compatible endpoint."""
    response = requests.post(
        provider["url"],
        headers=provider["headers_fn"](api_key),
        json={
            "model": provider["model"],
            "temperature": temperature,
            "max_tokens": provider["max_tokens"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        },
        timeout=60,
    )

    # Detect HTML error pages
    if "text/html" in response.headers.get("content-type", ""):
        raise Exception(f"{provider['name']} returned HTML error (HTTP {response.status_code})")

    if not response.ok:
        raise Exception(f"{provider['name']} HTTP {response.status_code}: {response.text[:200]}")

    data = response.json()

    # Check finish_reason — skip if cut off with no content
    choices = data.get("choices", [])
    if not choices:
        raise Exception(f"{provider['name']} returned no choices")

    first = choices[0]
    finish_reason = str(first.get("finish_reason", "")).lower()
    content = (first.get("message") or {}).get("content")

    if not content and finish_reason == "length":
        raise Exception(f"{provider['name']} hit max_tokens with no content (finish_reason=length)")

    if not content:
        raise Exception(f"{provider['name']} returned empty content (finish_reason={finish_reason})")

    return content.strip()


# ---------------------------------------------------------------------------
# Gemini-specific caller (different API format)
# ---------------------------------------------------------------------------

def _call_gemini(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> Optional[str]:
    """Call Google Gemini via REST API."""
    model = os.getenv("GEMINI_MODEL")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    response = requests.post(url, json=payload, timeout=60)

    if not response.ok:
        raise Exception(f"Gemini HTTP {response.status_code}: {response.text[:200]}")

    data = response.json()

    # Check for safety blocks
    candidates = data.get("candidates", [])
    if not candidates:
        raise Exception("Gemini returned no candidates")

    finish_reason = candidates[0].get("finishReason", "")
    if finish_reason in ("SAFETY", "RECITATION"):
        raise Exception(f"Gemini blocked: finishReason={finish_reason}")

    parts = (candidates[0].get("content") or {}).get("parts", [])
    if not parts:
        raise Exception("Gemini returned empty parts")

    text = parts[0].get("text", "").strip()
    if not text:
        raise Exception("Gemini returned empty text")

    return text


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> str:
    """
    Try each provider in order. Returns the first successful response.
    Raises Exception only if ALL providers fail.
    """
    errors = []

    for provider in PROVIDERS:
        key = os.getenv(provider["env_key"], "").strip()

        if not key:
            print(f"[LLM Router] Skipping {provider['name']} — no API key in .env")
            continue

        apikeys = [k.strip() for k in key.split(",") if k.strip()]

        for idx, apikey in enumerate(apikeys):
            try:
                print(f"[LLM Router] Trying {provider['name']} (Key {idx + 1}/{len(apikeys)})...")

                if provider["name"] == "Gemini":
                    result = _call_gemini(
                        apikey, system_prompt, user_prompt,
                        temperature, provider["max_tokens"]
                    )
                else:
                    result = _call_openai_compatible(
                        provider, apikey, system_prompt, user_prompt, temperature
                    )

                print(f"[LLM Router] ✅ {provider['name']} succeeded with Key {idx + 1}")
                return result

            except Exception as exc:
                err_msg = f"{provider['name']} (Key {idx + 1}): {exc}"
                errors.append(err_msg)
                print(f"[LLM Router] ❌ {err_msg}")

                # Short wait before trying next provider
                time.sleep(1)
                continue

        # All providers failed
    raise Exception(
        f"All LLM providers failed.\n" + "\n".join(errors)
    )