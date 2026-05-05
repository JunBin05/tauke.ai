import os
import requests
import jwt
import time
from typing import Any
from fastapi import HTTPException

# We use the helpers file you created!
from helpers import get_zhipu_api_key, _extract_model_text, _parse_model_json

# ---------------------------------------------------------
# ATTEMPT 2: GEMINI
# ---------------------------------------------------------
def _call_gemini_vision(image_data_url: str, prompt: str) -> Any:
    """Fallback 1: Google Gemini 2.5 Flash."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("Missing GEMINI_API_KEY in .env")

    header, encoded = image_data_url.split(",", 1)
    mime_type = header[5:].split(";")[0]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    payload = {
        "system_instruction": {"parts": [{"text": "You are a precise financial data extractor. Output ONLY pure JSON."}]},
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": encoded}}
            ]
        }],
        "generationConfig": {"temperature": 0.1}
    }

    response = requests.post(url, json=payload, timeout=60)
    
    if not response.ok:
        raise Exception(f"Gemini Vision HTTP {response.status_code}: {response.text[:200]}")

    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_model_json(text, source_name="Gemini Vision model")


# ---------------------------------------------------------
# ATTEMPT 3: OPENROUTER 
# ---------------------------------------------------------
def _call_openrouter_vision(image_data_url: str, prompt: str) -> Any:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise Exception("Missing OPENROUTER_API_KEY in .env")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": os.getenv("OPENROUTER_FALLBACK_MODEL"),
        "temperature": 0.1,
        "response_format": { "type": "json_object" },
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt + "\n\nReturn ONLY pure JSON."},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    
    if not response.ok:
        raise Exception(f"OpenRouter Vision HTTP {response.status_code}: {response.text[:200]}")
        
    data = response.json()
    text = data["choices"][0]["message"]["content"]
    return _parse_model_json(text, source_name="OpenRouter Vision model")


# ---------------------------------------------------------
# MAIN ROUTER
# ---------------------------------------------------------
def run_sync_router(image_data_url: str, prompt: str) -> Any:
    """
    Sync Router: 
    1. Tries Zhipu AI (GLM-4.6v-flash)
    2. Falls back to Gemini 2.5 Flash
    3. Falls back to OpenRouter (Qwen)
    """
    api_key = get_zhipu_api_key()
    parts = api_key.split(".")
    if len(parts) != 2:
        raise HTTPException(status_code=500, detail="ZHIPUAI_API_KEY must be in 'id.secret' format")

    api_id, api_secret = parts[0], parts[1]
    now_ms = int(time.time() * 1000)
    payload_jwt = {"api_key": api_id, "exp": now_ms + 300_000, "timestamp": now_ms}
    token = jwt.encode(payload_jwt, api_secret, algorithm="HS256", headers={"alg": "HS256", "sign_type": "SIGN"})

    # ----- ATTEMPT 1: ZHIPU AI -----
    try:
        response = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("ZHIPUAI_MODEL"),
                "temperature": 0.1,
                "messages": [
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ]}
                ],
            },
            timeout=30,
        )
        if response.status_code in [429, 502, 503] or not response.ok:
            raise Exception(f"Zhipu returned HTTP {response.status_code}")
            
        data = response.json()
        if "error" in data:
            raise Exception(f"Zhipu API Error: {data['error'].get('code')}")

        choices = data.get("choices")
        if choices:
            raw_text = _extract_model_text(choices[0].get("message", {}).get("content", ""))
            return _parse_model_json(raw_text, source_name="Zhipu Vision model")
            
    except Exception as zhipu_error:
        print(f"⚠️ [Sync Router] Zhipu failed ({zhipu_error}). Trying Gemini...")

        # ----- ATTEMPT 2: GEMINI FALLBACK -----
        try:
            return _call_gemini_vision(image_data_url, prompt)
            
        except Exception as gemini_error:
            print(f"⚠️ [Sync Router] Gemini failed ({gemini_error}). Trying OpenRouter...")
            
            # ----- ATTEMPT 3: OPENROUTER FALLBACK (THE NEW ONE) -----
            try:
                print(" [Sync Router] Executing OpenRouter Vision fallback...")
                return _call_openrouter_vision(image_data_url, prompt)
                
            except Exception as or_error:
                print(f"❌ [Sync Router] ALL SYNC MODELS FAILED: {or_error}")
                raise HTTPException(
                    status_code=502,
                    detail=f"All Sync models failed. Last error: {or_error}",
                )