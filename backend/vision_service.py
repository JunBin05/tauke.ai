import base64
import csv
import io
import json
import os
import re
import random
import json
import requests
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

import fitz
import pandas as pd
import zhipuai
import concurrent.futures
from dotenv import find_dotenv, load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import Client, create_client

from collections import defaultdict
from datetime import datetime


load_dotenv(find_dotenv(), override=True)


MASTER_EXTRACT_PROMPT = (
    "You are an F&B Financial Auditor for a Malaysian Cafe. Analyze this document and extract all financial data into a strict JSON format. "
    "1. If you see fixed costs (e.g., Rent, Payroll, TNB, Syabas, KWSP, Utilities), put them in 'operating_expenses'. "
    "2. If you see ingredient purchases (e.g., Chicken, Beans, Milk, Ice), put them in 'supplier_invoices'. "
    "3. If this is a Profit & Loss statement, extract the top-line sales number into 'total_revenue'. Look for terms like 'Total Revenue', 'Total Sales', 'Gross Sales', 'Turnover', 'Total Income', or 'Gross Profit'. \n\n"
    "RETURN ONLY JSON IN THIS EXACT FORMAT: "
    "{"
    "  \"document_type\": \"pl_statement\" | \"supplier_invoice\" | \"mixed\","
    "  \"total_revenue\": 0.00,"
    "  \"operating_expenses\": ["
    "    {\"expense_type\": \"Rent|Payroll|Utilities|Other\", \"amount\": 0.00}"
    "  ],"
    "  \"supplier_invoices\": ["
    "    {\"item_category\": \"Protein|Vegetable|Dry Goods|Dairy|Beverage|Other\", "
    "     \"item_name\": \"string\", \"quantity\": 0.0, \"unit\": \"string\", \"total_amount\": 0.00}"
    "  ]"
    "}"
)


class AnalyzeFinancialDocumentRequest(BaseModel):
    file_name: str = Field(min_length=1)
    file_data_url: str = Field(min_length=1)


class ProcessMonthlyUploadRequest(BaseModel):
    merchant_id: str = Field(min_length=1)
    merchant_profile: str = Field(min_length=1)
    report_month: str = Field(min_length=7)
    scanned_documents: List[Dict[str, Any]] = Field(default_factory=list)
    sales_csv_data_url: str = Field(min_length=1)


class BoardroomStartRequest(BaseModel):
    merchant_id: str = Field(min_length=1)
    target_month: str = Field(min_length=7)


class BoardroomContinueRequest(BaseModel):
    merchant_id: str = Field(min_length=1)
    target_month: str = Field(min_length=7)
    boss_answers: str = Field(min_length=1)

class WhatIfSimulationRequest(BaseModel):
    merchant_id: str = Field(min_length=1)
    target_month: str = Field(min_length=7)
    boss_idea: str = Field(min_length=1)
    customer_distribution_json: str = Field(default="{}")

class ProfileSetupRequest(BaseModel):
    merchant_id: str
    name: str
    type: str
    pricing_tier: str       # 👈 New
    operating_hours: str
    target_audience: dict   # 👈 Receives the JSON audience mix
    address: str            # 👈 New
    latitude: float         # 👈 New
    longitude: float        # 👈 New

class SignupRequest(BaseModel):
    email: str
    password: str
    business_name: str    

class LoginRequest(BaseModel):
    email: str
    password: str
    
class GoogleSyncRequest(BaseModel):
    access_token: str
    name: str            

class LocationUpdateRequest(BaseModel):
    merchant_id: str
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    place_id: Optional[str] = None

class DetectiveCardsRequest(BaseModel):
    merchant_id: str = Field(min_length=1)
    target_month: str = Field(min_length=7)

class GenerateRoadmapRequest(BaseModel):
    merchant_id: str = Field(min_length=1)
    target_month: Optional[str] = None
    source: str = Field(min_length=1, pattern=r"^(BOARDROOM|SANDBOX|SIMULATION)$")
    strategy_text: str = Field(...) # The chosen idea
    justification: str = Field(...) # Why the AI chose it (e.g., the profit boost reasoning)
    external_signals: Dict[str, Any] = Field(default_factory=dict)
    financial_trend: Dict[str, Any] = Field(default_factory=dict) # Financial trends related to the roadmap
    diagnostic_patterns: Dict[str, Any] = Field(default_factory=dict)


app = FastAPI(title="Vision Financial Upload Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



def get_zhipu_api_key() -> str:
    api_key = os.getenv("ZHIPU_API_KEY") or os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Missing ZHIPU_API_KEY or ZHIPUAI_API_KEY environment variable",
        )
    return api_key


def _get_google_places_api_key() -> Optional[str]:
    """Read Google Places API key tolerating both env var spellings."""
    return (
        os.getenv("GOOGLE_PLACES_API_KEY")
        or os.getenv("GOOGLE_PLACE_API_KEY")
    )


def get_zhipu_client() -> Any:
    api_key = get_zhipu_api_key()
    if hasattr(zhipuai, "ZhipuAI"):
        return {"mode": "modern", "client": zhipuai.ZhipuAI(api_key=api_key)}

    if hasattr(zhipuai, "model_api"):
        zhipuai.api_key = api_key
        return {"mode": "legacy", "client": zhipuai}

    raise HTTPException(
        status_code=500,
        detail="Installed zhipuai package has neither ZhipuAI nor model_api interface",
    )


def get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise HTTPException(
            status_code=500,
            detail="Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY environment variables",
        )

    return create_client(supabase_url, supabase_key)


def _extract_model_text(raw_content: Any) -> str:
    if raw_content is None:
        return ""

    if isinstance(raw_content, str):
        return raw_content.strip()

    if isinstance(raw_content, dict):
        text_value = raw_content.get("text")
        if isinstance(text_value, str):
            return text_value.strip()

        content_value = raw_content.get("content")
        if content_value is not None:
            return _extract_model_text(content_value)

        return ""

    if isinstance(raw_content, list):
        parts: List[str] = []
        for part in raw_content:
            extracted = _extract_model_text(part)
            if extracted:
                parts.append(extracted)
        return "\n".join(parts).strip()

    return str(raw_content).strip()


def _strip_markdown_fences(text: str) -> str:
    """Remove any surrounding markdown code fences from an LLM response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        cleaned = cleaned[first_newline + 1:] if first_newline != -1 else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    return cleaned


def _extract_json_from_text(raw_text: str, want_array: bool = False) -> str:
    """Multi-strategy JSON extractor — handles preamble text, markdown fences, truncated fences."""
    # Strategy 1: plain strip of fences
    candidate = _strip_markdown_fences(raw_text)
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        pass

    # Strategy 2: find the first { or [ and last } or ]
    open_char, close_char = ("[", "]") if want_array else ("{", "}")
    start = raw_text.find(open_char)
    end = raw_text.rfind(close_char)
    if start != -1 and end != -1 and end > start:
        candidate = raw_text[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # Strategy 3: try the stripped candidate anyway (e.g. trailing garbage after })
    for open_c, close_c in [("{" , "}"), ("[", "]")]:
        s = raw_text.find(open_c)
        e = raw_text.rfind(close_c)
        if s != -1 and e != -1 and e > s:
            try:
                json.loads(raw_text[s : e + 1])
                return raw_text[s : e + 1]
            except json.JSONDecodeError:
                pass

    # Strategy 4: return stripped as last resort (let caller raise a clear error)
    return candidate


def _repair_truncated_json(text: str) -> str:
    """
    Attempt to repair JSON that was cut off mid-stream (e.g. by max_tokens).
    Strategy: strip everything after the last cleanly-closed value, then
    close any unclosed braces/brackets in reverse order.
    """
    if not text:
        return text

    # Step 1: truncate at the last position that ends a clean value
    # Walk backwards from the end to find the last } or ] or " or digit
    t = text.rstrip()
    # Remove any trailing comma, colon, or partial key
    import re as _re
    # Strip trailing incomplete tokens: comma, colon, partial string, whitespace
    t = _re.sub(r'[,:\s]*$', '', t)
    # If we ended mid-string (odd number of unescaped quotes), strip the open string
    # Count quotes not preceded by backslash
    in_string = False
    escape_next = False
    for ch in t:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
    if in_string:
        # Remove back to the last unescaped opening quote
        last_quote = max(t.rfind('"'), 0)
        t = t[:last_quote].rstrip().rstrip(',').rstrip()

    # Step 2: close any open structures
    stack = []
    in_string = False
    escape_next = False
    for ch in t:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in '{[':
            stack.append('}' if ch == '{' else ']')
        elif ch in '}]':
            if stack:
                stack.pop()

    # Append the closing tokens in reverse
    closing = ''.join(reversed(stack))
    return t + closing


def _parse_model_json(raw_text: str, source_name: str, required_kind: Optional[str] = None) -> Any:
    """Parse JSON from an LLM response, tolerating preamble text and markdown fences."""
    if not isinstance(raw_text, str):
        raise HTTPException(status_code=502, detail=f"{source_name} returned non-text output before JSON parsing")

    if not raw_text.strip() or raw_text.strip().lower() in {"none", "null"}:
        raise HTTPException(status_code=502, detail=f"{source_name} returned empty output before JSON parsing")

    want_array = required_kind == "array"
    cleaned = _extract_json_from_text(raw_text, want_array=want_array)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Attempt to repair truncated JSON by closing unclosed braces/brackets
        repaired = _repair_truncated_json(cleaned)
        try:
            data = json.loads(repaired)
            print(f"[JSON Repair] Recovered truncated JSON for {source_name}")
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=502,
                detail=f"{source_name} returned invalid JSON: {exc}. Raw (first 300): {raw_text[:300]}"
            ) from exc

    if required_kind == "object" and not isinstance(data, dict):
        raise HTTPException(status_code=502, detail=f"{source_name} returned invalid JSON schema: expected object")
    if required_kind == "array" and not isinstance(data, list):
        raise HTTPException(status_code=502, detail=f"{source_name} returned invalid JSON schema: expected array")

    return data


def _to_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = "".join(ch for ch in value if ch.isdigit() or ch in {".", "-"})
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def _decode_data_url(data_url: str) -> Tuple[str, bytes]:
    if not data_url.startswith("data:") or "," not in data_url:
        raise HTTPException(status_code=400, detail="file_data_url must be a valid data URL")

    header, encoded = data_url.split(",", 1)
    mime = header[5:].split(";")[0].lower()

    if ";base64" not in header:
        raise HTTPException(status_code=400, detail="Only base64 data URLs are supported")

    try:
        raw = base64.b64decode(encoded)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {exc}") from exc

    return mime, raw


def _bytes_to_data_url(file_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _render_pdf_pages_as_data_urls(file_bytes: bytes, max_pages: int = 5) -> List[str]:
    data_urls: List[str] = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page_limit = min(len(doc), max_pages)

    for page_index in range(page_limit):
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
        png_bytes = pix.tobytes("png")
        data_urls.append(_bytes_to_data_url(png_bytes, "image/png"))

    return data_urls


def _vision_json(client: Any, image_data_url: str, prompt: str) -> Any:
    """Call ZhipuAI glm-5.1 vision model via direct HTTP API.

    The legacy SDK (v1.0.7) returns empty content for vision calls,
    so we bypass it and call the HTTP API directly with JWT auth.
    """
    _ = client  # Kept for call-site compat; we now use direct HTTP

    api_key = get_zhipu_api_key()

    # ZhipuAI API key format: "{id}.{secret}" — split to build JWT
    parts = api_key.split(".")
    if len(parts) != 2:
        raise HTTPException(status_code=500, detail="ZHIPUAI_API_KEY must be in 'id.secret' format")

    api_id, api_secret = parts[0], parts[1]

    # Build the JWT token (ZhipuAI's auth method)
    import time as _time
    try:
        import jwt
        now_ms = int(_time.time() * 1000)
        payload_jwt = {
            "api_key": api_id,
            "exp": now_ms + 300_000,  # 5 min expiry
            "timestamp": now_ms,
        }
        token = jwt.encode(payload_jwt, api_secret, algorithm="HS256", headers={"alg": "HS256", "sign_type": "SIGN"})
    except Exception as jwt_err:
        raise HTTPException(status_code=500, detail=f"Failed to sign ZhipuAI JWT: {jwt_err}")

    # Call the vision model via direct HTTP with retry on 429 rate limits
    import time as _time_mod
    MAX_VISION_RETRIES = 3
    last_exc = None

    for attempt in range(1, MAX_VISION_RETRIES + 1):
        try:
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "glm-5.1",
                    "temperature": 0.1,
                    "max_tokens": 4000,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Read this document and return JSON only."},
                                {"type": "image_url", "image_url": {"url": image_data_url}},
                            ],
                        },
                    ],
                },
                timeout=90,
            )

            # Handle HTML error pages (e.g. gateway errors)
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type:
                raise Exception(f"ZhipuAI returned HTML error (HTTP {response.status_code})")

            # Handle 429 rate limit — wait and retry
            if response.status_code == 429:
                wait_s = 8 * attempt  # 8s, 16s, 24s
                print(f"[Vision] ZhipuAI rate limited (429, attempt {attempt}/{MAX_VISION_RETRIES}). Waiting {wait_s}s...")
                _time_mod.sleep(wait_s)
                # Rebuild JWT since it's time-based
                now_ms = int(_time_mod.time() * 1000)
                payload_jwt["exp"] = now_ms + 300_000
                payload_jwt["timestamp"] = now_ms
                token = jwt.encode(payload_jwt, api_secret, algorithm="HS256", headers={"alg": "HS256", "sign_type": "SIGN"})
                last_exc = Exception(f"ZhipuAI vision HTTP 429 (rate limited): {response.text[:200]}")
                continue

            if not response.ok:
                raise Exception(f"ZhipuAI vision HTTP {response.status_code}: {response.text[:300]}")

            data = response.json()

            # Check for API-level error codes (e.g. 1305 = rate limit in body)
            if "error" in data:
                err_code = data["error"].get("code", "")
                err_msg = data["error"].get("message", "")
                if str(err_code) in ("1305", "1301", "1302"):
                    wait_s = 10 * attempt
                    print(f"[Vision] ZhipuAI error {err_code} (attempt {attempt}/{MAX_VISION_RETRIES}). Waiting {wait_s}s...")
                    _time_mod.sleep(wait_s)
                    last_exc = Exception(f"ZhipuAI vision error {err_code}: {err_msg}")
                    continue
                raise Exception(f"ZhipuAI vision API error {err_code}: {err_msg}")

            choices = data.get("choices")
            if not isinstance(choices, list) or not choices:
                raise HTTPException(status_code=502, detail=f"Vision model returned no choices: {data}")

            raw_text = _extract_model_text(choices[0].get("message", {}).get("content", ""))
            return _parse_model_json(raw_text, source_name="Vision model")

        except HTTPException:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_VISION_RETRIES:
                _time_mod.sleep(5 * attempt)
                continue
            break

    raise HTTPException(
        status_code=502,
        detail=f"ZhipuAI vision request failed after {MAX_VISION_RETRIES} attempts: {last_exc}",
    )




def _normalize_pl_rows(parsed: Any) -> List[Dict[str, Any]]:
    if isinstance(parsed, list):
        rows = parsed
    elif isinstance(parsed, dict):
        rows = parsed.get("operating_expenses") or []
    else:
        rows = []

    if not isinstance(rows, list):
        rows = []

    normalized: List[Dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        if "expense_type" not in row or "amount" not in row:
            continue
        expense_type = str(row.get("expense_type", "Other")).strip() or "Other"
        amount = round(_to_float(row.get("amount"), 0.0), 2)
        if amount > 0:
            normalized.append({"expense_type": expense_type, "amount": amount})

    return normalized


def _normalize_invoice_rows(parsed: Any) -> List[Dict[str, Any]]:
    if isinstance(parsed, list):
        rows = parsed
    elif isinstance(parsed, dict):
        rows = parsed.get("supplier_invoices") or []
    else:
        rows = []

    if not isinstance(rows, list):
        rows = []

    normalized: List[Dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        
        # ONLY require item_name and total_amount. 
        # If the AI forgets these, it's useless data.
        if "item_name" not in row or "total_amount" not in row:
            continue

        item_name = str(row.get("item_name", "")).strip()
        if not item_name:
            continue

        # Provide safe defaults if the AI missed these optional keys
        quantity = _to_float(row.get("quantity", 1.0), 1.0) # Default to 1
        unit = str(row.get("unit", "unit")).strip() or "unit"
        total_amount = round(_to_float(row.get("total_amount"), 0.0), 2)

        if total_amount <= 0:
            continue

        item_category = str(row.get("item_category", "Other")).strip() or "Other"
        unit_cost = round((total_amount / quantity), 4) if quantity > 0 else total_amount

        normalized.append(
            {
                "item_category": item_category,
                "item_name": item_name,
                "quantity": quantity,
                "unit": unit,
                "unit_cost": unit_cost,
                "total_amount": total_amount,
            }
        )

    return normalized


def _coerce_master_payload(parsed: Any) -> Dict[str, Any]:
    if isinstance(parsed, dict):
        # 🚀 THE FIX: Tell the bouncer to specifically grab the revenue!
        extracted_rev = _to_float(
            parsed.get("total_revenue") or parsed.get("gross_sales") or parsed.get("revenue"), 
            0.0
        )

        if "operating_expenses" in parsed or "supplier_invoices" in parsed:
            return {
                "document_type": str(parsed.get("document_type", "unknown")).strip().lower(),
                "total_revenue": extracted_rev, # 👈 Officially supported!
                "operating_expenses": parsed.get("operating_expenses") or parsed.get("expenses") or [],
                "supplier_invoices": parsed.get("supplier_invoices") or parsed.get("invoices") or parsed.get("items") or [],
            }

        if "expense_type" in parsed and "amount" in parsed:
            return {
                "document_type": "pl_statement",
                "total_revenue": extracted_rev,
                "operating_expenses": [parsed],
                "supplier_invoices": [],
            }
        if "item_name" in parsed and "total_amount" in parsed:
            return {
                "document_type": "supplier_invoice",
                "total_revenue": extracted_rev,
                "operating_expenses": [],
                "supplier_invoices": [parsed],
            }

        return {
            "document_type": str(parsed.get("document_type", "unknown")).strip().lower(),
            "total_revenue": extracted_rev,
            "operating_expenses": [],
            "supplier_invoices": [],
        }

    # If it's a list, fallback
    return {
        "document_type": "unknown",
        "total_revenue": 0.0,
        "operating_expenses": [],
        "supplier_invoices": [],
    }


def _normalize_roadmap_payload(parsed: Any) -> Dict[str, Any]:
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="Roadmap model returned invalid schema: expected object")

    estimated_total_days = int(_to_float(parsed.get("estimated_total_days"), 0.0))
    if estimated_total_days < 1:
        estimated_total_days = 1

    raw_phases = parsed.get("phases", [])
    if not isinstance(raw_phases, list):
        raw_phases = []

    phases: List[Dict[str, Any]] = []
    for i, raw_phase in enumerate(raw_phases, start=1):
        if not isinstance(raw_phase, dict):
            continue

        raw_tasks = raw_phase.get("tasks", [])
        if not isinstance(raw_tasks, list):
            raw_tasks = []

        tasks = [str(task).strip() for task in raw_tasks if str(task).strip()]
        if not tasks:
            continue

        phase_number = int(_to_float(raw_phase.get("phase_number"), float(i)))
        if phase_number < 1:
            phase_number = i

        title = str(raw_phase.get("title", f"Phase {phase_number}")).strip() or f"Phase {phase_number}"

        phases.append(
            {
                "phase_number": phase_number,
                "title": title,
                "tasks": tasks,
            }
        )

    if not phases:
        raise HTTPException(status_code=502, detail="Roadmap model returned no usable phases.")

    return {
        "estimated_total_days": estimated_total_days,
        "phases": phases,
    }


def _parse_sales_logs_csv(csv_bytes: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read sales CSV: {exc}") from exc

    if df.empty:
        raise HTTPException(status_code=400, detail="Sales CSV is empty")

    normalized_cols = {str(c).strip().lower(): c for c in df.columns}
    required = ["order_id", "timestamp", "item_name", "quantity", "price"]
    missing = [col for col in required if col not in normalized_cols]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Sales CSV missing required columns: {', '.join(missing)}",
        )

    selected = pd.DataFrame(
        {
            "order_id": df[normalized_cols["order_id"]],
            "timestamp": df[normalized_cols["timestamp"]],
            "item_name": df[normalized_cols["item_name"]],
            "quantity": df[normalized_cols["quantity"]],
            "price": df[normalized_cols["price"]],
        }
    )

    selected["logged_at"] = pd.to_datetime(selected["timestamp"], errors="coerce", utc=True)
    selected["order_id"] = selected["order_id"].astype(str).str.strip()
    selected["item_name"] = selected["item_name"].astype(str).str.strip()
    selected["quantity"] = pd.to_numeric(selected["quantity"], errors="coerce")
    selected["price"] = pd.to_numeric(selected["price"], errors="coerce")

    selected = selected.dropna(subset=["logged_at", "quantity", "price"])
    selected = selected[selected["item_name"] != ""]
    selected["quantity"] = selected["quantity"].astype(int)
    selected = selected[selected["quantity"] > 0]
    selected = selected[selected["price"] >= 0]

    if selected.empty:
        raise HTTPException(status_code=400, detail="Sales CSV has no valid rows after cleaning")

    return selected[["order_id", "item_name", "quantity", "price", "logged_at"]]


def _month_window(report_month: str) -> Tuple[str, str]:
    year = int(report_month[:4])
    month = int(report_month[5:7])

    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    return start.isoformat(), end.isoformat()


def _ingest_sales_logs(
    supabase: Client,
    merchant_id: str,
    report_month: str,
    sales_df: pd.DataFrame,
    batch_size: int = 1000,
) -> Tuple[int, float, Dict[str, float]]:
    start_iso, end_iso = _month_window(report_month)
    start_ts = pd.Timestamp(start_iso)
    end_ts = pd.Timestamp(end_iso)

    # Idempotency strategy: clear this merchant's month window before re-insert.
    supabase.table("sales_logs").delete().eq("merchant_id", merchant_id).gte("logged_at", start_iso).lt("logged_at", end_iso).execute()

    month_df = sales_df[(sales_df["logged_at"] >= start_ts) & (sales_df["logged_at"] < end_ts)].copy()
    if month_df.empty:
        raise HTTPException(status_code=400, detail="Sales CSV has no rows matching report_month window")

    month_df["merchant_id"] = merchant_id
    month_df["logged_at"] = month_df["logged_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    month_df["quantity"] = month_df["quantity"].astype(int)
    month_df["price"] = month_df["price"].astype(float)

    # Avoid duplicate rows inside the uploaded file itself.
    month_df = month_df.drop_duplicates(subset=["order_id", "item_name", "logged_at", "quantity", "price"])

    records = month_df[["merchant_id", "order_id", "item_name", "quantity", "price", "logged_at"]].to_dict(orient="records")

    inserted_count = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        supabase.table("sales_logs").insert(batch).execute()
        inserted_count += len(batch)

    month_df["line_revenue"] = month_df["quantity"] * month_df["price"]
    total_revenue = round(float(month_df["line_revenue"].sum()), 2)
    grouped = month_df.groupby("item_name", dropna=False)["line_revenue"].sum()
    category_revenue = {str(k): round(float(v), 2) for k, v in grouped.to_dict().items()}

    return inserted_count, total_revenue, category_revenue


def _normalize_report_month(report_month: str) -> str:
    value = report_month.strip()
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise HTTPException(status_code=400, detail="report_month must be YYYY-MM")

    year = int(value[:4])
    month = int(value[5:7])
    if year < 2000 or month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="report_month must be a valid month in YYYY-MM")

    return f"{year:04d}-{month:02d}"


def _upsert_monthly_summary(supabase: Client, payload: Dict[str, Any]) -> str:
    try:
        response = (
            supabase.table("monthly_summaries")
            .upsert(payload, on_conflict="merchant_id,report_month")
            .execute()
        )
        if response.data and response.data[0].get("id"):
            return str(response.data[0]["id"])
    except Exception:
        pass

    existing = (
        supabase.table("monthly_summaries")
        .select("id")
        .eq("merchant_id", payload["merchant_id"])
        .eq("report_month", payload["report_month"])
        .limit(1)
        .execute()
    )

    if existing.data:
        summary_id = str(existing.data[0]["id"])
        supabase.table("monthly_summaries").update(payload).eq("id", summary_id).execute()
        return summary_id

    inserted = supabase.table("monthly_summaries").insert(payload).execute()
    if inserted.data and inserted.data[0].get("id"):
        return str(inserted.data[0]["id"])

    raise HTTPException(status_code=500, detail="Failed to upsert monthly summary")


def _replace_operating_expenses(supabase: Client, summary_id: str, rows: List[Dict[str, Any]]) -> int:
    supabase.table("operating_expenses").delete().eq("summary_id", summary_id).execute()

    if not rows:
        return 0

    payload = [
        {
            "summary_id": summary_id,
            "expense_type": row["expense_type"],
            "amount": row["amount"],
        }
        for row in rows
    ]

    supabase.table("operating_expenses").insert(payload).execute()
    return len(payload)

@app.get("/analyze-surroundings/{merchant_id}")
async def analyze_surroundings(merchant_id: str, lat: float, lon: float):
    # Now it fetches everything: Offices, Schools, Banks, etc.
     # Uses a 1km radius so the AI has a full picture of who is around the shop.
    neighborhood = get_neighborhood_context(lat, lon)

    # Simple logic for the summary message
    office_count = len([x for x in neighborhood if x['category'] == "Office/Workplace"])
    edu_count = len([x for x in neighborhood if x['category'] == "Education"])

    if neighborhood:
        message = (
            f"Location Analysis: {office_count} offices and {edu_count} schools nearby. "
            f"Closest landmark: {neighborhood[0]['name']}."
        )
    else:
        message = "No nearby locations found in 1km."

    return {
        "merchant_id": merchant_id, 
        "neighborhood_data": neighborhood, 
        "note": message
    }

def get_neighborhood_context(lat, lon, radius=1000):
    api_key = _get_google_places_api_key()
    url = "https://places.googleapis.com/v1/places:searchNearby"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.types"
    }

    # 🚀 We now search for a variety of "Business Drivers" 🚀
    payload = {
        "includedTypes": [
            "school", "university", "corporate_office", 
            "business_center", "bank", "government_office",
            "hospital", "park"
        ], 
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": radius # Increased to 1km to catch offices
            }
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        context_items = []
        if "places" in data:
            for place in data["places"]:
                # We categorize them so the AI understands who the audience is
                types = place.get("types", [])
                category = "General"
                if "corporate_office" in types or "business_center" in types:
                    category = "Office/Workplace"
                elif "university" in types or "school" in types:
                    category = "Education"
                
                context_items.append({
                    "name": place["displayName"]["text"],
                    "category": category
                })
        return context_items
    except Exception as e:
        print(f"Neighborhood API Error: {e}")
        return []

def _replace_supplier_invoices(supabase: Client, summary_id: str, rows: List[Dict[str, Any]]) -> int:
    supabase.table("supplier_invoices").delete().eq("summary_id", summary_id).execute()

    if not rows:
        return 0

    payload = [
        {
            "summary_id": summary_id,
            "item_category": row["item_category"],
            "item_name": row["item_name"],
            "quantity": row["quantity"],
            "unit": row["unit"],
            "unit_cost": row["unit_cost"],
            "total_amount": row["total_amount"],
        }
        for row in rows
    ]

    supabase.table("supplier_invoices").insert(payload).execute()
    return len(payload)


def _call_text_llm(
    client: Any, system_prompt: str, user_prompt: str, temperature: float = 0.2
) -> str:
    """Call ILMU glm-5.1 with auto-retry on 504/timeout errors."""
    _ = client  # Kept for call-site compatibility; glm-5.1 now routes via ILMU.

    ilmu_api_key = os.getenv("ILMU_API_KEY")
    if not ilmu_api_key:
        raise HTTPException(
            status_code=500,
            detail="Missing ILMU_API_KEY environment variable for glm-5.1",
        )

    # The only model available on this ILMU subscription is ilmu-glm-5.1
    model_name = os.getenv("ILMU_MODEL", "ilmu-glm-5.1")

    max_retries = 2
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            request_body = {
                "model": model_name,
                "temperature": temperature,
                "max_tokens": 3000,  # Enough for full JSON without truncation
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }

            response = requests.post(
                "https://api.ilmu.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {ilmu_api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
                timeout=90,  # Under Cloudflare's ~100s gateway timeout
            )

            # Detect HTML error pages (504, 502 from Cloudflare)
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type or response.text.strip().startswith("<!DOCTYPE"):
                raise requests.exceptions.ConnectionError(
                    f"ILMU returned HTML error page (HTTP {response.status_code}) — server overloaded, retrying..."
                )

            # Check if the API returned an error code
            if not response.ok:
                error_details = response.text
                try:
                    error_details = response.json()
                except ValueError:
                    pass
                raise Exception(f"HTTP {response.status_code}: {error_details}")

            # SUCCESS — parse the response
            payload = response.json() if response.content else {}
            choices = payload.get("choices") if isinstance(payload, dict) else None
            if not isinstance(choices, list) or not choices:
                raise Exception(f"ILMU text response missing choices: {payload}")

            first_choice = choices[0] if isinstance(choices[0], dict) else {}
            message = first_choice.get("message") if isinstance(first_choice, dict) else {}
            content = message.get("content") if isinstance(message, dict) else ""
            text_output = _extract_model_text(content)

            finish_reason = str(first_choice.get("finish_reason", "")).strip().lower() if isinstance(first_choice, dict) else ""
            if finish_reason in {"content_filter", "sensitive", "blocked"}:
                raise Exception(f"ILMU finish_reason={finish_reason}")

            if not text_output and isinstance(message, dict):
                text_output = _extract_model_text(message.get("reasoning_content"))

            if not text_output and isinstance(first_choice, dict):
                # Fallback for providers that sometimes return top-level text.
                text_output = _extract_model_text(first_choice.get("text"))

            if not text_output and isinstance(payload, dict):
                text_output = _extract_model_text(payload.get("output_text"))

            if not text_output:
                # Debug: log raw payload to diagnose empty content
                print(f"[ILMU Empty] finish_reason={finish_reason!r} | raw payload keys={list(payload.keys()) if isinstance(payload, dict) else type(payload)} | message={str(message)[:200]}")
                raise Exception("ILMU returned empty content in choices[0]")

            return text_output

        except HTTPException:
            raise  # Don't retry on our own validation errors
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_error = exc
            if attempt < max_retries:
                import time as _time
                wait_secs = 3 * (attempt + 1)
                print(f"[ILMU Retry {attempt+1}/{max_retries}] Timeout/connection error, waiting {wait_secs}s: {exc}")
                _time.sleep(wait_secs)
                continue
        except Exception as exc:
            last_error = exc
            exc_str = str(exc).lower()
            retryable = any(
                kw in exc_str
                for kw in [
                    "504",
                    "502",
                    "timeout",
                    "looping",
                    "flagged",
                    "empty content",
                    "missing choices",
                    "content_filter",
                    "blocked",
                ]
            )
            if attempt < max_retries and retryable:
                import time as _time
                wait_secs = 3 * (attempt + 1)
                # Bump temperature on retry to break looping patterns
                temperature = min(temperature + 0.2, 0.8)
                print(f"[ILMU Retry {attempt+1}/{max_retries}] Error (will retry with temp={temperature}), waiting {wait_secs}s: {exc}")
                _time.sleep(wait_secs)
                continue
            break

    # All retries exhausted - FALLBACK TO ZHIPU via async invoke (legacy SDK compatible)
    print(f"[ILMU Failed] Falling back to Zhipu natively due to: {last_error}")
    try:
        if isinstance(client, dict):
            zhipu_client = client.get("client")
        else:
            zhipu_client = client

        if not zhipu_client:
            raise Exception("No Zhipu client available for fallback")

        # Use async invoke which works with legacy SDK 1.0.7
        combined_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
        response = zhipu_client.model_api.async_invoke(
            model="glm-5.1",
            prompt=[{"role": "user", "content": combined_prompt}],
            temperature=min(temperature, 0.9)
        )
        task_id = response.get("data", {}).get("task_id", "")
        if not task_id:
            raise Exception(f"Zhipu async_invoke failed - no task_id: {response}")

        # Poll for result
        import time as _time
        for _ in range(30):
            _time.sleep(2)
            result = zhipu_client.model_api.query_async_invoke_result(task_id)
            task_status = result.get("data", {}).get("task_status", "")
            if task_status == "SUCCESS":
                choices = result.get("data", {}).get("choices", [])
                raw_text = choices[0].get("content", "") if choices else ""
                return _extract_model_text(raw_text)
            elif task_status in ("FAILED", "EXPIRED"):
                raise Exception(f"Zhipu async task {task_status}: {result}")
        raise Exception("Zhipu async task timed out after 60 seconds")
    except Exception as fallback_exc:
        raise HTTPException(
            status_code=502,
            detail=f"ILMU failed and Zhipu fallback also failed: {fallback_exc} (Original ILMU error: {last_error})",
        )
def _get_previous_month(month_str: str) -> str:
    dt = datetime.strptime(f"{month_str}-01", "%Y-%m-%d")
    if dt.month == 1:
        return f"{dt.year - 1}-12"
    return f"{dt.year:04d}-{dt.month - 1:02d}"


def _fetch_diagnostic_patterns(supabase: Client, merchant_id: str, target_month: str) -> Dict[str, Any]:
    res = (
        supabase.table("monthly_summaries")
        .select("diagnostic_patterns")
        .eq("merchant_id", merchant_id)
        .eq("report_month", target_month)
        .limit(1)
        .execute()
    )

    if not res.data:
        raise HTTPException(status_code=404, detail="No monthly summary found for merchant and target_month")

    diagnostic = res.data[0].get("diagnostic_patterns")
    
    # --- 🚀 NEW AUTO-COMPUTE LOGIC 🚀 ---
    if not isinstance(diagnostic, dict):
        print(f"⚡ [Auto-Compute] Diagnostics missing for {target_month}. Crunching data now...")
        
        # Import the math engine directly from your agent_tools file
        from agent_tools import analyze_sales_patterns
        
        # Figure out the baseline month
        baseline_month = _get_previous_month(target_month)
        
        # Run the math engine (this also saves it to Supabase automatically!)
        diagnostic = analyze_sales_patterns(merchant_id, baseline_month, target_month)
        print("✅ [Auto-Compute] Math complete and saved to database.")
    # ------------------------------------

    return diagnostic


def _fetch_financial_comparison(supabase: Client, merchant_id: str, target_month: str) -> Dict[str, Any]:
    baseline_month = _get_previous_month(target_month)

    baseline_res = (
        supabase.table("monthly_summaries")
        .select("report_month,total_revenue,total_fixed_costs,net_profit")
        .eq("merchant_id", merchant_id)
        .eq("report_month", baseline_month)
        .limit(1)
        .execute()
    )
    target_res = (
        supabase.table("monthly_summaries")
        .select("report_month,total_revenue,total_fixed_costs,net_profit")
        .eq("merchant_id", merchant_id)
        .eq("report_month", target_month)
        .limit(1)
        .execute()
    )

    # Gracefully degrade when baseline month has no data yet (common for new merchants)
    baseline: Dict[str, Any] = baseline_res.data[0] if baseline_res.data else {}
    if not target_res.data:
        raise HTTPException(status_code=404, detail=f"No target month data found for {target_month}")
    target = target_res.data[0]

    return {
        "baseline_month": baseline_month,
        "target_month": target_month,
        "baseline": {
            "report_month": baseline.get("report_month", baseline_month),
            "total_revenue": _to_float(baseline.get("total_revenue"), 0.0),
            "total_fixed_costs": _to_float(baseline.get("total_fixed_costs"), 0.0),
            "net_profit": _to_float(baseline.get("net_profit"), 0.0),
        },
        "target": {
            "report_month": target.get("report_month", target_month),
            "total_revenue": _to_float(target.get("total_revenue"), 0.0),
            "total_fixed_costs": _to_float(target.get("total_fixed_costs"), 0.0),
            "net_profit": _to_float(target.get("net_profit"), 0.0),
        },
    }


def _fetch_financial_trend(
    supabase: Client,
    merchant_id: str,
    target_month: str,
    max_context_months: int = 12,
) -> Dict[str, Any]:
    history_res = (
        supabase.table("monthly_summaries")
        .select("report_month,total_revenue,net_profit")
        .eq("merchant_id", merchant_id)
        .lte("report_month", target_month)
        .order("report_month", desc=False)
        .limit(max_context_months + 1)
        .execute()
    )

    rows = history_res.data or []

    # Gracefully handle merchants with no history yet — synthesise a stub row
    if not rows:
        stub = {
            "report_month": target_month,
            "total_revenue": 0.0,
            "net_profit": 0.0,
        }
        return {
            "target_month": stub,
            "context_depth_months": 0,
            "rolling_averages": {"avg_revenue": 0.0, "avg_profit": 0.0},
            "historical_curve": [],
        }

    normalized_rows: List[Dict[str, Any]] = []
    target_row: Optional[Dict[str, Any]] = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        report_month = str(row.get("report_month") or "").strip()
        if not report_month:
            continue
        normalized = {
            "report_month": report_month,
            "total_revenue": _to_float(row.get("total_revenue"), 0.0),
            "net_profit": _to_float(row.get("net_profit"), 0.0),
        }
        normalized_rows.append(normalized)
        if report_month == target_month:
            target_row = normalized

    # If target month row not found, use the latest available row as a stub
    if target_row is None:
        target_row = normalized_rows[-1] if normalized_rows else {
            "report_month": target_month,
            "total_revenue": 0.0,
            "net_profit": 0.0,
        }

    historical_rows = [r for r in normalized_rows if r["report_month"] < target_month]
    if len(historical_rows) > max_context_months:
        historical_rows = historical_rows[-max_context_months:]

    context_depth = len(historical_rows)
    if context_depth > 0:
        avg_revenue = round(sum(r["total_revenue"] for r in historical_rows) / context_depth, 2)
        avg_profit = round(sum(r["net_profit"] for r in historical_rows) / context_depth, 2)
    else:
        avg_revenue = round(target_row["total_revenue"], 2)
        avg_profit = round(target_row["net_profit"], 2)

    historical_curve = [
        {"month": r["report_month"], "net_profit": round(r["net_profit"], 2)} for r in historical_rows
    ]

    return {
        "target_month": {
            "report_month": target_row["report_month"],
            "total_revenue": round(target_row["total_revenue"], 2),
            "net_profit": round(target_row["net_profit"], 2),
        },
        "context_depth_months": context_depth,
        "rolling_averages": {
            "avg_revenue": avg_revenue,
            "avg_profit": avg_profit,
        },
        "historical_curve": historical_curve,
    }


def _build_financial_context_payload(supabase: Client, merchant_id: str, target_month: str) -> Dict[str, Any]:
    # Gracefully handle merchants without enough historical data yet
    try:
        financial_trend = _fetch_financial_trend(supabase, merchant_id, target_month)
    except Exception:
        financial_trend = {
            "target_month": {"report_month": target_month, "total_revenue": 0.0, "net_profit": 0.0},
            "context_depth_months": 0,
            "rolling_averages": {"avg_revenue": 0.0, "avg_profit": 0.0},
            "historical_curve": [],
        }

    try:
        diagnostic_patterns = _fetch_diagnostic_patterns(supabase, merchant_id, target_month)
    except Exception:
        diagnostic_patterns = {}

    return {
        "financial_trend": financial_trend,
        "diagnostic_patterns": diagnostic_patterns,
    }


def _fetch_traffic_signal(lat: float, lon: float) -> Dict[str, Any]:
    api_key = _get_google_places_api_key()
    if not api_key:
        return {"attempted": True, "status": "error", "error": "Missing GOOGLE_PLACES_API_KEY", "data": {}}

    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.condition"
    }
    
    # Simulate a short trip to measure local traffic density
    payload = {
        "origin": {"location": {"latLng": {"latitude": lat, "longitude": lon}}},
        "destination": {"location": {"latLng": {"latitude": lat + 0.01, "longitude": lon + 0.01}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE"
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        duration = int(data["routes"][0]["duration"][:-1])
        static_duration = int(data["routes"][0]["staticDuration"][:-1])
        delay = duration - static_duration
        
        status = "Heavy Traffic" if delay > 300 else "Clear"
        return {"attempted": True, "status": "ok", "provider": "google_routes", "data": {"traffic_status": status, "delay_seconds": delay}}
    except Exception as exc:
        return {"attempted": True, "status": "error", "error": str(exc), "data": {}}

def _fetch_foot_traffic_signal(lat: float, lon: float) -> Dict[str, Any]:
    api_key = os.getenv("BESTTIME_API_KEY")
    if not api_key:
        return {"attempted": True, "status": "ok", "provider": "simulation", "data": {"status": "Busy", "live_intensity": 85, "note": "Simulated foot traffic"}}

    url = "https://besttime.app/api/v1/forecasts/now"
    params = {"api_key_private": api_key, "lat": lat, "lng": lon}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") == "OK":
            analysis = data.get("analysis", {})
            return {
                "attempted": True, 
                "status": "ok", 
                "provider": "besttime", 
                "data": {
                    "status": analysis.get("venue_forecast_status", "Normal"),
                    "live_intensity": analysis.get("venue_live_busyness", 50)
                }
            }
        return {"attempted": True, "status": "error", "error": "API returned non-OK status", "data": {}}
    except Exception as exc:
        return {"attempted": True, "status": "error", "error": str(exc), "data": {}}
    
def get_coordinates(address):
    api_key = _get_google_places_api_key()
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
    try:
        response = requests.get(url).json()
        if response.get("status") == "OK":
            location = response["results"][0]["geometry"]["location"]
            return location["lat"], location["lng"]
        return None, None
    except Exception as e:
        print(f"Geocoding Error: {e}")
        return None, None
    
# Turns coordinates back into a human-readable address (e.g. full street address)
def reverse_geocode(lat: float, lon: float):
    api_key = _get_google_places_api_key()
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={api_key}"
    try:
        response = requests.get(url).json()
        if response.get("status") == "OK":
            return response["results"][0]["formatted_address"]
        return "Unknown Location"
    except Exception as e:
        return f"Error: {e}"
    
def get_details_from_place_id(place_id: str):
    api_key = _get_google_places_api_key()
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&key={api_key}"
    try:
        response = requests.get(url).json()
        if response.get("status") == "OK":
            location = response["result"]["geometry"]["location"]
            return location["lat"], location["lng"]
        return None, None
    except Exception as e:
        print(f"Place Details Error: {e}")
        return None, None
    
def _fetch_merchant_profile(supabase: Client, merchant_id: str) -> str:
    res = (
        supabase.table("merchants")
        .select("merchant_profile")
        .eq("id", merchant_id)
        .limit(1)
        .execute()
    )

    if not res.data:
        return ""
    return str(res.data[0].get("merchant_profile") or "").strip()


def _extract_location_hint(merchant_profile: str) -> str:
    if merchant_profile.strip():
        return merchant_profile
    return "Malaysia"


def _target_month_date_range(target_month: str) -> Tuple[str, str]:
    month_start = datetime.strptime(f"{target_month}-01", "%Y-%m-%d")
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    month_end = (next_month - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    return month_start.strftime("%Y-%m-%d"), month_end


# 👇 Notice we added merchant_profile so we can search for local news!
def _fetch_news_signal(merchant_profile: str, target_month: str) -> Dict[str, Any]:
    gnews_api_key = os.getenv("GNEWS_API_KEY")
    if not gnews_api_key:
        return {"attempted": True, "status": "error", "error": "Missing GNEWS_API_KEY", "data": []}

    start_date, end_date = _target_month_date_range(target_month)
    
    # 1. 🚨 We use the location hint to get hyper-local news! 🚨
    location_hint = _extract_location_hint(merchant_profile)
    # 👇 🚨 THE HYBRID QUERY 🚨 👇
    # We tell GNews to find EITHER local events OR Malaysia-wide economic shifts (petrol, inflation, tax, subsidies).
    # We also remove {target_month} from the text string because the `start_date` and `end_date` parameters already filter the exact dates perfectly!
    query = f'("{location_hint}" AND (cafe OR food OR event)) OR (Malaysia AND (economy OR petrol OR inflation OR subsidy OR tax))'
    
    try:
        url = "https://gnews.io/api/v4/search"
        params = {
            "query": query,
            "from": start_date,
            "to": end_date,
            "lang": "en",
            "country": "my",
            "max": 5,
            "sortby": "publishedAt",
            "apikey": gnews_api_key,
        }
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("articles", []) if isinstance(data, dict) else []
        compact = [
            {
                "title": row.get("title", ""),
                # 2. 🚨 We copied the description extraction from main.py 🚨
                "description": row.get("description", ""), 
                "source": (row.get("source") or {}).get("name", "") if isinstance(row.get("source"), dict) else "",
                "published_at": row.get("publishedAt", ""),
            }
            for row in rows[:5]
            if isinstance(row, dict)
        ]
        return {"attempted": True, "status": "ok", "provider": "gnews", "data": compact}
    except Exception as exc:
        return {"attempted": True, "status": "error", "error": str(exc), "data": []}


# 👇 Notice we added merchant_profile as a parameter here to get the location!
def _fetch_web_signal(merchant_profile: str, target_month: str) -> Dict[str, Any]:
    serper_api_key = os.getenv("SERPER_API_KEY")
    if not serper_api_key:
        return {"attempted": True, "status": "error", "error": "Missing SERPER_API_KEY", "data": []}

    # 1. We copy the location trick from main.py
    location_hint = _extract_location_hint(merchant_profile)
    query = f"cafe menu prices OR coffee promotion near {location_hint} {target_month}"
    
    try:
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
        payload = {"q": query, "gl": "my", "hl": "en", "num": 5}
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        body = resp.json()
        rows = body.get("organic", []) if isinstance(body, dict) else []
        compact = [
            {
                "title": row.get("title", ""),
                # 2. 🚨 We copied the snippet extraction from main.py 🚨
                "snippet": row.get("snippet", ""), 
                "date": row.get("date", ""),
                "url": row.get("link", ""),
            }
            for row in rows[:5]
            if isinstance(row, dict)
        ]
        return {"attempted": True, "status": "ok", "provider": "serper", "data": compact}
    except Exception as exc:
        return {"attempted": True, "status": "error", "error": str(exc), "data": []}


def _fetch_places_signal(merchant_profile: str) -> Dict[str, Any]:
    """Fetch nearby competitor cafes/restaurants using Google Places Text Search API."""
    places_api_key = _get_google_places_api_key()
    if not places_api_key:
        return {
            "attempted": True,
            "status": "error",
            "error": "Missing GOOGLE_PLACES_API_KEY / GOOGLE_PLACE_API_KEY",
            "data": {},
        }

    location_hint = _extract_location_hint(merchant_profile)
    query = f"cafe OR restaurant near {location_hint}"
    try:
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": query,
            "key": places_api_key,
        }
        resp = requests.get(url, params=params, timeout=25)
        resp.raise_for_status()
        body = resp.json()
        rows = body.get("results", []) if isinstance(body, dict) else []
        top_places = [
            {
                "name": row.get("name", ""),
                "rating": row.get("rating"),
                "user_ratings_total": row.get("user_ratings_total"),
                "business_status": row.get("business_status", ""),
                "formatted_address": row.get("formatted_address", ""),
            }
            for row in rows[:5]
            if isinstance(row, dict)
        ]
        return {
            "attempted": True,
            "status": "ok",
            "provider": "google_places",
            "data": {"query": query, "nearby_food_venue_count": len(rows), "top_places": top_places},
        }
    except Exception as exc:
        return {"attempted": True, "status": "error", "error": str(exc), "data": {}}


def _fetch_weather_signal(merchant_profile: str, target_month: str) -> Dict[str, Any]:
    weather_api_key = os.getenv("OPENWEATHER_API_KEY")
    if not weather_api_key:
        return {"attempted": True, "status": "error", "error": "Missing OPENWEATHER_API_KEY", "data": {}}

    try:
        geo_url = "https://api.openweathermap.org/geo/1.0/direct"
        geo_params = {"q": _extract_location_hint(merchant_profile), "limit": 1, "appid": weather_api_key}
        geo_resp = requests.get(geo_url, params=geo_params, timeout=20)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if not geo_data:
            return {
                "attempted": True,
                "status": "error",
                "error": "Unable to geocode location from merchant profile.",
                "data": {},
            }

        top = geo_data[0]
        weather_url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": float(top.get("lat")),
            "lon": float(top.get("lon")),
            "appid": weather_api_key,
            "units": "metric",
        }
        resp = requests.get(weather_url, params=params, timeout=25)
        resp.raise_for_status()
        body = resp.json()
        weather = body.get("weather", []) if isinstance(body, dict) else []
        main_obj = body.get("main", {}) if isinstance(body, dict) else {}
        rain_obj = body.get("rain", {}) if isinstance(body, dict) else {}
        summary = {
            "target_month": target_month,
            "location": f"{top.get('name', '')}, {top.get('country', '')}",
            "current_temp_c": _to_float(main_obj.get("temp"), 0.0),
            "humidity_pct": _to_float(main_obj.get("humidity"), 0.0),
            "condition": weather[0].get("main", "") if weather and isinstance(weather[0], dict) else "",
            # 🚨 We copied the detailed description from main.py 🚨
            "description": weather[0].get("description", "") if weather and isinstance(weather[0], dict) else "",
            "rain_1h_mm": _to_float(rain_obj.get("1h"), 0.0),
        }
        return {"attempted": True, "status": "ok", "provider": "openweather", "data": summary}
    except Exception as exc:
        return {"attempted": True, "status": "error", "error": str(exc), "data": {}}


# 👇 Notice we added `supabase` and `merchant_id` to the parameters
def _fetch_external_signals(supabase: Client, merchant_id: str, merchant_profile: str, target_month: str) -> Dict[str, Any]:
    # 1. Fetch existing signals
    news = _fetch_news_signal(merchant_profile, target_month)
    web = _fetch_web_signal(merchant_profile, target_month)
    places = _fetch_places_signal(merchant_profile)
    weather = _fetch_weather_signal(merchant_profile, target_month)
    
    # 2. Fetch the exact Lat/Lon for this merchant from the database
    res = supabase.table("merchants").select("latitude, longitude").eq("owner_id", merchant_id).limit(1).execute()
    
    traffic = {"status": "skipped", "reason": "No coordinates"}
    foot_traffic = {"status": "skipped", "reason": "No coordinates"}
    
    # 3. If they have a location set, run the Live Pulse APIs!
    if res.data and res.data[0].get("latitude") and res.data[0].get("longitude"):
        lat = float(res.data[0]["latitude"])
        lon = float(res.data[0]["longitude"])
        traffic = _fetch_traffic_signal(lat, lon)
        foot_traffic = _fetch_foot_traffic_signal(lat, lon)

    return {
        "news": news,
        "web": web,
        "places": places,
        "weather": weather,
        "traffic": traffic,           # 👈 NEW!
        "foot_traffic": foot_traffic, # 👈 NEW!
    }

def _detective_cards_prompt(
    target_month: str,
    diagnostic_patterns: Dict[str, Any],
    external_signals: Dict[str, Any],
) -> Tuple[str, str]:
    system_prompt = (
        "You are an AI Business Analyst. Synthesize the provided financial diagnostics and external signals into a concise UI data structure. "
        "Return ONLY pure, valid JSON in the exact structure below. Do not include markdown fences or any explanation.\n\n"
        "{\n"
        "  \"performance_summary\": {\n"
        "    \"score\": 8.5,\n"
        "    \"headline\": \"Short 3-5 word headline\",\n"
        "    \"subheadline\": \"1 sentence summary of performance\",\n"
        "    \"insights\": [\n"
        "      {\"id\": 1, \"type\": \"growth\", \"title\": \"Short Title\", \"message\": \"Brief insight about revenue/growth.\"},\n"
        "      {\"id\": 2, \"type\": \"alert\", \"title\": \"Short Title\", \"message\": \"Brief insight about drops or risks.\"},\n"
        "      {\"id\": 3, \"type\": \"efficiency\", \"title\": \"Short Title\", \"message\": \"Brief insight about costs/margins.\"}\n"
        "    ]\n"
        "  },\n"
        "  \"external_intelligence\": [\n"
        "    {\"id\": 1, \"title\": \"Competitor/Event Name\", \"trend\": \"up\", \"percentage\": \"5%\", \"progress\": 60, \"content\": \"Brief description mapping signal to sales.\"}\n"
        "  ] // Max 3 items in external_intelligence\n"
        "}\n\n"
        "Notes: 'type' must be 'growth', 'alert', or 'efficiency'. 'trend' must be 'up' or 'down'. 'progress' is 0-100."
    )
    user_prompt = (
        f"Target Month: {target_month}\n\n"
        "Diagnostics:\n"
        f"{json.dumps(diagnostic_patterns, indent=2)}\n\n"
        "External Signals:\n"
        f"{json.dumps(external_signals, indent=2)}"
    )
    return system_prompt, user_prompt


def _analyst_interrogation_prompt(financial_context: Dict[str, Any]) -> Tuple[str, str]:
    system_prompt = (
        "You are an F&B Analyst. Overall Revenue shifted from [Baseline Revenue] to [Target Revenue]. "
        "Here is the underlying 12-point diagnostic JSON explaining the shifts. Look at this data. "
        "Do not generate a theory yet. Your job is to interrogate the Boss to get real-world context. "
        "Generate up to 5 critical, direct questions (preferably Yes/No or short answer) for the Boss. "
        "Rule 1: You MUST always ask if any specific marketing campaigns, promotions, or discounts were run during the target month. "
        "Rule 2: Base the remaining questions on the largest anomalies in the JSON (e.g., sudden drops in a specific item, or massive shifts in time-of-day traffic). "
        "Rule 3: Keep the questions concise. Do not overwhelm the Boss."
    )
    user_prompt = (
        "Combined Financial Context JSON:\n"
        f"{json.dumps(financial_context, indent=2)}\n\n"
        "Return plain text with numbered questions only."
    )
    return system_prompt, user_prompt


def _analyst_synthesis_prompt(
    merchant_profile: str,
    target_month: str,
    financial_context: Dict[str, Any],
    boss_answers: str,
    external_signals: Dict[str, Any],
) -> Tuple[str, str]:
    system_prompt = (
        "You are an expert F&B Analyst. Evidence-first reasoning is mandatory. "
        "You have been provided with internal sales diagnostics, Boss context, and 4 specific external data signals. "
        "You MUST map the external signals to the internal data using these strict guidelines:\n"
        "1. Weather (OpenWeather): Cross-reference rain or extreme heat with drops in specific time-of-day traffic or cold/hot beverage shifts.\n"
        "2. Competitors (Places): Check if the nearby_food_venue_count or specific high-rated competitors explain a sudden drop in Order Volume.\n"
        "3. Local Events (Web/Serper): Look for local promotions, road closures, or Reddit chatter that aligns with the Boss's answers.\n"
        "4. Macro News (GNews): Look for official holidays, university breaks, or economic news that explains macro shifts.\n\n"
        "You MUST use these external findings as support for the internal data, not as replacement truth. State uncertainty where tools are weak."
    )
    user_prompt = (
        f"Target month: {target_month}\n"
        f"Merchant profile: {merchant_profile}\n\n"
        "Combined Financial Context JSON:\n"
        f"{json.dumps(financial_context, indent=2)}\n\n"
        "Boss answers:\n"
        f"{boss_answers}\n\n"
        "External signals:\n"
        f"{json.dumps(external_signals, indent=2)}\n\n"
        "Write Theory V1 with sections:\n"
        "1) Theory V1 Summary\n"
        "2) Internal Data Evidence\n"
        "3) Boss Context Evidence\n"
        "4) External Evidence\n"
        "5) Magnitude Check\n"
        "6) Strategic Recommendation (So What)\n"
        "7) Confidence and Unknowns"
    )
    return system_prompt, user_prompt


def _supervisor_review_prompt(
    diagnostic_json: Dict[str, Any],
    boss_answers: str,
    theory_v1: str,
    external_signals: Dict[str, Any],
) -> Tuple[str, str]:
    system_prompt = (
        "You are the ruthless CFO Supervisor. Review the Analyst's Theory V1 against the original "
        "JSON data and the Boss's answers. You are the gatekeeper. "
        "Reject if tools/data are missing, if major claims are ungrounded, if boss answers are ignored, "
        "if magnitude logic fails, or if no actionable recommendation exists. "
        "Approve only when all checks pass."
    )
    user_prompt = (
        "Original diagnostic JSON:\n"
        f"{json.dumps(diagnostic_json, indent=2)}\n\n"
        "Boss answers:\n"
        f"{boss_answers}\n\n"
        "External tool outputs:\n"
        f"{json.dumps(external_signals, indent=2)}\n\n"
        "Analyst Theory V1:\n"
        f"{theory_v1}\n\n"
        "Return in this format:\n"
        "Decision: APPROVED or REJECTED\n"
        "Gate Checks:\n"
        "- Tool/Data Coverage: PASS/FAIL\n"
        "- Internal Grounding: PASS/FAIL\n"
        "- Boss Alignment: PASS/FAIL\n"
        "- Magnitude Test: PASS/FAIL\n"
        "- So-What Rule: PASS/FAIL\n"
        "Supervisor Verdict: (short, sharp evaluation)"
    )
    return system_prompt, user_prompt


def _extract_supervisor_decision(supervisor_evaluation: str) -> str:
    text = (supervisor_evaluation or "").upper()
    match = re.search(r"DECISION\s*:\s*(APPROVED|REJECTED)", text)
    if match:
        return match.group(1)
    if "APPROVED" in text and "REJECTED" not in text:
        return "APPROVED"
    if "REJECTED" in text:
        return "REJECTED"
    return "UNKNOWN"


def _strategist_action_plan_prompt(
    merchant_profile: str,
    diagnostic_json: Dict[str, Any],
    boss_answers: str,
    final_approved_theory: str,
    external_signals: Dict[str, Any], # 👈 NEW: Add this parameter
) -> Tuple[str, str]:
    system_prompt = (
        "You are an elite F&B Business Strategist. You have just read the Final Theory regarding why this business's revenue shifted. "
        "You also have their 12-point internal data patterns, their merchant profile, and real-world external signals. "
        "Your task is to generate the 'Top 3 Strategic Action Plans' for the Boss to execute immediately.\n\n"
        "Strict Rules:\n\n"
        "No Generic Advice: Do NOT say 'Run a social media campaign' or 'Offer a discount.'\n\n"
        "Hyper-Specific: You must name specific items from their data... and suggest specific price points or bundle strategies...\n\n"
        "Context Aware: You MUST factor in the external signals (weather, events, competitors) when designing these strategies.\n\n"
        "Format: Output the response as 3 distinct, bolded Action Items, each followed by a short paragraph explaining the exact 'Why' "
        "and 'How' based strictly on the data."
    )
    user_prompt = (
        f"Merchant profile:\n{merchant_profile}\n\n"
        "12-point diagnostic JSON:\n"
        f"{json.dumps(diagnostic_json, indent=2)}\n\n"
        "External Signals (Weather, Events, Competitors):\n" # 👈 NEW: Injecting the data
        f"{json.dumps(external_signals, indent=2)}\n\n"
        "Boss answers:\n"
        f"{boss_answers}\n\n"
        "Final approved theory:\n"
        f"{final_approved_theory}\n"
    )
    return system_prompt, user_prompt


@app.get("/health")
def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}

@app.post("/auth/signup")
async def signup(req: SignupRequest):
    supabase = get_supabase_client()
    try:
        # 1. Create the user in Supabase Auth
        auth_response = supabase.auth.sign_up({"email": req.email, "password": req.password})
        
        if auth_response.user:
            user_id = auth_response.user.id
            
            # 2. Insert into your merchants table
            merchant_data = {
                "owner_id": user_id, 
                "name": req.business_name # Maps to the "name" column in your schema
                # We leave "type" out, so it defaults to null per your schema
            }
            supabase.table("merchants").insert(merchant_data).execute()
            
            return {"status": "success", "owner_id": user_id}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/auth/login")
async def login(req: LoginRequest):
    supabase = get_supabase_client()
    try:
        response = supabase.auth.sign_in_with_password({"email": req.email, "password": req.password})
        return {
            "status": "success",
            "message": "Login successful!",
            "access_token": response.session.access_token,
            "owner_id": response.user.id
        }
    except Exception as e:
        return {"status": "error", "message": f"Login failed: {e}"}

@app.post("/auth/sync-google-profile")
async def sync_google_profile(req: GoogleSyncRequest):
    supabase = get_supabase_client()
    try:
        user_response = supabase.auth.get_user(req.access_token)
        if not user_response.user:
            return {"status": "error", "message": "Invalid access token"}

        user_id = user_response.user.id
        
        # 1. Check if the shop exists
        existing_shop = supabase.table("merchants").select("*").eq("owner_id", user_id).execute()
        
        if existing_shop.data:
            shop = existing_shop.data[0]
            # Check if they have filled out their target audience yet
            is_complete = bool(shop.get("target_audience"))
            
            return {
                "status": "success", 
                "message": "Welcome back!", 
                "owner_id": user_id, 
                "profile_complete": is_complete # 👈 SMART FLAG
            }

        # 2. If no shop exists, CREATE IT NOW with their Google Name
        merchant_data = {"owner_id": user_id, "name": req.name}
        supabase.table("merchants").insert(merchant_data).execute()
        
        return {
            "status": "success", 
            "message": "Shop created!", 
            "owner_id": user_id, 
            "profile_complete": False # 👈 They definitely need to configure it
        }
    except Exception as e:
        return {"status": "error", "message": f"Google sync failed: {e}"}

@app.post("/merchants/update-location")
async def update_location(req: LocationUpdateRequest):
    supabase = get_supabase_client()
    try:
        final_lat, final_lon, final_address = req.lat, req.lon, req.address

        # Scenario A: User selected a Place from a dropdown (Place ID)
        if req.place_id:
            final_lat, final_lon = get_details_from_place_id(req.place_id)
            final_address = reverse_geocode(final_lat, final_lon)

         # Scenario B: User typed a manual address but we need coordinates
        elif req.address and (final_lat is None or final_lon is None):
            final_lat, final_lon = get_coordinates(req.address)

        # Scenario C: User used GPS (Lat/Lon) but we need the readable address
        elif final_lat and final_lon and not req.address:
            final_address = reverse_geocode(final_lat, final_lon)

        if final_lat is None or final_lon is None:
            return {"status": "error", "message": "Could not determine coordinates."}

        #save to database
        update_data = {"address": final_address, "latitude": final_lat, "longitude": final_lon}
        supabase.table("merchants").update(update_data).eq("owner_id", req.merchant_id).execute()

        return {"status": "success", "message": "Shop location updated!", "updated_data": update_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
@app.post("/merchants/setup-profile")
async def setup_profile(req: ProfileSetupRequest):
    supabase = get_supabase_client()
    try:
        update_data = {
            "name": req.name,
            "type": req.type,
            "pricing_tier": req.pricing_tier,
            "operating_hours": req.operating_hours,
            "target_audience": req.target_audience, # JSONB handles dicts automatically
            "address": req.address,
            "latitude": req.latitude,
            "longitude": req.longitude
        }
        
        # Use owner_id to update the specific merchant record
        supabase.table("merchants").update(update_data).eq("owner_id", req.merchant_id).execute()
        
        return {"status": "success", "message": "Profile fully initialized!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/analyze-financial-document")
def analyze_financial_document(payload: AnalyzeFinancialDocumentRequest) -> Dict[str, Any]:
    mime, raw_bytes = _decode_data_url(payload.file_data_url)

    if mime in {"image/png", "image/jpeg", "image/jpg"}:
        pages = [payload.file_data_url]
    elif mime == "application/pdf":
        pages = _render_pdf_pages_as_data_urls(raw_bytes)
        if not pages:
            raise HTTPException(status_code=400, detail="PDF has no renderable pages")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file mime type: {mime}")

    client = get_zhipu_client()

    operating_expenses: List[Dict[str, Any]] = []
    supplier_invoices: List[Dict[str, Any]] = []
    extraction_errors: List[str] = []
    detected_types: set[str] = set()

    for page_index, page_data_url in enumerate(pages, start=1):
        # Single-pass extraction per page with a strict master schema.
        try:
            parsed = _vision_json(client, page_data_url, MASTER_EXTRACT_PROMPT)
            parsed_obj = _coerce_master_payload(parsed)

            page_type = str(parsed_obj.get("document_type", "")).strip().lower()
            if page_type in {"pl_statement", "supplier_invoice", "mixed"}:
                detected_types.add(page_type)

            operating_expenses.extend(_normalize_pl_rows(parsed_obj.get("operating_expenses", [])))
            supplier_invoices.extend(_normalize_invoice_rows(parsed_obj.get("supplier_invoices", [])))
        except HTTPException as exc:
            extraction_errors.append(f"page {page_index} extract: {exc.detail}")

    if not operating_expenses and not supplier_invoices:
        reason = "; ".join(extraction_errors[:4]) if extraction_errors else "Vision output did not match expected schemas"
        raise HTTPException(
            status_code=422,
            detail=f"No extractable financial rows found from vision scan. Reason: {reason}",
        )

    if "mixed" in detected_types or (operating_expenses and supplier_invoices):
        document_type = "mixed"
    elif "pl_statement" in detected_types or operating_expenses:
        document_type = "pl_statement"
    elif "supplier_invoice" in detected_types or supplier_invoices:
        document_type = "supplier_invoice"
    else:
        document_type = "unknown"

    return {
        "file_name": payload.file_name,
        "document_type": document_type,
        "operating_expenses": operating_expenses,
        "supplier_invoices": supplier_invoices,
    }


@app.post("/process-monthly-upload")
def process_monthly_upload(payload: ProcessMonthlyUploadRequest) -> Dict[str, Any]:
    report_month = _normalize_report_month(payload.report_month)

    csv_mime, csv_bytes = _decode_data_url(payload.sales_csv_data_url)
    if csv_mime not in {"text/csv", "application/vnd.ms-excel", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail=f"Unsupported sales CSV mime type: {csv_mime}")

    sales_df = _parse_sales_logs_csv(csv_bytes)

    operating_expenses: List[Dict[str, Any]] = []
    supplier_invoices: List[Dict[str, Any]] = []

    for doc in payload.scanned_documents:
        if not isinstance(doc, dict):
            continue
        operating_expenses.extend(_normalize_pl_rows(doc.get("operating_expenses", [])))
        supplier_invoices.extend(_normalize_invoice_rows(doc.get("supplier_invoices", [])))

    supabase = get_supabase_client()
    inserted_sales_logs, total_revenue, category_revenue = _ingest_sales_logs(
        supabase=supabase,
        merchant_id=payload.merchant_id.strip(),
        report_month=report_month,
        sales_df=sales_df,
        batch_size=1000,
    )

    total_fixed_costs = round(sum(row["amount"] for row in operating_expenses), 2)
    total_ingredient_costs = round(sum(row["total_amount"] for row in supplier_invoices), 2)
    net_profit = round(total_revenue - (total_fixed_costs + total_ingredient_costs), 2)

    summary_payload = {
        "merchant_id": payload.merchant_id.strip(),
        "report_month": report_month,
        "total_revenue": total_revenue,
        "total_fixed_costs": total_fixed_costs,
        "total_ingredient_costs": total_ingredient_costs,
        "net_profit": net_profit,
        "category_revenue": category_revenue,
    }

    summary_id = _upsert_monthly_summary(supabase, summary_payload)

    inserted_expenses = _replace_operating_expenses(supabase, summary_id, operating_expenses)
    inserted_invoices = _replace_supplier_invoices(supabase, summary_id, supplier_invoices)

    supabase.table("monthly_summaries").update(summary_payload).eq("id", summary_id).execute()

    return {
        "summary_id": summary_id,
        "merchant_id": payload.merchant_id,
        "report_month": report_month,
        "merchant_profile": payload.merchant_profile.strip(),
        "total_revenue": total_revenue,
        "total_fixed_costs": total_fixed_costs,
        "total_ingredient_costs": total_ingredient_costs,
        "net_profit": net_profit,
        "category_revenue": category_revenue,
        "sales_logs_rows": inserted_sales_logs,
        "operating_expenses_rows": inserted_expenses,
        "supplier_invoices_rows": inserted_invoices,
    }


@app.post("/boardroom/detective-cards")
def boardroom_detective_cards(payload: DetectiveCardsRequest) -> Dict[str, Any]:
    try:
        merchant_id = payload.merchant_id.strip()
        target_month = _normalize_report_month(payload.target_month)
        supabase = get_supabase_client()
        
        # 1. Fetch exact merchant ID
        actual_shop_id = _resolve_merchant_id(supabase, merchant_id)
        
        # 2. Fetch Diagnostic Patterns
        diagnostic_patterns = _fetch_diagnostic_patterns(supabase, actual_shop_id, target_month)
        
        # 3. Fetch External Signals
        merchant_profile = _fetch_merchant_profile(supabase, actual_shop_id)
        external_signals = _fetch_external_signals(supabase, actual_shop_id, merchant_profile, target_month)
        
        # 4. Generate Cards via LLM
        sys_prompt, usr_prompt = _detective_cards_prompt(target_month, diagnostic_patterns, external_signals)
        llm_client = get_zhipu_client()
        
        # 5. We use temperature 0.1 for high determinism since it's formatting JSON
        raw_output = _call_text_llm(llm_client, sys_prompt, usr_prompt, temperature=0.1)
        parsed_cards = _parse_model_json(raw_output, source_name="Detective Cards", required_kind="object")
        
        # Ensure default structure if AI missed something
        if "performance_summary" not in parsed_cards:
            parsed_cards["performance_summary"] = {"score": 0, "headline": "Data Unavailable", "subheadline": "Could not generate summary.", "insights": []}
        if "external_intelligence" not in parsed_cards:
            parsed_cards["external_intelligence"] = []
            
        return {
            "status": "success",
            "data": parsed_cards
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/boardroom/start")
def boardroom_start(payload: BoardroomStartRequest) -> Dict[str, Any]:
    try:
        merchant_id = payload.merchant_id.strip()
        target_month = _normalize_report_month(payload.target_month)

        supabase = get_supabase_client()
        llm_client = get_zhipu_client()

        financial_context = _build_financial_context_payload(supabase, merchant_id, target_month)
        financial_trend = financial_context.get("financial_trend", {})
        diagnostic_json = financial_context.get("diagnostic_patterns", {})

        sys_prompt, usr_prompt = _analyst_interrogation_prompt(financial_context)
        analyst_questions = _call_text_llm(llm_client, sys_prompt, usr_prompt, temperature=0.1)

        return {
            "merchant_id": merchant_id,
            "target_month": target_month,
            "financial_context": financial_context,
            # Backward compatibility for existing frontend consumers.
            "financial_comparison": financial_trend,
            "financial_trend": financial_trend,
            "diagnostic_patterns": diagnostic_json,
            "analyst_questions": analyst_questions,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Boardroom start failed: {exc}") from exc

def _resolve_merchant_id(supabase, frontend_id: str) -> str:
    # 1. Check if the frontend sent the Auth 'owner_id'
    res = supabase.table("merchants").select("shop_id").eq("owner_id", frontend_id).execute()
    if res.data:
        return str(res.data[0]["shop_id"])
    
    # 2. Check if the frontend already sent the real 'shop_id'
    res2 = supabase.table("merchants").select("shop_id").eq("shop_id", frontend_id).execute()
    if res2.data:
        return str(res2.data[0]["shop_id"])
        
    raise HTTPException(status_code=404, detail="Shop not found in DB. Please check your localStorage ID.")

@app.get("/boardroom/trend/{owner_id}/{target_month}")
def get_monthly_trend(owner_id: str, target_month: str):
    try:
        supabase = get_supabase_client()
        # Use your bulletproof resolver!
        actual_merchant_id = _resolve_merchant_id(supabase, owner_id)
        
        # 1. Calculate the start and end of the month
        start_date = f"{target_month}-01T00:00:00Z"
        
        # Quick hack to get the next month for the 'less than' query
        year, month = map(int, target_month.split('-'))
        if month == 12:
            end_date = f"{year + 1}-01-01T00:00:00Z"
        else:
            end_date = f"{year}-{month + 1:02d}-01T00:00:00Z"

        # 2. Fetch all sales for this specific month from your DB
        res = supabase.table("sales_logs") \
            .select("logged_at, price, quantity") \
            .eq("merchant_id", actual_merchant_id) \
            .gte("logged_at", start_date) \
            .lt("logged_at", end_date) \
            .execute()
            
        sales = res.data if res.data else []
        
        # 3. Group the revenue by Day
        daily_revenue = defaultdict(float)
        
        for row in sales:
            # Parse '2026-04-15T14:30:00Z' into a datetime object
            dt = datetime.fromisoformat(row["logged_at"].replace("Z", "+00:00"))
            
            # Format as "15 Apr" for the Recharts X-Axis
            day_str = dt.strftime("%d %b").lstrip("0") 
            
            # Add (Price * Quantity) to that specific day
            daily_revenue[day_str] += float(row["price"] * row["quantity"])

        # 4. Format exactly how Recharts expects it: [{"name": "1 Apr", "revenue": 150}, ...]
        trend_data = [{"name": day, "revenue": round(rev, 2)} for day, rev in daily_revenue.items()]
        
        # Sort it chronologically (Optional, but good if dates are out of order)
        trend_data.sort(key=lambda x: int(x["name"].split(" ")[0]))

        return {
            "status": "success",
            "trend_data": trend_data
        }
        
    except Exception as e:
        print(f"Trend Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/boardroom/continue")
def boardroom_continue(payload: BoardroomContinueRequest) -> Dict[str, Any]:
    try:
        merchant_id = payload.merchant_id.strip()
        target_month = _normalize_report_month(payload.target_month)
        boss_answers = payload.boss_answers.strip()

        supabase = get_supabase_client()
        llm_client = get_zhipu_client()

        financial_context = _build_financial_context_payload(supabase, merchant_id, target_month)
        financial_trend = financial_context.get("financial_trend", {})
        diagnostic_json = financial_context.get("diagnostic_patterns", {})
        merchant_profile = _fetch_merchant_profile(supabase, merchant_id)
        external_signals = _fetch_external_signals(supabase, merchant_id, merchant_profile, target_month)

        analyst_sys, analyst_usr = _analyst_synthesis_prompt(
            merchant_profile=merchant_profile,
            target_month=target_month,
            financial_context=financial_context,
            boss_answers=boss_answers,
            external_signals=external_signals,
        )
        theory_v1 = _call_text_llm(llm_client, analyst_sys, analyst_usr, temperature=0.2)

        sup_sys, sup_usr = _supervisor_review_prompt(
            diagnostic_json=diagnostic_json,
            boss_answers=boss_answers,
            theory_v1=theory_v1,
            external_signals=external_signals,
        )
        supervisor_evaluation = _call_text_llm(llm_client, sup_sys, sup_usr, temperature=0.1)

        supervisor_decision = _extract_supervisor_decision(supervisor_evaluation)
        final_approved_theory = theory_v1 if supervisor_decision == "APPROVED" else ""

        strategist_action_plan = ""
        if supervisor_decision == "APPROVED":
            strategist_sys, strategist_usr = _strategist_action_plan_prompt(
                merchant_profile=merchant_profile,
                diagnostic_json=diagnostic_json,
                boss_answers=boss_answers,
                final_approved_theory=final_approved_theory,
                external_signals=external_signals,
            )
            strategist_action_plan = _call_text_llm(llm_client, strategist_sys, strategist_usr, temperature=0.2)

            supabase.table("monthly_summaries").update({
                "boss_context": boss_answers,
                "approved_theory": final_approved_theory
            }).eq("merchant_id", merchant_id).eq("report_month", target_month).execute()

        return {
            "merchant_id": merchant_id,
            "target_month": target_month,
            "merchant_profile": merchant_profile,
            "financial_context": financial_context,
            "financial_trend": financial_trend,
            "financial_comparison": financial_trend,
            "diagnostic_patterns": diagnostic_json,
            "external_signals": external_signals,
            "theory_v1": theory_v1,
            "supervisor_evaluation": supervisor_evaluation,
            "supervisor_decision": supervisor_decision,
            "final_approved_theory": final_approved_theory,
            "strategist_action_plan": strategist_action_plan,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Boardroom continue failed: {exc}") from exc
    
class BoardroomDebateRequest(BaseModel):
    merchant_id: str = Field(min_length=1)
    target_month: str = Field(min_length=7)
    boss_answers: str = Field(default="")

@app.post("/boardroom/debate")
def boardroom_debate(payload: BoardroomDebateRequest) -> Dict[str, Any]:
    try:
        merchant_id = payload.merchant_id.strip()
        target_month = _normalize_report_month(payload.target_month)
        boss_answers = payload.boss_answers.strip() or "No additional context provided."

        supabase = get_supabase_client()
        llm_client = get_zhipu_client()

        # 1. Fetch Context (no LLM calls yet)
        financial_context = _build_financial_context_payload(supabase, merchant_id, target_month)
        financial_trend = financial_context.get("financial_trend", {})
        diagnostic_json = financial_context.get("diagnostic_patterns", {})
        merchant_profile = _fetch_merchant_profile(supabase, merchant_id)
        external_signals = _fetch_external_signals(supabase, merchant_id, merchant_profile, target_month)

        # ── LLM CALL #1: Generate 3 Strategies AND debate them in one shot ──
        strategy_sys = (
            "You are a board of AI advisors for an F&B business (CMO, COO, CFO). "
            "Based on the provided financial data and boss's context, do two things in sequence:\n"
            "PART A: Generate 3 distinct recovery strategies for the business.\n"
            "PART B: Have CMO, COO, CFO each evaluate those 3 strategies in 1-2 sentences.\n\n"
            "Output PURE JSON — no markdown, no backticks:\n"
            "{\n"
            "  \"cmo_opinion\": \"CMO's 2-sentence take on best strategy and why\",\n"
            "  \"coo_opinion\": \"COO's 2-sentence take on best strategy and why\",\n"
            "  \"cfo_opinion\": \"CFO's 2-sentence take on best strategy and why\",\n"
            "  \"strategies_summary\": \"Brief 1-sentence overview of all 3 strategies considered\"\n"
            "}"
        )
        strategy_usr = (
            f"Merchant: {merchant_profile}\n"
            f"Target Month: {target_month}\n"
            f"Boss Context: {boss_answers}\n"
            f"Financial Diagnostics: {json.dumps(diagnostic_json, indent=2)[:2000]}\n"
            f"Financial Trend: {json.dumps(financial_trend, indent=2)[:1000]}\n"
            f"External Signals: {json.dumps(external_signals, indent=2)[:1000]}\n"
            "Return the JSON."
        )
        opinions_raw = _call_text_llm(llm_client, strategy_sys, strategy_usr, temperature=0.3)
        opinions = _parse_model_json(opinions_raw, source_name="Debate Opinions")
        if not isinstance(opinions, dict):
            opinions = {}

        cmo_text = opinions.get("cmo_opinion", "CMO recommends aggressive growth.")
        coo_text = opinions.get("coo_opinion", "COO recommends phased rollout.")
        cfo_text = opinions.get("cfo_opinion", "CFO recommends margin protection.")
        strategies_summary = opinions.get("strategies_summary", "Three recovery strategies were evaluated.")

        # ── LLM CALL #2: CEO synthesizes the final verdict as JSON ──
        boss_sys = (
            "You are the CEO. Select ONE best strategy from the executives' opinions. "
            "Output ONLY pure JSON (no markdown):\n"
            "{\n"
            "  \"strategies\": [\n"
            "    {\"role\": \"Growth Hacker\", \"icon\": \"trending_up\", \"stance\": \"Aggressive Push\", \"copy\": \"<CMO opinion>\", \"indicatorLabel\": \"Impact\", \"indicatorValue\": \"+15%\", \"tone\": \"up\"},\n"
            "    {\"role\": \"Risk Manager\", \"icon\": \"shield\", \"stance\": \"Margin Protection\", \"copy\": \"<CFO opinion>\", \"indicatorLabel\": \"Risk\", \"indicatorValue\": \"Low\", \"tone\": \"down\"},\n"
            "    {\"role\": \"Operations Chief\", \"icon\": \"account_tree\", \"stance\": \"Phased Rollout\", \"copy\": \"<COO opinion>\", \"indicatorLabel\": \"Readiness\", \"indicatorValue\": \"Stable\", \"tone\": \"neutral\"}\n"
            "  ],\n"
            "  \"recommended_strategy\": {\n"
            "    \"role\": \"Consensus\", \"strategy\": \"<winning strategy title>\", \"argument_for\": \"<why>\", \"argument_against\": \"<risk accepted>\", \"projected_profit_impact\": \"<e.g. +RM 1,200>\"\n"
            "  }\n"
            "}"
        )
        boss_usr = f"CMO: {cmo_text}\nCOO: {coo_text}\nCFO: {cfo_text}\nStrategies overview: {strategies_summary}\n\nReturn JSON."
        boss_text = _call_text_llm(llm_client, boss_sys, boss_usr, 0.2)

        try:
            parsed_data = _parse_model_json(boss_text, source_name="Debate JSON", required_kind="object")
        except Exception:
            parsed_data = {
                "strategies": [
                    {"role": "Growth Hacker", "icon": "trending_up", "stance": "Aggressive Push", "copy": cmo_text, "indicatorLabel": "Impact", "indicatorValue": "High", "tone": "up"},
                    {"role": "Risk Manager", "icon": "shield", "stance": "Margin Protection", "copy": cfo_text, "indicatorLabel": "Risk", "indicatorValue": "Low", "tone": "down"},
                    {"role": "Operations Chief", "icon": "account_tree", "stance": "Phased Rollout", "copy": coo_text, "indicatorLabel": "Readiness", "indicatorValue": "Stable", "tone": "neutral"}
                ],
                "recommended_strategy": {
                    "role": "Consensus", "strategy": "Balanced Execution Strategy",
                    "argument_for": cmo_text, "argument_against": cfo_text,
                    "projected_profit_impact": "+RM 800"
                }
            }

        return {
            "status": "success",
            "strategies": parsed_data.get("strategies", []),
            "recommended_strategy": parsed_data.get("recommended_strategy", {})
        }

    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Debate pipeline failed: {exc}") from exc

@app.post("/sandbox/simulate-what-if")
def simulate_what_if(payload: WhatIfSimulationRequest) -> Dict[str, Any]:
    try:
        supabase = get_supabase_client()
        llm_client = get_zhipu_client()

        # 1. Fetch exact signals
        merchant_profile = _fetch_merchant_profile(supabase, payload.merchant_id)
        external_signals = _fetch_external_signals(supabase, payload.merchant_id, merchant_profile, payload.target_month)
        financial_context = _build_financial_context_payload(supabase, payload.merchant_id, payload.target_month)
        financial_trend = financial_context.get("financial_trend", {})
        diagnostic_patterns = financial_context.get("diagnostic_patterns", {})

        # 2. Dynamic Agent Count (Based on Foot Traffic)
        foot_traffic_data = external_signals.get("foot_traffic", {}).get("data", {})
        if not isinstance(foot_traffic_data, dict):
            foot_traffic_data = {}
        live_intensity = _to_float(foot_traffic_data.get("live_intensity"), 50.0)
        agent_count = max(5, min(100, int(live_intensity)))

        # 3. RUN THE PROFIT-DRIVEN SWARM SIMULATION
        simulation_sys = (
            "You are an advanced Swarm Intelligence Game Master and Financial Auditor. "
            "Your job is to simulate a 'What-If' scenario by generating a raw JSON object.\n\n"
            "STRICT INSTRUCTIONS:\n"
            "1. FINANCIAL COMPARISON: Look at the Current Sales Diagnostics. Estimate what the profit would be WITHOUT the idea (Baseline). Then, estimate the extra costs and extra revenue OF the idea. Calculate the Profit Boost (or Loss).\n"
            "2. THE VERDICT: YOU must make the final call (PROCEED or ABORT) based on whether the Profit Boost is worth the risk, NOT just based on conversion rates.\n"
            f"3. THE SWARM: Generate exactly {agent_count} virtual customer agents inside the 'agents' array. Give them unique traits and logic.\n"
            "4. OUTPUT FORMAT: Return ONLY pure JSON. NO markdown, NO text outside the JSON.\n\n"
            "JSON SCHEMA REQUIREMENT:\n"
            "{\n"
            "  \"financial_analysis\": {\n"
            "    \"baseline_estimated_profit\": 1500,\n"
            "    \"projected_new_profit\": 1800,\n"
            "    \"profit_boost\": 300,\n"
            "    \"final_verdict\": \"PROCEED\",\n"
            "    \"verdict_reason\": \"The RM300 boost outweighs the RM50 staff overtime cost.\"\n"
            "  },\n"
            "  \"agents\": [\n"
            "    {\"id\": 1, \"role\": \"Student\", \"trait\": \"Broke\", \"decision\": \"pass\", \"reason\": \"Too expensive.\"}\n"
            "  ]\n"
            "}"
        )

        simulation_usr = (
            f"--- THE WHAT-IF SCENARIO ---\n"
            f"Boss Idea: {payload.boss_idea}\n\n"
            
            f"--- THE ENVIRONMENT ---\n"
            f"Customer Demographic Distribution: {payload.customer_distribution_json}\n"
            f"Current Weather Data: {json.dumps(external_signals.get('weather', {}))}\n"
            f"Competitor Data: {json.dumps(external_signals.get('web', {}))}\n"
            f"Combined Financial Context JSON: {json.dumps({'financial_trend': financial_trend, 'diagnostic_patterns': diagnostic_patterns})}\n\n"
            
            f"Run the simulation. Generate the financial comparison and exactly {agent_count} agents. Return pure JSON."
        )

        raw_json_response = _call_text_llm(llm_client, simulation_sys, simulation_usr, temperature=0.5)

        # 4. Clean and Parse the JSON safely
        simulation_data = _parse_model_json(
            raw_json_response,
            source_name="Simulation model",
            required_kind="object",
        )

        # 5. Extract the AI's exact math and decisions
        financials = simulation_data.get("financial_analysis", {})
        if not isinstance(financials, dict):
            financials = {}

        raw_agents = simulation_data.get("agents", [])
        if not isinstance(raw_agents, list):
            raw_agents = []

        agents: List[Dict[str, Any]] = []
        for i, raw_agent in enumerate(raw_agents, start=1):
            if not isinstance(raw_agent, dict):
                continue

            decision = str(raw_agent.get("decision", "pass")).strip().lower()
            if decision not in {"buy", "pass"}:
                decision = "pass"

            agents.append(
                {
                    "id": i,
                    "role": str(raw_agent.get("role", "Unknown")).strip() or "Unknown",
                    "trait": str(raw_agent.get("trait", "Undecided")).strip() or "Undecided",
                    "decision": decision,
                    "reason": str(raw_agent.get("reason", "No reason provided.")).strip() or "No reason provided.",
                }
            )

        if len(agents) > agent_count:
            agents = agents[:agent_count]
        while len(agents) < agent_count:
            idx = len(agents) + 1
            agents.append(
                {
                    "id": idx,
                    "role": "Unknown",
                    "trait": "Neutral",
                    "decision": "pass",
                    "reason": "Padded to satisfy required agent count.",
                }
            )

        baseline_profit = _to_float(financials.get("baseline_estimated_profit"), 0.0)
        projected_profit = _to_float(financials.get("projected_new_profit"), baseline_profit)
        profit_boost = _to_float(financials.get("profit_boost"), projected_profit - baseline_profit)

        verdict = str(financials.get("final_verdict", "")).strip().upper()
        if verdict not in {"PROCEED", "ABORT", "AVOID"}:
            verdict = "PROCEED" if profit_boost > 0 else "AVOID"
        # Hard override: never PROCEED if profit is negative
        if profit_boost < 0 and verdict == "PROCEED":
            verdict = "AVOID"
            print(f"[Verdict Override] Forced AVOID because profit_boost={profit_boost:.2f}")

        verdict_reason = str(financials.get("verdict_reason", "")).strip()
        if not verdict_reason:
            verdict_reason = (
                "Projected profit exceeds baseline profit."
                if verdict == "PROCEED"
                else "Projected profit does not exceed baseline profit."
            )

        # UI Stats (for the scoreboard)
        total_buy = sum(1 for agent in agents if agent.get("decision") == "buy")
        total_pass = len(agents) - total_buy

        return {
            "status": "success",
            "boss_idea": payload.boss_idea,
            "verdict": verdict,
            "financials": {
                "baseline_profit": round(baseline_profit, 2),
                "projected_profit": round(projected_profit, 2),
                "profit_boost": round(profit_boost, 2),
                "reasoning": verdict_reason,
            },
            "stats": {
                "total_agents": len(agents),
                "total_buy": total_buy,
                "total_pass": total_pass
            },
            "swarm_data": agents
        }

    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Simulation failed: {exc}") from exc
    
@app.post("/roadmap/generate")
def generate_roadmap(payload: GenerateRoadmapRequest) -> Dict[str, Any]:
    try:
        supabase = get_supabase_client()
        llm_client = get_zhipu_client()
        target_month: Optional[str] = None
        if isinstance(payload.target_month, str) and payload.target_month.strip():
            target_month = _normalize_report_month(payload.target_month)
        elif payload.source in {"BOARDROOM", "SANDBOX"}:
            raise HTTPException(status_code=400, detail="target_month is required for BOARDROOM/SANDBOX roadmap generation")

        financial_trend = payload.financial_trend if isinstance(payload.financial_trend, dict) else {}
        if not financial_trend and target_month:
            financial_trend = _fetch_financial_trend(supabase, payload.merchant_id, target_month)
        elif not financial_trend:
            financial_trend = {
                "mode": "simulation_only",
                "note": "No target_month provided; using simulation insights supplied by caller.",
            }

        diagnostic_patterns = payload.diagnostic_patterns if isinstance(payload.diagnostic_patterns, dict) else {}
        if not diagnostic_patterns and target_month:
            diagnostic_patterns = _fetch_diagnostic_patterns(supabase, payload.merchant_id, target_month)
        elif not diagnostic_patterns:
            diagnostic_patterns = {
                "mode": "simulation_only",
                "note": "No month-based diagnostics available; roadmap grounded on strategy, justification, and provided insights.",
            }

        combined_financial_context = {
            "financial_trend": financial_trend,
            "diagnostic_patterns": diagnostic_patterns,
        }

        roadmap_sys = (
            "You are an elite Project Manager for an F&B business. Your job is to take a business strategy "
            "and break it down into a highly actionable, context-aware execution roadmap.\n\n"
            "STRICT INSTRUCTIONS:\n"
            "1. DYNAMIC PHASES: The number of phases and tasks MUST adapt to the complexity of the strategy.\n"
            "2. CONTEXT-DRIVEN TASKS: You MUST weave the provided external signals (weather, competitors) and internal diagnostics directly into the tasks. Do NOT write generic tasks like 'Launch promo'. Instead write: 'Launch GrabFood promo at 12 PM to capture the predicted 85% foot traffic spike during the rainy weather.'\n"
            "3. JUSTIFICATION ALIGNMENT: Ensure the tasks specifically address the 'Why' (Justification) provided by the CEO/Financial Auditor.\n"
            "4. OUTPUT FORMAT: Return ONLY a pure JSON object. NO markdown fences, NO extra text.\n\n"
            "JSON SCHEMA REQUIREMENT:\n"
            "{\n"
            "  \"estimated_total_days\": 14,\n"
            "  \"phases\": [\n"
            "    {\n"
            "      \"phase_number\": 1,\n"
            "      \"title\": \"Preparation & Risk Mitigation\",\n"
            "      \"tasks\": [\"Detailed, context-aware task 1\", \"Detailed, context-aware task 2\"]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        roadmap_usr = (
            f"--- THE STRATEGY ---\n"
            f"Source: {payload.source}\n"
            f"Plan to Execute: {payload.strategy_text}\n"
            f"Justification / Reasoning: {payload.justification}\n\n"
            
            f"--- THE ENVIRONMENT (Use this to make tasks hyper-specific) ---\n"
            f"Combined Financial Context JSON: {json.dumps(combined_financial_context)}\n"
            f"External Signals (Weather, Traffic, Competitors): {json.dumps(payload.external_signals)}\n\n"
            
            "Generate the JSON execution roadmap."
        )

        # Temperature 0.4 gives it enough creativity to apply the weather/traffic to the tasks logically
        raw_json_response = _call_text_llm(llm_client, roadmap_sys, roadmap_usr, temperature=0.4)

        roadmap_data = _parse_model_json(
            raw_json_response,
            source_name="Roadmap model",
            required_kind="object",
        )
        roadmap_data = _normalize_roadmap_payload(roadmap_data)

        # Save to Database (Optional: Save it so the Boss can view it later)
        if payload.source == "BOARDROOM" and target_month:
            supabase.table("monthly_summaries").update({
                "action_plan": json.dumps(roadmap_data) # Save the structured JSON
            }).eq("merchant_id", payload.merchant_id).eq("report_month", target_month).execute()

        return {
            "status": "success",
            "roadmap": roadmap_data
        }

    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Roadmap generation failed: {exc}") from exc

class SingleUploadRequest(BaseModel):
    merchant_id: str
    report_month: str
    file_data_url: str

class AnalyzeMonthRequest(BaseModel):
    merchant_id: str
    report_month: str

# ---------------------------------------------------------
# 1. THE STATUS CHECKER
# ---------------------------------------------------------
@app.get("/merchants/{merchant_id}/sync-status/{report_month}")
def get_sync_status(merchant_id: str, report_month: str) -> Dict[str, Any]:
    supabase = get_supabase_client()
    
    # 1. Fetch actual shop_id
    shop_res = supabase.table("merchants").select("shop_id").eq("owner_id", merchant_id).limit(1).execute()
    actual_shop_id = shop_res.data[0]["shop_id"] if shop_res.data else None

    # Check Sales using actual_shop_id
    start_iso, end_iso = _month_window(report_month)
    has_sales = False
    if actual_shop_id:
        sales_res = supabase.table("sales_logs").select("id").eq("merchant_id", actual_shop_id).gte("logged_at", start_iso).lt("logged_at", end_iso).limit(1).execute()
        has_sales = len(sales_res.data) > 0

    # 🚀 THE FIX: Check Summary using actual_shop_id instead of owner_id!
    has_summary = False
    if actual_shop_id:
        summary_res = supabase.table("monthly_summaries").select("id").eq("merchant_id", actual_shop_id).eq("report_month", report_month).limit(1).execute()
        has_summary = len(summary_res.data) > 0

    return {
        "status": "success",
        "month": report_month,
        "sync_state": {
            "sales": {"isSynced": has_sales, "isUploading": False},
            "procurement": {"isSynced": has_summary, "isUploading": False},
            "invoices": {"isSynced": has_summary, "isUploading": False}
        },
        "all_synced": has_sales and has_summary
    }

# ---------------------------------------------------------
# 2. THE INGESTORS (Separate Uploads)
# ---------------------------------------------------------
@app.post("/upload/sales")
def upload_sales_csv(payload: SingleUploadRequest):
    supabase = get_supabase_client()
    csv_mime, csv_bytes = _decode_data_url(payload.file_data_url)
    
    sales_df = _parse_sales_logs_csv(csv_bytes)
    
    # --- 🛠️ FIX: Fetch actual shop_id to satisfy foreign key ---
    shop_res = supabase.table("merchants").select("shop_id").eq("owner_id", payload.merchant_id.strip()).limit(1).execute()
    if not shop_res.data:
        raise HTTPException(status_code=404, detail="Merchant shop not found.")
    actual_shop_id = str(shop_res.data[0]["shop_id"])
    
    # Save directly to the database using actual_shop_id
    inserted_sales_logs, total_revenue, category_revenue = _ingest_sales_logs(
        supabase=supabase,
        merchant_id=actual_shop_id, # <--- 🚀 Replaced payload.merchant_id
        report_month=payload.report_month,
        sales_df=sales_df,
        batch_size=1000,
    )
    
    return {"status": "success", "message": f"Saved {inserted_sales_logs} rows.", "revenue": total_revenue}

@app.post("/upload/statement")
def upload_statement_pdf(payload: SingleUploadRequest):
    supabase = get_supabase_client()
    owner_id = payload.merchant_id.strip()

    # 1. Fetch actual shop_id
    shop_res = supabase.table("merchants").select("shop_id").eq("owner_id", owner_id).limit(1).execute()
    if not shop_res.data:
        raise HTTPException(status_code=404, detail="Merchant shop not found.")
    actual_shop_id = str(shop_res.data[0]["shop_id"])

    # 2. Decode and prep the file for the AI
    mime, raw_bytes = _decode_data_url(payload.file_data_url)
    pages = _render_pdf_pages_as_data_urls(raw_bytes) if mime == "application/pdf" else [payload.file_data_url]

    # 3. Run the REAL Vision LLM Extraction
    client = get_zhipu_client()
    operating_expenses = []
    total_revenue = 0.0 

    for page in pages:
        parsed = _vision_json(client, page, MASTER_EXTRACT_PROMPT)
        parsed_obj = _coerce_master_payload(parsed)
        
        # 🚀 Now we safely grab it from the cleaned object!
        page_revenue = parsed_obj.get("total_revenue", 0.0)
        if page_revenue > total_revenue:
            total_revenue = page_revenue

        operating_expenses.extend(_normalize_pl_rows(parsed_obj.get("operating_expenses", [])))

    total_fixed_costs = round(sum(row["amount"] for row in operating_expenses), 2)

    # 5. Save the summary total and the individual line items to the database
    summary_payload = {
        "merchant_id": actual_shop_id,
        "report_month": payload.report_month,
        "total_revenue": round(total_revenue, 2),
        "total_fixed_costs": total_fixed_costs
    }
    summary_id = _upsert_monthly_summary(supabase, summary_payload)
    _replace_operating_expenses(supabase, summary_id, operating_expenses)

    return {
        "status": "success",
        "message": f"Processed {len(operating_expenses)} expenses via AI.",
        "total_extracted": total_fixed_costs
    }

@app.post("/upload/invoices")
def upload_invoices_pdf(payload: SingleUploadRequest):
    supabase = get_supabase_client()
    owner_id = payload.merchant_id.strip()

    # 1. Fetch actual shop_id
    shop_res = supabase.table("merchants").select("shop_id").eq("owner_id", owner_id).limit(1).execute()
    if not shop_res.data:
        raise HTTPException(status_code=404, detail="Merchant shop not found.")
    actual_shop_id = str(shop_res.data[0]["shop_id"])

    # 2. Decode and prep the file for the AI
    mime, raw_bytes = _decode_data_url(payload.file_data_url)
    pages = _render_pdf_pages_as_data_urls(raw_bytes) if mime == "application/pdf" else [payload.file_data_url]

    # 3. Run the REAL Vision LLM Extraction
    client = get_zhipu_client()
    supplier_invoices = []

    for page in pages:
        parsed = _vision_json(client, page, MASTER_EXTRACT_PROMPT)
        parsed_obj = _coerce_master_payload(parsed)
        supplier_invoices.extend(_normalize_invoice_rows(parsed_obj.get("supplier_invoices", [])))

    # 4. Calculate the true total variable/ingredient costs
    total_ingredient_costs = round(sum(row["total_amount"] for row in supplier_invoices), 2)

    # 5. Save the summary total and individual line items
    summary_payload = {
        "merchant_id": actual_shop_id,
        "report_month": payload.report_month,
        "total_ingredient_costs": total_ingredient_costs
    }
    summary_id = _upsert_monthly_summary(supabase, summary_payload)
    _replace_supplier_invoices(supabase, summary_id, supplier_invoices)

    return {
        "status": "success",
        "message": f"Processed {len(supplier_invoices)} invoices via AI.",
        "total_extracted": total_ingredient_costs
    }

# ---------------------------------------------------------
# 3. THE CRUNCHER (Pattern Recognition)
# ---------------------------------------------------------
@app.post("/analyze/monthly-patterns")
def analyze_monthly_patterns(payload: AnalyzeMonthRequest):
    supabase = get_supabase_client()
    owner_id = payload.merchant_id.strip() 
    report_month = payload.report_month
    
    # --- 🛠️ Fetch actual shop_id ---
    shop_res = supabase.table("merchants").select("shop_id").eq("owner_id", owner_id).limit(1).execute()
    if not shop_res.data:
        raise HTTPException(status_code=404, detail="Merchant shop not found.")
    actual_shop_id = str(shop_res.data[0]["shop_id"])

    # 1. Grab the total revenue from the CSV data
    start_iso, end_iso = _month_window(report_month)
    sales_res = supabase.table("sales_logs").select("price, quantity").eq("merchant_id", actual_shop_id).gte("logged_at", start_iso).lt("logged_at", end_iso).execute()
    
    total_revenue = sum([row["price"] * row["quantity"] for row in sales_res.data]) if sales_res.data else 0.0
    
    # 2. 🚀 THE REAL FIX: Fetch the actual costs AND revenue uploaded by the Vision LLM 🚀
    summary_res = supabase.table("monthly_summaries").select("total_revenue, total_fixed_costs, total_ingredient_costs").eq("merchant_id", actual_shop_id).eq("report_month", report_month).limit(1).execute()
    
    total_fixed_costs = 0.0
    total_ingredient_costs = 0.0
    
    if summary_res.data:
        existing_summary = summary_res.data[0]
        # 👈 NEW: Check if the AI already extracted a P&L revenue. If yes, override the CSV revenue!
        if existing_summary.get("total_revenue") and existing_summary.get("total_revenue") > 0:
            total_revenue = existing_summary.get("total_revenue")
            
        # Use .get() with a fallback to 0.0 in case the AI couldn't find any expenses
        total_fixed_costs = existing_summary.get("total_fixed_costs") or 0.0
        total_ingredient_costs = existing_summary.get("total_ingredient_costs") or 0.0

    # 3. Calculate REAL net profit
    net_profit = total_revenue - total_fixed_costs - total_ingredient_costs

    # 4. Save the final summary USING actual_shop_id
    summary_payload = {
        "merchant_id": actual_shop_id, 
        "report_month": report_month,
        "total_revenue": round(total_revenue, 2),
        "total_fixed_costs": round(total_fixed_costs, 2),
        "total_ingredient_costs": round(total_ingredient_costs, 2),
        "net_profit": round(net_profit, 2),
    }
    
    _upsert_monthly_summary(supabase, summary_payload)
    
    # 5. Trigger the Pattern Recognition Math
    _fetch_diagnostic_patterns(supabase, actual_shop_id, report_month)

    return {"status": "success", "message": "Analysis complete!"}
# ---------------------------------------------------------
# 3. SWARM SIMULATION ENGINE (MICROFISH)
# ---------------------------------------------------------
class SwarmSimulationRequest(BaseModel):
    merchant_id: str = Field(min_length=1)
    target_month: str = Field(min_length=7)
    scenario_prompt: str = Field(min_length=1)


def _build_local_swarm_fallback(
    scenario_prompt: str,
    slim_fin: Dict[str, Any],
    sigs: Dict[str, Any],
    merchant_data: Dict[str, Any],
) -> Dict[str, Any]:
    scenario_text = str(scenario_prompt or "").strip()
    scenario_lower = scenario_text.lower()

    base_profit = round(_to_float(slim_fin.get("profit"), 0.0), 2)
    avg_rev = _to_float(slim_fin.get("avg_rev"), 0.0)
    scale_base = avg_rev if avg_rev > 0 else max(abs(base_profit), 500.0)

    foot_intensity = max(0.0, min(100.0, _to_float(sigs.get("foot_traffic"), 50.0)))
    competitors = max(0.0, _to_float(sigs.get("competitors"), 0.0))
    weather = str(sigs.get("weather", "N/A"))
    traffic = str(sigs.get("traffic", "N/A"))

    signal_score = (foot_intensity - 50.0) / 20.0
    signal_score -= min(competitors, 20.0) / 10.0
    if "heavy" in traffic.lower():
        signal_score -= 1.0
    if "rain" in weather.lower():
        signal_score -= 0.5
    elif "clear" in weather.lower() or "sun" in weather.lower():
        signal_score += 0.3

    positive_keywords = [
        "bundle",
        "promo",
        "promotion",
        "delivery",
        "upsell",
        "loyalty",
        "combo",
        "campaign",
        "grabfood",
        "foodpanda",
        "new menu",
    ]
    negative_keywords = [
        "raise price",
        "price hike",
        "cut staff",
        "shorten hours",
        "close early",
        "remove menu",
        "stop promo",
        "higher cost",
    ]

    keyword_score = sum(1 for kw in positive_keywords if kw in scenario_lower)
    keyword_score -= sum(1 for kw in negative_keywords if kw in scenario_lower)

    estimated_delta = (0.03 * scale_base * keyword_score) + (0.02 * scale_base * signal_score)
    projected_profit = round(base_profit + estimated_delta, 2)
    profit_boost = round(projected_profit - base_profit, 2)
    final_verdict = "PROCEED" if profit_boost >= 0 else "AVOID"

    can_handle_traffic = foot_intensity <= 85 and "heavy" not in traffic.lower()
    if foot_intensity > 85 or "heavy" in traffic.lower():
        bottleneck_risk = "High"
    elif foot_intensity > 70:
        bottleneck_risk = "Moderate"
    else:
        bottleneck_risk = "Low"

    target_audience = merchant_data.get("target_audience", {})
    segment_rows: List[Tuple[str, float]] = []
    if isinstance(target_audience, dict):
        for key, value in target_audience.items():
            pct = _to_float(value, 0.0)
            if pct > 0:
                segment_rows.append((str(key).strip() or "General", pct))

    if not segment_rows:
        segment_rows = [("Students", 30.0), ("Office Workers", 30.0), ("Families", 20.0), ("Tourists", 20.0)]

    segment_rows.sort(key=lambda item: item[1], reverse=True)
    segment_rows = segment_rows[:4]

    swarm_behavior: List[Dict[str, Any]] = []
    for segment, pct in segment_rows:
        if final_verdict == "PROCEED":
            reaction = f"{segment} show positive intent for this scenario if execution quality stays high."
            churn_risk = "Low" if pct >= 25 else "Medium"
        else:
            reaction = f"{segment} are likely to delay purchases unless the offer is tightened and priced better."
            churn_risk = "High" if pct >= 25 else "Medium"

        if foot_intensity < 40 and churn_risk == "Low":
            churn_risk = "Medium"
        if "heavy" in traffic.lower() and churn_risk == "Medium":
            churn_risk = "High"

        swarm_behavior.append(
            {
                "segment": segment,
                "reaction": reaction,
                "churn_risk": churn_risk,
            }
        )

    simulation_summary = (
        f"Fallback simulation used because the live model did not return usable text. "
        f"Signals show foot traffic at {int(round(foot_intensity))}/100 with {int(round(competitors))} nearby competitors and traffic '{traffic}'."
    )

    return {
        "simulation_summary": simulation_summary,
        "financial_analysis": {
            "baseline_estimated_profit": base_profit,
            "projected_new_profit": projected_profit,
            "profit_boost": profit_boost,
            "final_verdict": final_verdict,
        },
        "operational_impact": {
            "can_handle_traffic": can_handle_traffic,
            "bottleneck_risk": bottleneck_risk,
            "operational_notes": "Monitor prep-time and queue length during peak windows; adjust staffing if demand spikes.",
        },
        "swarm_behavior": swarm_behavior,
        "signal_references": [
            f"weather={weather}",
            f"traffic={traffic}",
            f"foot_traffic={int(round(foot_intensity))}",
            f"competitors={int(round(competitors))}",
            f"scenario={scenario_text[:120]}",
        ],
    }

@app.post("/swarm/simulate")
def run_swarm_simulation(payload: SwarmSimulationRequest):
    try:
        supabase = get_supabase_client()
        
        # 1. Resolve ID and fetch Merchant Foundation
        actual_merchant_id = _resolve_merchant_id(supabase, payload.merchant_id.strip())
        merch_res = supabase.table("merchants").select("*").eq("shop_id", actual_merchant_id).limit(1).execute()
        
        if not merch_res.data:
            raise HTTPException(status_code=404, detail="Merchant details missing.")
        merchant_data = merch_res.data[0]
        merchant_profile_str = merchant_data.get("merchant_profile", "")

        # 2. Fetch the Hard Financial Data
        financial_context = _build_financial_context_payload(supabase, actual_merchant_id, payload.target_month)

        # 3. 🚨 REINSTATED: The Hackathon Safeguard 🚨
        try:
            external_signals = _fetch_external_signals(supabase, actual_merchant_id, merchant_profile_str, payload.target_month)
        except Exception as api_error:
            print(f"Warning: Real APIs failed during simulation - {api_error}")
            # CRITICAL HACKATHON SAFEGUARD: Prevents Swarm from crashing if rate-limited!
            external_signals = {
                "warning": "Real-time signals temporarily unavailable. Proceeding with baseline merchant data.",
                "foot_traffic": {"data": {"live_intensity": 50}} # Safe default
            }

        import random

        weather_raw = external_signals.get("weather", {}).get("data", {})
        traffic_raw = external_signals.get("traffic", {}).get("data", {})
        foot_raw = external_signals.get("foot_traffic", {}).get("data", {})
        places_raw = (external_signals.get("places") or {}).get("data", {})

        # ---------------------------------------------------------
        # 5. BUILD MICRO-COHORTS (The Persona Matrix)
        # ---------------------------------------------------------
        PERSONA_MATRIX = {
            "Students": [
                {"type": "Broke Student", "trait": "Very price sensitive"},
                {"type": "Rich Student", "trait": "Wants premium aesthetic"},
                {"type": "Stressed Student", "trait": "Needs fast + caffeine"},
                {"type": "Gym Student", "trait": "Cares about protein"},
            ],
            "Office Workers": [
                {"type": "Rushed Worker", "trait": "Needs under 5 min"},
                {"type": "Executive", "trait": "High spending power"},
                {"type": "Intern", "trait": "Low budget"},
                {"type": "Health Exec", "trait": "Avoids unhealthy food"},
            ],
            "Families": [
                {"type": "Exhausted Parent", "trait": "Just wants kids to eat"},
                {"type": "Big Gathering", "trait": "Looking for sharing platters"}
            ],
            "General": [
                {"type": "Impulse Buyer", "trait": "Easily persuaded"},
                {"type": "Skeptic", "trait": "Hard to convince"},
                {"type": "Loyal Regular", "trait": "Likely to support"},
            ]
        }

        audience_dist = merchant_data.get("target_audience", {})
        if not audience_dist:
            audience_dist = {"Students": 40, "Office Workers": 40, "General": 20}

        live_intensity = foot_raw.get("live_intensity", 50) if isinstance(foot_raw, dict) else 50
        target_agent_count = max(5, min(100, int(live_intensity)))

        micro_cohorts = []
        for segment, pct in audience_dist.items():
            pct_val = float(pct) / 100.0
            segment_total = max(1, int(round(target_agent_count * pct_val)))

            personas = PERSONA_MATRIX.get(segment, PERSONA_MATRIX["General"])
            per_persona = max(1, segment_total // len(personas))

            for p in personas:
                micro_cohorts.append({
                    "cohort": p["type"],
                    "segment": segment,
                    "headcount": per_persona,
                    "trait": p["trait"]
                })

        # Limit to avoid LLM overload (max 10 micro-cohorts)
        micro_cohorts = micro_cohorts[:10]

        # ---------------------------------------------------------
        # 6. LEAN MICROFISH PROMPT (Updated with your instructions)
        # ---------------------------------------------------------
        system_prompt = (
            "You are MicroFish, an F&B swarm-intelligence simulator. "
            "Analyze the scenario using the merchant data, live signals, and the provided micro-cohorts.\n\n"
            "Task: Evaluate how the scenario affects the financials, operations, and EACH specific micro-cohort. "
            "Return ONLY valid JSON (no markdown) with these exact keys:\n"
            "- simulation_summary: 2 sentences referencing the signal data\n"
            "- financial_analysis: {baseline_estimated_profit, projected_new_profit, profit_boost, final_verdict: PROCEED/AVOID}\n"
            "- operational_impact: {can_handle_traffic: bool, bottleneck_risk: Low/Moderate/High, operational_notes}\n"
            "- swarm_behavior: array evaluating EACH cohort [{cohort: string, decision: buy/pass, reaction: short reasoning}]\n\n"
            "CRITICAL INSTRUCTION:\n"
            "1. You must mathematically evaluate the final projected profit.\n"
            "2. If projected profit is less than 0, output 'final_verdict': 'AVOID'.\n"
            "3. Under NO circumstances should you approve a strategy that results in negative profit."
        )

        fin_trend = financial_context.get("financial_trend", {})
        slim_fin = {
            "rev": (fin_trend.get("target_month") or {}).get("total_revenue", 0),
            "profit": (fin_trend.get("target_month") or {}).get("net_profit", 0),
            "avg_rev": (fin_trend.get("rolling_averages") or {}).get("avg_revenue", 0),
        }

        sigs = {
            "weather": f"{weather_raw.get('condition', 'N/A')}, {weather_raw.get('temp_c', weather_raw.get('temp', 'N/A'))}°C" if isinstance(weather_raw, dict) else "N/A",
            "traffic": traffic_raw.get("congestion_level", "N/A") if isinstance(traffic_raw, dict) else "N/A",
            "foot_traffic": live_intensity,
            "competitors": places_raw.get("nearby_food_venue_count", 0) if isinstance(places_raw, dict) else 0,
        }

        user_prompt = (
            f"Scenario: \"{payload.scenario_prompt}\"\n"
            f"Shop: {merchant_data.get('type')} | Hours: {merchant_data.get('operating_hours')}\n"
            f"Financials: {json.dumps(slim_fin)}\n"
            f"Signals: {json.dumps(sigs)}\n\n"
            f"You will receive a list of micro-cohorts representing groups of people.\n"
            f"Each cohort includes: cohort name, headcount, and behavioral trait.\n"
            f"Micro-Cohorts to Evaluate:\n{json.dumps(micro_cohorts)}\n\n"
            f"JSON only."
        )

        # ---------------------------------------------------------
        # 7. CALL LLM 
        # ---------------------------------------------------------
        engine = "ilmu"
        fallback_reason = ""
        try:
            raw_json_response = _call_text_llm(None, system_prompt, user_prompt, temperature=0.4)
            simulation_data = _parse_model_json(raw_json_response, source_name="Simulation model", required_kind="object")
        except HTTPException as llm_exc:
            engine = "local_fallback"
            fallback_reason = str(llm_exc.detail)
            print(f"[Swarm Fallback] {fallback_reason}")
            simulation_data = _build_local_swarm_fallback(payload.scenario_prompt, slim_fin, sigs, merchant_data)

        # Sanity-check the verdict
        financials = simulation_data.get("financial_analysis", {})
        if isinstance(financials, dict):
            profit_boost = _to_float(financials.get("profit_boost"), 0.0)
            llm_verdict = str(financials.get("final_verdict", "")).strip().upper()
            if profit_boost < 0 and llm_verdict == "PROCEED":
                financials["final_verdict"] = "AVOID"
            simulation_data["financial_analysis"] = financials

        # ---------------------------------------------------------
        # 8. UNPACK COHORTS INTO REALISTIC INDIVIDUAL AGENTS
        # ---------------------------------------------------------
        swarm_behavior = simulation_data.get("swarm_behavior", [])
        if not isinstance(swarm_behavior, list):
            swarm_behavior = []

        # Map LLM results by cohort name for easy lookup
        cohort_results = {
            str(c.get("cohort", "")): c for c in swarm_behavior if isinstance(c, dict)
        }

        synthetic_agents = []
        agent_id = 1

        for cohort in micro_cohorts:
            cohort_name = cohort["cohort"]
            segment = cohort["segment"]
            count = cohort["headcount"]

            llm_eval = cohort_results.get(cohort_name, {})
            
            base_decision = str(llm_eval.get("decision", "buy")).strip().lower()
            if base_decision not in ["buy", "pass"]:
                base_decision = "pass"
                
            base_reason = llm_eval.get("reaction", f"Reacting based on {cohort['trait']}")

            for i in range(count):
                decision = base_decision

                # MICRO VARIATION: Even within a cohort, people are unpredictable
                if decision == "buy" and i % 7 == 0:
                    decision = "pass"
                elif decision == "pass" and i % 5 == 0:
                    decision = "buy"

                synthetic_agents.append({
                    "id": agent_id,
                    "segment": segment,      # e.g., "Students"
                    "role": cohort_name,     # e.g., "Broke Student"
                    "trait": cohort["trait"],# e.g., "Very price sensitive"
                    "decision": decision,
                    "reason": base_reason
                })
                agent_id += 1

        # Shuffle so the Live Agent Feed UI looks like a natural stream of people
        random.shuffle(synthetic_agents)

        total_buy = sum(1 for a in synthetic_agents if a["decision"] == "buy")
        total_pass = len(synthetic_agents) - total_buy

        response_payload = {
            "status": "success",
            "engine": engine,
            "scenario": payload.scenario_prompt,
            "summary": simulation_data.get("simulation_summary", ""),
            "financials": simulation_data.get("financial_analysis", {}),
            "operations": simulation_data.get("operational_impact", {}),
            "swarm_behavior": swarm_behavior,
            "signal_references": simulation_data.get("signal_references", []),
            "stats": {
                "total_agents": len(synthetic_agents),
                "total_buy": total_buy,
                "total_pass": total_pass
            },
            "swarm_data": synthetic_agents
        }

        if fallback_reason:
            response_payload["fallback_reason"] = fallback_reason

        return response_payload

    except HTTPException:
        raise
    except Exception as e:
        print(f"Swarm Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("vision_service:app", host="0.0.0.0", port=8001, reload=True)
