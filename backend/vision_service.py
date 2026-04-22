import base64
import csv
import io
import json
import os
import re
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


load_dotenv(find_dotenv())


MASTER_EXTRACT_PROMPT = (
    "You are an F&B Financial Auditor for a Malaysian Cafe. Analyze this document and extract all financial data into a strict JSON format. "
    "1. If you see fixed costs (e.g., Rent, Payroll, TNB, Syabas, KWSP, Utilities), put them in 'operating_expenses'. "
    "2. If you see ingredient purchases (e.g., Chicken, Beans, Milk, Ice), put them in 'supplier_invoices'. "
    "\\n\\nRETURN ONLY JSON IN THIS EXACT FORMAT: "
    "{"
    "  \"document_type\": \"pl_statement\" | \"supplier_invoice\" | \"mixed\","
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

class SetupProfileRequest(BaseModel):
    merchant_id: str  # We need this to know which shop to update
    target_audience: str
    operating_hours: str

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

class GenerateRoadmapRequest(BaseModel):
    merchant_id: str = Field(min_length=1)
    target_month: str = Field(min_length=7)
    source: str = Field(min_length=1, pattern=r"^(BOARDROOM|SANDBOX)$")
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
    if isinstance(raw_content, str):
        return raw_content.strip()

    if isinstance(raw_content, list):
        parts: List[str] = []
        for part in raw_content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text_value = part.get("text") or part.get("content")
                if isinstance(text_value, str):
                    parts.append(text_value)
        return "\n".join(parts).strip()

    return str(raw_content).strip()


def _strip_markdown_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    return cleaned


def _parse_model_json(raw_text: str, source_name: str, required_kind: Optional[str] = None) -> Any:
    cleaned = _strip_markdown_fences(raw_text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"{source_name} returned invalid JSON: {exc}") from exc

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
    mode = client.get("mode")
    sdk_client = client.get("client")

    if mode == "modern":
        response = sdk_client.chat.completions.create(
            model="glm-4.6v-flash",
            temperature=0,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Read this document and return JSON only."},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
        )

        if not getattr(response, "choices", None):
            raise HTTPException(status_code=502, detail="Vision model returned no choices")

        raw_text = _extract_model_text(response.choices[0].message.content)
    elif mode == "legacy":
        legacy_response = sdk_client.model_api.invoke(
            model="glm-4.6v-flash",
            prompt=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Read this document and return JSON only."},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
        )

        data = legacy_response.get("data") if isinstance(legacy_response, dict) else None
        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices:
            raise HTTPException(status_code=502, detail=f"Legacy vision response invalid: {legacy_response}")

        first_choice = choices[0] if isinstance(choices[0], dict) else {}
        raw_text = _extract_model_text(first_choice.get("content", ""))
    else:
        raise HTTPException(status_code=500, detail="Unsupported zhipu client mode")

    return _parse_model_json(raw_text, source_name="Vision model")


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
    # Expected shape:
    # {
    #   "document_type": "pl_statement|supplier_invoice|mixed",
    #   "operating_expenses": [...],
    #   "supplier_invoices": [...]
    # }
    if isinstance(parsed, dict):
        # Handle alternative wrappers that models often emit.
        if "operating_expenses" in parsed or "supplier_invoices" in parsed:
            return {
                "document_type": str(parsed.get("document_type", "unknown")).strip().lower(),
                "operating_expenses": parsed.get("operating_expenses") or parsed.get("expenses") or [],
                "supplier_invoices": parsed.get("supplier_invoices") or parsed.get("invoices") or parsed.get("items") or [],
            }

        # If dict is a single row-like structure, wrap it into one of the arrays.
        if "expense_type" in parsed and "amount" in parsed:
            return {
                "document_type": "pl_statement",
                "operating_expenses": [parsed],
                "supplier_invoices": [],
            }
        if "item_name" in parsed and "total_amount" in parsed:
            return {
                "document_type": "supplier_invoice",
                "operating_expenses": [],
                "supplier_invoices": [parsed],
            }

        return {
            "document_type": str(parsed.get("document_type", "unknown")).strip().lower(),
            "operating_expenses": [],
            "supplier_invoices": [],
        }

    if isinstance(parsed, list):
        operating_expenses: List[Dict[str, Any]] = []
        supplier_invoices: List[Dict[str, Any]] = []

        for row in parsed:
            if not isinstance(row, dict):
                continue
            if "expense_type" in row and "amount" in row:
                operating_expenses.append(row)
            elif "item_name" in row and "total_amount" in row:
                supplier_invoices.append(row)

        if operating_expenses and supplier_invoices:
            doc_type = "mixed"
        elif operating_expenses:
            doc_type = "pl_statement"
        elif supplier_invoices:
            doc_type = "supplier_invoice"
        else:
            doc_type = "unknown"

        return {
            "document_type": doc_type,
            "operating_expenses": operating_expenses,
            "supplier_invoices": supplier_invoices,
        }

    return {
        "document_type": "unknown",
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
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
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


def _call_text_llm(client: Any, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    mode = client.get("mode")
    sdk_client = client.get("client")

    if mode == "modern":
        response = sdk_client.chat.completions.create(
            model="glm-4.7-flash",
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        if not getattr(response, "choices", None):
            raise HTTPException(status_code=502, detail="Text model returned no choices")

        return _extract_model_text(response.choices[0].message.content)

    if mode == "legacy":
        response = sdk_client.model_api.invoke(
            model="glm-4.7-flash",
            temperature=temperature,
            prompt=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        data = response.get("data") if isinstance(response, dict) else None
        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices:
            raise HTTPException(status_code=502, detail=f"Legacy text response invalid: {response}")

        first_choice = choices[0] if isinstance(choices[0], dict) else {}
        return _extract_model_text(first_choice.get("content", ""))

    raise HTTPException(status_code=500, detail="Unsupported zhipu client mode")


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

    if not baseline_res.data:
        raise HTTPException(status_code=404, detail=f"No baseline month data found for {baseline_month}")
    if not target_res.data:
        raise HTTPException(status_code=404, detail=f"No target month data found for {target_month}")

    baseline = baseline_res.data[0]
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
    if not rows:
        raise HTTPException(status_code=404, detail="No monthly summary history found for this merchant")

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

    if target_row is None:
        raise HTTPException(status_code=404, detail=f"No target month data found for {target_month}")

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
    return {
        "financial_trend": _fetch_financial_trend(supabase, merchant_id, target_month),
        "diagnostic_patterns": _fetch_diagnostic_patterns(supabase, merchant_id, target_month),
    }


def _fetch_traffic_signal(lat: float, lon: float) -> Dict[str, Any]:
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
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
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
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
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={api_key}"
    try:
        response = requests.get(url).json()
        if response.get("status") == "OK":
            return response["results"][0]["formatted_address"]
        return "Unknown Location"
    except Exception as e:
        return f"Error: {e}"
    
def get_details_from_place_id(place_id: str):
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
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
    places_api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not places_api_key:
        return {
            "attempted": True,
            "status": "error",
            "error": "Missing GOOGLE_PLACES_API_KEY",
            "data": {},
        }

    query = f"cafe OR restaurant near {_extract_location_hint(merchant_profile)}"
    try:
        url = "https://gnews.io/api/v4/search"
        params = {
            "query": query,
            "from": start_date,
            "to": end_date,
            "lang": "en",
            "country": "my",
            "max": 5, # Grabs the top 5 articles across both categories
            "sortby": "relevance", # Changed from publishedAt to relevance to get the most impactful news
            "apikey": gnews_api_key,
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
async def setup_profile(req: SetupProfileRequest):
    supabase = get_supabase_client()
    try:
        # We only update the specific fields they filled out in the onboarding UI
        update_data = {
            "target_audience": req.target_audience,
            "operating_hours": req.operating_hours
        }
        
        # We use .update() because the row was already created during /auth/signup
        response = supabase.table("merchants").update(update_data).eq("owner_id", req.merchant_id).execute()
        
        return {
            "status": "success", 
            "message": "Shop profile setup complete!", 
            "data": response.data
        }
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
    proposed_strategies: str = Field(min_length=1)
    merchant_profile: str = Field(default="")
    external_signals: Dict[str, Any] = Field(default_factory=dict)
    financial_trend: Dict[str, Any] = Field(default_factory=dict) # Financial trends related to the debate
    
    # 👇 NEW: Catching the Internal Signals!
    diagnostic_patterns: Dict[str, Any] = Field(default_factory=dict)
    approved_theory: str = Field(default="")

@app.post("/boardroom/debate")
def boardroom_debate(payload: BoardroomDebateRequest) -> Dict[str, Any]:
    try:
        llm_client = get_zhipu_client()

        financial_trend = payload.financial_trend
        if not isinstance(financial_trend, dict) or not financial_trend:
            try:
                supabase = get_supabase_client()
                target_month = _normalize_report_month(payload.target_month)
                financial_trend = _fetch_financial_trend(supabase, payload.merchant_id.strip(), target_month)
            except Exception:
                financial_trend = {}

        user_prompt = (
            f"--- BUSINESS CONTEXT ---\n"
            f"Merchant Profile: {payload.merchant_profile}\n\n"
            
            f"--- INTERNAL SIGNALS ---\n"
            f"Financial Trend JSON: {json.dumps(financial_trend, indent=2)}\n"
            f"Diagnostic Data: {json.dumps(payload.diagnostic_patterns, indent=2)}\n"
            f"Approved Business Theory (includes Boss's input): {payload.approved_theory}\n\n"
            
            f"--- EXTERNAL SIGNALS ---\n"
            f"Real-World Data (Weather, Events, Competitors):\n"
            f"{json.dumps(payload.external_signals, indent=2)}\n\n"
            
            f"--- THE TASK ---\n"
            f"Here are the 3 proposed strategies to analyze:\n{payload.proposed_strategies}"
        )
        
        # 1. Define the 3 distinct Agent personas
        cmo_sys = "You are the CMO (Growth Hacker). Analyze the 3 strategies using the financial_trend plus diagnostic_patterns. Map item-level drops/spikes to external signals like weather and competitors. Pick the strategy with best demand upside and explain pros/cons in 2-3 conversational sentences."
        coo_sys = "You are the COO (Kitchen Operations). Analyze the 3 strategies using diagnostic_patterns and external signals. Identify which strategy best handles real operational bottlenecks caused by the exact items/time blocks shifting in the data. Keep it conversational in 2-3 sentences."
        cfo_sys = "You are the CFO (Risk Manager). Compare target_month against rolling_averages to determine above/below baseline. Use historical_curve to check if there are consecutive months of cash bleeding. Rank the 3 strategies by margin protection and downside risk in 2-3 sentences."

        # 2. Run the 3 Agents IN PARALLEL (Massive speed boost!)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_cmo = executor.submit(_call_text_llm, llm_client, cmo_sys, user_prompt, 0.4)
            future_coo = executor.submit(_call_text_llm, llm_client, coo_sys, user_prompt, 0.4)
            future_cfo = executor.submit(_call_text_llm, llm_client, cfo_sys, user_prompt, 0.4)
            
            cmo_text = future_cmo.result()
            coo_text = future_coo.result()
            cfo_text = future_cfo.result()

        # 3. The "Final Boss" Synthesis
        boss_sys = (
            "You are the CEO. Read your executives' opinions on the 3 strategies. "
            "Base your final decision on long-term trend direction (rolling averages + historical curve), not one-month panic. "
            "Select ONE strategy that best balances growth, operations, and finance, and explain why it wins."
        )
        boss_usr = f"CMO says:\n{cmo_text}\n\nCOO says:\n{coo_text}\n\nCFO says:\n{cfo_text}\n\nWhat is your final decision?"
        
        boss_text = _call_text_llm(llm_client, boss_sys, boss_usr, 0.2)

        # 4. Stitch it together into the "Chat Bubble" JSON array for Next.js!
        # Notice we don't need dangerous Regex anymore; we control the JSON directly!
        debate_script = [
            {"speaker": "CMO", "text": cmo_text},
            {"speaker": "COO", "text": coo_text},
            {"speaker": "CFO", "text": cfo_text},
            {"speaker": "FINAL DECISION", "text": boss_text}
        ]
        
        return {
            "status": "success",
            "debate_script": debate_script
        }
        
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Parallel debate generation failed: {exc}") from exc

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
        if verdict not in {"PROCEED", "ABORT"}:
            verdict = "PROCEED" if profit_boost > 0 else "ABORT"

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
        target_month = _normalize_report_month(payload.target_month)

        financial_trend = payload.financial_trend if isinstance(payload.financial_trend, dict) else {}
        if not financial_trend:
            financial_trend = _fetch_financial_trend(supabase, payload.merchant_id, target_month)

        diagnostic_patterns = payload.diagnostic_patterns if isinstance(payload.diagnostic_patterns, dict) else {}
        if not diagnostic_patterns:
            diagnostic_patterns = _fetch_diagnostic_patterns(supabase, payload.merchant_id, target_month)

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
        if payload.source == "BOARDROOM":
            supabase.table("monthly_summaries").update({
                "action_plan": json.dumps(roadmap_data) # Save the structured JSON
            }).eq("merchant_id", payload.merchant_id).eq("report_month", target_month).execute()

        return {
            "status": "success",
            "roadmap": roadmap_data
        }

    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Roadmap generation failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("vision_service:app", host="0.0.0.0", port=8001, reload=True)
