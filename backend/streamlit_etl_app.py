import base64
import io
import json
import os
import re
import requests
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import fitz
import pandas as pd
import streamlit as st
import zhipuai
from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()


SUPPORTED_FILE_TYPES = ["csv", "pdf", "png", "jpg", "jpeg"]


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


def _extract_model_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text_value = part.get("text") or part.get("content")
                if isinstance(text_value, str):
                    parts.append(text_value)
        return "\n".join(parts).strip()
    return str(content).strip()


def _strip_markdown_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    return cleaned


def normalize_report_month(value: str) -> Optional[str]:
    if not value:
        return None

    value = value.strip()
    regex_match = re.search(r"(20\d{2})[-_./ ]?(0?[1-9]|1[0-2])", value)
    if regex_match:
        year = int(regex_match.group(1))
        month = int(regex_match.group(2))
        return f"{year:04d}-{month:02d}"

    month_names = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }

    lowered = value.lower()
    for month_name, month_num in month_names.items():
        if month_name in lowered:
            year_match = re.search(r"(20\d{2})", lowered)
            if year_match:
                year = int(year_match.group(1))
                return f"{year:04d}-{month_num:02d}"

    return None


def extract_report_month_from_text(text: str) -> Optional[str]:
    return normalize_report_month(text)


def infer_category_from_item(item_name: str) -> str:
    lowered = (item_name or "").lower()
    if any(token in lowered for token in ["coffee", "latte", "espresso", "tea", "milo", "drink", "beverage"]):
        return "Coffee"
    if any(token in lowered for token in ["nasi", "mee", "rice", "chicken", "roti", "food", "burger", "sandwich"]):
        return "Food"
    return "Uncategorized"


def get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY environment variables."
        )

    return create_client(supabase_url, supabase_key)


def get_zhipu_client() -> Any:
    api_key = os.getenv("ZHIPU_API_KEY") or os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ZHIPU_API_KEY or ZHIPUAI_API_KEY environment variable for Vision LLM parsing.")

    if not hasattr(zhipuai, "ZhipuAI"):
        raise RuntimeError("Installed zhipuai package does not expose ZhipuAI client.")

    return zhipuai.ZhipuAI(api_key=api_key)


def file_bytes_to_data_url(file_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def call_vision_llm_json(vision_client: Any, data_url: str, prompt: str) -> Any:
    response = vision_client.chat.completions.create(
        model="glm-4.6v-flash",
        temperature=0,
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Read this document and return JSON only."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
    )

    if not getattr(response, "choices", None):
        raise RuntimeError("Vision LLM returned no choices.")

    raw_content = response.choices[0].message.content
    text = _strip_markdown_fences(_extract_model_text(raw_content))

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Vision response is not valid JSON: {exc}") from exc


def render_pdf_to_png_data_urls(file_bytes: bytes, max_pages: int = 5) -> List[str]:
    data_urls: List[str] = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page_limit = min(len(doc), max_pages)

    for page_index in range(page_limit):
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
        image_bytes = pix.tobytes("png")
        data_urls.append(file_bytes_to_data_url(image_bytes, "image/png"))

    return data_urls


def process_sales_csv(uploaded_file: Any) -> Tuple[float, Dict[str, float], Optional[str]]:
    try:
        file_bytes = uploaded_file.getvalue()
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(f"Failed to read CSV {uploaded_file.name}: {exc}") from exc

    if df.empty:
        raise ValueError(f"CSV {uploaded_file.name} is empty.")

    normalized_cols = {str(col).strip().lower(): col for col in df.columns}

    def pick_col(candidates: List[str]) -> Optional[str]:
        for candidate in candidates:
            if candidate in normalized_cols:
                return normalized_cols[candidate]
        return None

    amount_col = pick_col(["total", "amount", "line_total", "sales_amount", "total_amount", "revenue"])
    qty_col = pick_col(["quantity", "qty", "units_sold"])
    unit_price_col = pick_col(["unit_price", "price", "selling_price"])
    category_col = pick_col(["category", "item_category", "product_category", "type"])
    item_col = pick_col(["item_name", "item", "product", "menu_item", "name"])
    date_col = pick_col(["date", "order_date", "log_date", "transaction_date"])

    if amount_col:
        revenue_series = pd.to_numeric(df[amount_col], errors="coerce")
    elif qty_col and unit_price_col:
        quantity = pd.to_numeric(df[qty_col], errors="coerce")
        unit_price = pd.to_numeric(df[unit_price_col], errors="coerce")
        revenue_series = quantity * unit_price
    else:
        raise ValueError(
            f"CSV {uploaded_file.name} is malformed. Include either amount/total column or quantity + unit_price columns."
        )

    valid_mask = revenue_series.notna()
    if valid_mask.sum() == 0:
        raise ValueError(f"CSV {uploaded_file.name} has no valid numeric sales rows.")

    df_valid = df.loc[valid_mask].copy()
    df_valid["_revenue"] = revenue_series.loc[valid_mask].astype(float)

    if category_col:
        df_valid["_category"] = df_valid[category_col].fillna("").astype(str).str.strip()
        if item_col:
            blank_mask = df_valid["_category"] == ""
            df_valid.loc[blank_mask, "_category"] = df_valid.loc[blank_mask, item_col].astype(str).map(infer_category_from_item)
        df_valid.loc[df_valid["_category"] == "", "_category"] = "Uncategorized"
    else:
        if item_col:
            df_valid["_category"] = df_valid[item_col].astype(str).map(infer_category_from_item)
        else:
            df_valid["_category"] = "Uncategorized"

    grouped = df_valid.groupby("_category", dropna=False)["_revenue"].sum()
    category_revenue = {k: round(float(v), 2) for k, v in grouped.to_dict().items()}
    total_revenue = round(float(df_valid["_revenue"].sum()), 2)

    inferred_month = None
    if date_col:
        parsed_dates = pd.to_datetime(df_valid[date_col], errors="coerce", dayfirst=True)
        parsed_dates = parsed_dates.dropna()
        if not parsed_dates.empty:
            month_counts = parsed_dates.dt.strftime("%Y-%m").value_counts()
            inferred_month = month_counts.index[0]

    return total_revenue, category_revenue, inferred_month


def parse_pl_from_image_data_url(vision_client: Any, data_url: str) -> List[Dict[str, Any]]:
    prompt = (
        "You are parsing a profit and loss statement image for a restaurant. "
        "Extract ONLY fixed operating costs and return JSON array with this schema: "
        "[{\"expense_type\":\"Rent|Payroll|Utilities|Other\",\"amount\":number}]. "
        "Ignore revenue lines and ingredient purchase lines. Return JSON only."
    )
    parsed = call_vision_llm_json(vision_client, data_url, prompt)
    if isinstance(parsed, dict):
        parsed = parsed.get("expenses", [])
    if not isinstance(parsed, list):
        raise ValueError("P&L parser expected a JSON array.")

    output: List[Dict[str, Any]] = []
    for row in parsed:
        if not isinstance(row, dict):
            continue
        expense_type = str(row.get("expense_type", "Other")).strip() or "Other"
        amount = round(_to_float(row.get("amount"), 0.0), 2)
        if amount > 0:
            output.append({"expense_type": expense_type, "amount": amount})

    return output


def parse_invoice_from_image_data_url(vision_client: Any, data_url: str) -> List[Dict[str, Any]]:
    prompt = (
        "You are parsing a supplier invoice for an F&B merchant. "
        "Extract ingredient-level lines and return JSON array with this schema: "
        "[{\"item_category\":\"Protein|Vegetable|Dry Goods|Dairy|Beverage|Other\","
        "\"item_name\":string,\"quantity\":number,\"unit\":string,\"unit_cost\":number,\"total_amount\":number}]. "
        "Return JSON only."
    )
    parsed = call_vision_llm_json(vision_client, data_url, prompt)
    if isinstance(parsed, dict):
        parsed = parsed.get("items", [])
    if not isinstance(parsed, list):
        raise ValueError("Invoice parser expected a JSON array.")

    output: List[Dict[str, Any]] = []
    for row in parsed:
        if not isinstance(row, dict):
            continue

        item_name = str(row.get("item_name", "")).strip()
        if not item_name:
            continue

        quantity = _to_float(row.get("quantity"), 0.0)
        unit = str(row.get("unit", "unit")).strip() or "unit"
        unit_cost = round(_to_float(row.get("unit_cost"), 0.0), 2)
        total_amount = round(_to_float(row.get("total_amount"), 0.0), 2)

        if total_amount <= 0 and quantity > 0 and unit_cost > 0:
            total_amount = round(quantity * unit_cost, 2)

        if total_amount <= 0:
            continue

        item_category = str(row.get("item_category", "Other")).strip() or "Other"
        output.append(
            {
                "item_category": item_category,
                "item_name": item_name,
                "quantity": quantity,
                "unit": unit,
                "unit_cost": unit_cost,
                "total_amount": total_amount,
            }
        )

    return output


def is_pl_document(filename: str) -> bool:
    lowered = filename.lower()
    return any(token in lowered for token in ["p&l", "profit", "loss", "overhead", "expense", "fixed_cost"])


def is_invoice_document(filename: str) -> bool:
    lowered = filename.lower()
    return any(token in lowered for token in ["invoice", "supplier", "purchase", "ingredients", "bill"])


def merge_category_revenue(target: Dict[str, float], incoming: Dict[str, float]) -> Dict[str, float]:
    merged = defaultdict(float)
    for category, amount in target.items():
        merged[category] += float(amount)
    for category, amount in incoming.items():
        merged[category] += float(amount)
    return {k: round(v, 2) for k, v in merged.items()}


def upsert_monthly_summary(supabase: Client, payload: Dict[str, Any]) -> str:
    upsert_error: Optional[Exception] = None

    try:
        response = (
            supabase.table("monthly_summaries")
            .upsert(payload, on_conflict="merchant_id,report_month")
            .execute()
        )
        if response.data and len(response.data) > 0 and response.data[0].get("id"):
            return str(response.data[0]["id"])
    except Exception as exc:
        upsert_error = exc

    existing = (
        supabase.table("monthly_summaries")
        .select("id")
        .eq("merchant_id", payload["merchant_id"])
        .eq("report_month", payload["report_month"])
        .limit(1)
        .execute()
    )

    if existing.data:
        summary_id = existing.data[0]["id"]
        supabase.table("monthly_summaries").update(payload).eq("id", summary_id).execute()
        return str(summary_id)

    inserted = supabase.table("monthly_summaries").insert(payload).execute()
    if inserted.data and inserted.data[0].get("id"):
        return str(inserted.data[0]["id"])

    if upsert_error:
        raise RuntimeError(f"Failed to upsert monthly_summaries: {upsert_error}")

    raise RuntimeError("Failed to write monthly_summaries record.")


def replace_operating_expenses(supabase: Client, summary_id: str, expenses: List[Dict[str, Any]]) -> int:
    supabase.table("operating_expenses").delete().eq("summary_id", summary_id).execute()

    if not expenses:
        return 0

    payload = [
        {
            "summary_id": summary_id,
            "expense_type": row["expense_type"],
            "amount": row["amount"],
        }
        for row in expenses
    ]

    inserted_count = 0
    batch_size = 200
    for i in range(0, len(payload), batch_size):
        batch = payload[i : i + batch_size]
        supabase.table("operating_expenses").insert(batch).execute()
        inserted_count += len(batch)

    return inserted_count


def replace_supplier_invoices(supabase: Client, summary_id: str, invoices: List[Dict[str, Any]]) -> int:
    supabase.table("supplier_invoices").delete().eq("summary_id", summary_id).execute()

    if not invoices:
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
        for row in invoices
    ]

    inserted_count = 0
    batch_size = 200
    for i in range(0, len(payload), batch_size):
        batch = payload[i : i + batch_size]
        supabase.table("supplier_invoices").insert(batch).execute()
        inserted_count += len(batch)

    return inserted_count


def parse_document_file(
    vision_client: Any,
    file_name: str,
    file_bytes: bytes,
    file_ext: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    pl_rows: List[Dict[str, Any]] = []
    invoice_rows: List[Dict[str, Any]] = []

    if file_ext in {"png", "jpg", "jpeg"}:
        mime = "image/png" if file_ext == "png" else "image/jpeg"
        data_url = file_bytes_to_data_url(file_bytes, mime)

        if is_pl_document(file_name):
            pl_rows.extend(parse_pl_from_image_data_url(vision_client, data_url))
        elif is_invoice_document(file_name):
            invoice_rows.extend(parse_invoice_from_image_data_url(vision_client, data_url))
        else:
            candidate_expenses = parse_pl_from_image_data_url(vision_client, data_url)
            if candidate_expenses:
                pl_rows.extend(candidate_expenses)
            else:
                invoice_rows.extend(parse_invoice_from_image_data_url(vision_client, data_url))

    elif file_ext == "pdf":
        data_urls = render_pdf_to_png_data_urls(file_bytes)
        if not data_urls:
            raise ValueError(f"No pages could be rendered from PDF {file_name}.")

        for data_url in data_urls:
            if is_pl_document(file_name):
                pl_rows.extend(parse_pl_from_image_data_url(vision_client, data_url))
            elif is_invoice_document(file_name):
                invoice_rows.extend(parse_invoice_from_image_data_url(vision_client, data_url))
            else:
                candidate_expenses = parse_pl_from_image_data_url(vision_client, data_url)
                if candidate_expenses:
                    pl_rows.extend(candidate_expenses)
                else:
                    invoice_rows.extend(parse_invoice_from_image_data_url(vision_client, data_url))

    return pl_rows, invoice_rows


def run_pipeline(merchant_id: str, report_month_input: str, uploaded_files: List[Any]) -> Dict[str, Any]:
    if not merchant_id.strip():
        raise ValueError("merchant_id is required.")

    if not uploaded_files:
        raise ValueError("Please upload at least one file.")

    supabase = get_supabase_client()

    total_revenue = 0.0
    category_revenue: Dict[str, float] = {}
    operating_expenses: List[Dict[str, Any]] = []
    supplier_invoices: List[Dict[str, Any]] = []

    detected_months: List[str] = []
    file_errors: List[str] = []

    vision_client: Optional[Any] = None

    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name
        file_ext = file_name.split(".")[-1].lower()

        if file_ext not in SUPPORTED_FILE_TYPES:
            file_errors.append(f"Unsupported file type for {file_name}.")
            continue

        month_from_name = extract_report_month_from_text(file_name)
        if month_from_name:
            detected_months.append(month_from_name)

        try:
            if file_ext == "csv":
                csv_revenue, csv_category_revenue, month_from_data = process_sales_csv(uploaded_file)
                total_revenue += csv_revenue
                category_revenue = merge_category_revenue(category_revenue, csv_category_revenue)
                if month_from_data:
                    detected_months.append(month_from_data)
            else:
                if vision_client is None:
                    vision_client = get_zhipu_client()

                file_bytes = uploaded_file.getvalue()
                pl_rows, invoice_rows = parse_document_file(vision_client, file_name, file_bytes, file_ext)
                operating_expenses.extend(pl_rows)
                supplier_invoices.extend(invoice_rows)

        except Exception as exc:
            file_errors.append(f"{file_name}: {exc}")

    report_month = normalize_report_month(report_month_input)

    if not report_month:
        unique_months = sorted(set(detected_months))
        if len(unique_months) == 1:
            report_month = unique_months[0]
        elif len(unique_months) > 1:
            raise ValueError(
                f"Detected multiple report months {unique_months}. Enter report_month manually in YYYY-MM format."
            )
        else:
            raise ValueError("Unable to determine report_month from files. Enter report_month manually in YYYY-MM format.")

    total_fixed_costs = round(sum(row["amount"] for row in operating_expenses), 2)
    total_ingredient_costs = round(sum(row["total_amount"] for row in supplier_invoices), 2)
    net_profit = round(total_revenue - (total_fixed_costs + total_ingredient_costs), 2)

    summary_payload = {
        "merchant_id": merchant_id.strip(),
        "report_month": report_month,
        "total_revenue": round(total_revenue, 2),
        "total_fixed_costs": total_fixed_costs,
        "total_ingredient_costs": total_ingredient_costs,
        "net_profit": net_profit,
        "category_revenue": category_revenue,
    }

    summary_id = upsert_monthly_summary(supabase, summary_payload)

    inserted_expenses = replace_operating_expenses(supabase, summary_id, operating_expenses)
    inserted_invoices = replace_supplier_invoices(supabase, summary_id, supplier_invoices)

    supabase.table("monthly_summaries").update(
        {
            "total_revenue": round(total_revenue, 2),
            "total_fixed_costs": total_fixed_costs,
            "total_ingredient_costs": total_ingredient_costs,
            "net_profit": net_profit,
            "category_revenue": category_revenue,
        }
    ).eq("id", summary_id).execute()

    return {
        "summary_id": summary_id,
        "merchant_id": merchant_id,
        "report_month": report_month,
        "total_revenue": round(total_revenue, 2),
        "total_fixed_costs": total_fixed_costs,
        "total_ingredient_costs": total_ingredient_costs,
        "net_profit": net_profit,
        "category_revenue": category_revenue,
        "operating_expenses_count": inserted_expenses,
        "supplier_invoices_count": inserted_invoices,
        "file_errors": file_errors,
        "processed_at": datetime.utcnow().isoformat() + "Z",
    }


def call_text_llm(client: Any, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    response = client.chat.completions.create(
        model="glm-4.7-flash",
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    if not getattr(response, "choices", None):
        raise RuntimeError("Text LLM returned no choices.")

    return _extract_model_text(response.choices[0].message.content)


def get_previous_month(month_str: str) -> str:
    dt = datetime.strptime(f"{month_str}-01", "%Y-%m-%d")
    if dt.month == 1:
        return f"{dt.year - 1}-12"
    return f"{dt.year:04d}-{dt.month - 1:02d}"


def fetch_diagnostic_patterns(supabase: Client, merchant_id: str, target_month: str) -> Dict[str, Any]:
    res = (
        supabase.table("monthly_summaries")
        .select("diagnostic_patterns")
        .eq("merchant_id", merchant_id)
        .eq("report_month", target_month)
        .limit(1)
        .execute()
    )

    if not res.data:
        raise ValueError("No monthly_summaries row found for this merchant_id and target_month.")

    diagnostic_patterns = res.data[0].get("diagnostic_patterns")
    if not isinstance(diagnostic_patterns, dict):
        raise ValueError("diagnostic_patterns JSON is missing or invalid for this month.")

    return diagnostic_patterns


def fetch_financial_comparison(supabase: Client, merchant_id: str, target_month: str) -> Dict[str, Any]:
    baseline_month = get_previous_month(target_month)

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
        raise ValueError(
            f"No monthly_summaries row found for baseline month {baseline_month}. "
            "State 1 requires both baseline and target financial data."
        )
    if not target_res.data:
        raise ValueError(
            f"No monthly_summaries row found for target month {target_month}. "
            "State 1 requires both baseline and target financial data."
        )

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


def fetch_merchant_profile(supabase: Client, merchant_id: str) -> str:
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
    if not merchant_profile.strip():
        return "Malaysia"

    # Keep this simple: pass merchant profile to geocoder, fallback to Malaysia.
    return merchant_profile


def _target_month_date_range(target_month: str) -> Tuple[str, str]:
    month_start = datetime.strptime(f"{target_month}-01", "%Y-%m-%d")
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    month_end = (next_month - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    return month_start.strftime("%Y-%m-%d"), month_end


def _geocode_location(location_query: str) -> Dict[str, Any]:
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "tauke-ai-boardroom/1.0"}
    params = {"q": location_query, "format": "json", "limit": 1}

    resp = requests.get(url, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return {}

    top = data[0]
    return {
        "lat": float(top.get("lat")),
        "lon": float(top.get("lon")),
        "display_name": top.get("display_name", ""),
    }


def fetch_news_signal(merchant_profile: str, target_month: str) -> Dict[str, Any]:
    gnews_api_key = os.getenv("GNEWS_API_KEY")
    serper_api_key = os.getenv("SERPER_API_KEY")
    start_date, end_date = _target_month_date_range(target_month)
    query = f"Malaysia food OR cafe OR restaurant {target_month}"

    try:
        if not gnews_api_key:
            raise ValueError("Missing GNEWS_API_KEY")

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
        articles = data.get("articles", []) if isinstance(data, dict) else []
        compact = [
            {
                "title": art.get("title", ""),
                "source": (art.get("source") or {}).get("name", "") if isinstance(art.get("source"), dict) else "",
                "published_at": art.get("publishedAt", ""),
                "url": art.get("url", ""),
            }
            for art in articles[:5]
            if isinstance(art, dict)
        ]
        return {"attempted": True, "status": "ok", "provider": "gnews", "data": compact}
    except Exception as exc:
        # Fallback to Serper if GNews fails or key is missing.
        try:
            if not serper_api_key:
                raise ValueError("Missing SERPER_API_KEY")

            serper_url = "https://google.serper.dev/search"
            headers = {
                "X-API-KEY": serper_api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "q": query,
                "gl": "my",
                "hl": "en",
                "num": 5,
            }
            serper_resp = requests.post(serper_url, headers=headers, json=payload, timeout=20)
            serper_resp.raise_for_status()
            serper_data = serper_resp.json()
            organic = serper_data.get("organic", []) if isinstance(serper_data, dict) else []
            compact = [
                {
                    "title": item.get("title", ""),
                    "source": item.get("source", ""),
                    "published_at": item.get("date", ""),
                    "url": item.get("link", ""),
                }
                for item in organic[:5]
                if isinstance(item, dict)
            ]
            return {
                "attempted": True,
                "status": "ok",
                "provider": "serper",
                "fallback_from": str(exc),
                "data": compact,
            }
        except Exception as fallback_exc:
            return {
                "attempted": True,
                "status": "error",
                "error": f"GNews failed: {exc}; Serper fallback failed: {fallback_exc}",
                "data": [],
            }


def fetch_weather_signal(merchant_profile: str, target_month: str) -> Dict[str, Any]:
    openweather_api_key = os.getenv("OPENWEATHER_API_KEY")

    try:
        if not openweather_api_key:
            raise ValueError("Missing OPENWEATHER_API_KEY")

        location_query = _extract_location_hint(merchant_profile)
        geocode_url = "https://api.openweathermap.org/geo/1.0/direct"
        geo_params = {
            "q": location_query,
            "limit": 1,
            "appid": openweather_api_key,
        }
        geo_resp = requests.get(geocode_url, params=geo_params, timeout=20)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if not geo_data:
            return {
                "attempted": True,
                "status": "error",
                "error": "Unable to geocode location from merchant profile.",
                "data": {},
            }

        geo_top = geo_data[0]
        lat = float(geo_top.get("lat"))
        lon = float(geo_top.get("lon"))
        weather_url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": openweather_api_key,
            "units": "metric",
        }
        resp = requests.get(weather_url, params=params, timeout=25)
        resp.raise_for_status()
        data = resp.json()
        weather = data.get("weather", []) if isinstance(data, dict) else []
        main_obj = data.get("main", {}) if isinstance(data, dict) else {}
        rain_obj = data.get("rain", {}) if isinstance(data, dict) else {}

        weather_summary = {
            "target_month": target_month,
            "location": f"{geo_top.get('name', '')}, {geo_top.get('country', '')}",
            "current_temp_c": _to_float(main_obj.get("temp"), 0.0),
            "humidity_pct": _to_float(main_obj.get("humidity"), 0.0),
            "condition": weather[0].get("main", "") if weather and isinstance(weather[0], dict) else "",
            "rain_1h_mm": _to_float(rain_obj.get("1h"), 0.0),
            "note": "OpenWeather free endpoint provides current weather context, not full historical month aggregates.",
        }
        return {"attempted": True, "status": "ok", "data": weather_summary}
    except Exception as exc:
        return {"attempted": True, "status": "error", "error": str(exc), "data": {}}


def fetch_places_signal(merchant_profile: str) -> Dict[str, Any]:
    google_places_api_key = os.getenv("GOOGLE_PLACES_API_KEY")

    try:
        if not google_places_api_key:
            raise ValueError("Missing GOOGLE_PLACES_API_KEY")

        location_query = _extract_location_hint(merchant_profile)
        places_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": f"cafe OR restaurant near {location_query}",
            "key": google_places_api_key,
        }
        resp = requests.get(places_url, params=params, timeout=25)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", []) if isinstance(data, dict) else []

        top_places = [
            {
                "name": place.get("name", ""),
                "rating": place.get("rating"),
                "user_ratings_total": place.get("user_ratings_total"),
                "formatted_address": place.get("formatted_address", ""),
                "business_status": place.get("business_status", ""),
            }
            for place in results[:5]
            if isinstance(place, dict)
        ]

        places_summary = {
            "query": location_query,
            "nearby_food_venue_count": len(results),
            "top_places": top_places,
        }
        return {"attempted": True, "status": "ok", "data": places_summary}
    except Exception as exc:
        return {"attempted": True, "status": "error", "error": str(exc), "data": {}}


def fetch_external_signals(merchant_profile: str, target_month: str) -> Dict[str, Any]:
    news = fetch_news_signal(merchant_profile, target_month)
    weather = fetch_weather_signal(merchant_profile, target_month)
    places = fetch_places_signal(merchant_profile)
    return {
        "news": news,
        "weather": weather,
        "places": places,
        "required_tools_attempted": bool(
            news.get("attempted") and weather.get("attempted") and places.get("attempted")
        ),
    }


def analyst_interrogation_prompt(
    financial_comparison: Dict[str, Any],
    diagnostic_json: Dict[str, Any],
) -> Tuple[str, str]:
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
        "High-level financial comparison (baseline vs target):\n"
        f"{json.dumps(financial_comparison, indent=2)}\n\n"
        "Diagnostic JSON:\n"
        f"{json.dumps(diagnostic_json, indent=2)}\n\n"
        "Return plain text with numbered questions only."
    )
    return system_prompt, user_prompt


def analyst_synthesis_prompt(
    merchant_profile: str,
    diagnostic_json: Dict[str, Any],
    boss_answers: str,
    external_signals: Dict[str, Any],
    target_month: str,
) -> Tuple[str, str]:
    system_prompt = (
        "You are an expert F&B Analyst. Evidence-first reasoning is mandatory. "
        "You MUST use all required external tools: News, Places, Weather. "
        "External evidence is mandatory but secondary to internal database evidence and Boss answers. "
        "Do not invent tool results. If a tool failed, state the limitation and proceed with calibrated confidence."
    )
    user_prompt = (
        f"Target month: {target_month}\n"
        f"Merchant profile: {merchant_profile}\n\n"
        "12-point diagnostic JSON:\n"
        f"{json.dumps(diagnostic_json, indent=2)}\n\n"
        "Boss answers to your questions:\n"
        f"{boss_answers}\n\n"
        "External signals (mandatory tools already called):\n"
        f"{json.dumps(external_signals, indent=2)}\n\n"
        "Write Theory V1 in this exact section format:\n"
        "1) Theory V1 Summary\n"
        "2) Internal Data Evidence\n"
        "3) Boss Context Evidence\n"
        "4) External Evidence (News/Places/Weather)\n"
        "5) Magnitude Check\n"
        "6) Strategic Recommendation (So What)\n"
        "7) Confidence and Unknowns\n"
        "Keep it concise and specific to this merchant type."
    )
    return system_prompt, user_prompt


def supervisor_review_prompt(
    diagnostic_json: Dict[str, Any],
    boss_answers: str,
    theory_v1: str,
    external_signals: Dict[str, Any],
) -> Tuple[str, str]:
    system_prompt = (
        "You are the ruthless CFO Supervisor. Review the Analyst's Theory V1 against the original "
        "JSON data and the Boss's answers. You are the gatekeeper.\n\n"
        "You MUST evaluate the theory against these strict criteria:\n"
        "Reject if the Analyst did not use all required tools and data points.\n"
        "Reject if any major claim lacks internal-data grounding.\n"
        "Reject if the Analyst ignores or contradicts the Boss's direct answers.\n"
        "Reject if the Analyst fails the Magnitude Test (blaming a massive revenue drop on a minor 2-day external event).\n"
        "Reject if the report lacks a strategic, actionable business recommendation (The So What rule).\n\n"
        "Approve ONLY when external findings are used as supporting context, not replacement truth, and all criteria are met. "
        "If rejecting, provide a short, sharp critique routing it back to the Analyst. "
        "If approving, output the final stamped report."
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
        "Return in this exact format:\n"
        "Decision: APPROVED or REJECTED\n"
        "Gate Checks:\n"
        "- Tool/Data Coverage: PASS/FAIL\n"
        "- Internal Grounding: PASS/FAIL\n"
        "- Boss Alignment: PASS/FAIL\n"
        "- Magnitude Test: PASS/FAIL\n"
        "- So-What Rule: PASS/FAIL\n"
        "Supervisor Verdict:\n"
        "(Short, sharp evaluation)"
    )
    return system_prompt, user_prompt


def extract_supervisor_decision(supervisor_evaluation: str) -> str:
    text = (supervisor_evaluation or "").upper()
    match = re.search(r"DECISION\s*:\s*(APPROVED|REJECTED)", text)
    if match:
        return match.group(1)
    if "APPROVED" in text and "REJECTED" not in text:
        return "APPROVED"
    if "REJECTED" in text:
        return "REJECTED"
    return "UNKNOWN"


def strategist_action_plan_prompt(
    merchant_profile: str,
    diagnostic_json: Dict[str, Any],
    boss_answers: str,
    final_approved_theory: str,
) -> Tuple[str, str]:
    system_prompt = (
        "You are an elite F&B Business Strategist. You have just read the Final Theory regarding why this business's revenue shifted. "
        "You also have their 12-point internal data patterns and their merchant profile. "
        "Your task is to generate the 'Top 3 Strategic Action Plans' for the Boss to execute immediately.\n\n"
        "Strict Rules:\n\n"
        "No Generic Advice: Do NOT say 'Run a social media campaign' or 'Offer a discount.'\n\n"
        "Hyper-Specific: You must name specific items from their data (e.g., 'Kopi C Ais', 'Nasi Lemak Ayam'), specify exact times of day "
        "(e.g., 'Target the 2 PM - 6 PM Afternoon slump'), and suggest specific price points or bundle strategies based on their "
        "Average Order Value (AOV) and Units Per Transaction (UPT).\n\n"
        "Leverage Strengths: If a specific item or time block grew (e.g., 'Evening sales grew 5%'), at least one suggestion must focus "
        "on accelerating that growth, not just fixing the drops.\n\n"
        "Format: Output the response as 3 distinct, bolded Action Items, each followed by a short paragraph explaining the exact 'Why' "
        "and 'How' based strictly on the data."
    )
    user_prompt = (
        f"Merchant profile:\n{merchant_profile}\n\n"
        "12-point diagnostic JSON:\n"
        f"{json.dumps(diagnostic_json, indent=2)}\n\n"
        "Boss answers:\n"
        f"{boss_answers}\n\n"
        "Final approved theory:\n"
        f"{final_approved_theory}\n"
    )
    return system_prompt, user_prompt


def _push_chat(role: str, speaker: str, content: str) -> None:
    st.session_state.boardroom_chat.append(
        {
            "role": role,
            "speaker": speaker,
            "content": content,
        }
    )


def _render_chat_history() -> None:
    for msg in st.session_state.boardroom_chat:
        with st.chat_message(msg["role"]):
            st.markdown(f"**{msg['speaker']}**\n\n{msg['content']}")


def init_boardroom_state() -> None:
    defaults = {
        "boardroom_state": 0,
        "boardroom_chat": [],
        "boardroom_merchant_id": "",
        "boardroom_target_month": "",
        "boardroom_merchant_profile": "",
        "boardroom_diagnostic_json": None,
        "boardroom_financial_comparison": None,
        "boardroom_analyst_questions": "",
        "boardroom_boss_answers": "",
        "boardroom_theory_v1": "",
        "boardroom_supervisor_eval": "",
        "boardroom_supervisor_decision": "UNKNOWN",
        "boardroom_final_approved_theory": "",
        "boardroom_strategist_plan": "",
        "boardroom_external_signals": None,
        "boardroom_state1_done": False,
        "boardroom_state3_done": False,
        "boardroom_state4_done": False,
        "boardroom_state5_done": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_etl_tab() -> None:
    st.subheader("Tauke.ai Monthly ETL Processor")
    st.caption("Upload CSV, PDF, PNG, JPG files and load monthly results into Supabase.")

    merchant_id = st.text_input("merchant_id", placeholder="e.g. c6417c1f-56ee-4f6a-bab8-def781d9418f")
    report_month_input = st.text_input("report_month (optional)", placeholder="YYYY-MM")

    uploaded_files = st.file_uploader(
        "Upload sales CSV, P&L images/PDFs, and supplier invoice images/PDFs",
        type=SUPPORTED_FILE_TYPES,
        accept_multiple_files=True,
    )

    if uploaded_files:
        st.write(f"Files selected: {len(uploaded_files)}")
        st.write([f.name for f in uploaded_files])

    if st.button("Process All", type="primary"):
        try:
            result = run_pipeline(merchant_id, report_month_input, uploaded_files or [])
            st.success("Pipeline completed successfully.")
            st.json(result)

            if result["file_errors"]:
                st.warning("Some files could not be fully processed.")
                for err in result["file_errors"]:
                    st.write(f"- {err}")

        except Exception as exc:
            st.error(f"Processing failed: {exc}")


def render_boardroom_tab() -> None:
    init_boardroom_state()
    st.subheader("Boardroom Agentic Audit")
    st.caption("State machine: 0 Init -> 1 Interrogation -> 2 Boss Input -> 3 Synthesis -> 4 Peer Review -> 5 Strategy")

    merchant_id = st.text_input(
        "merchant_id for audit",
        key="boardroom_input_merchant_id",
        placeholder="e.g. af065e86-3643-4ef6-8a37-eaff5258f82b",
    )
    target_month = st.text_input(
        "target_month",
        key="boardroom_input_target_month",
        placeholder="YYYY-MM",
        value="2026-04",
    )

    run_clicked = st.button("Run Monthly Audit", type="primary", key="boardroom_run_monthly_audit")

    if run_clicked:
        if not merchant_id.strip() or not normalize_report_month(target_month):
            st.error("Please provide a valid merchant_id and target_month (YYYY-MM).")
        else:
            st.session_state.boardroom_state = 1
            st.session_state.boardroom_chat = []
            st.session_state.boardroom_merchant_id = merchant_id.strip()
            st.session_state.boardroom_target_month = normalize_report_month(target_month) or target_month
            st.session_state.boardroom_merchant_profile = ""
            st.session_state.boardroom_diagnostic_json = None
            st.session_state.boardroom_financial_comparison = None
            st.session_state.boardroom_analyst_questions = ""
            st.session_state.boardroom_boss_answers = ""
            st.session_state.boardroom_theory_v1 = ""
            st.session_state.boardroom_supervisor_eval = ""
            st.session_state.boardroom_supervisor_decision = "UNKNOWN"
            st.session_state.boardroom_final_approved_theory = ""
            st.session_state.boardroom_strategist_plan = ""
            st.session_state.boardroom_external_signals = None
            st.session_state.boardroom_state1_done = False
            st.session_state.boardroom_state3_done = False
            st.session_state.boardroom_state4_done = False
            st.session_state.boardroom_state5_done = False

    _render_chat_history()

    if st.session_state.boardroom_state == 0:
        st.info("State 0: Click Run Monthly Audit to start the boardroom loop.")
        return

    try:
        supabase = get_supabase_client()
        llm_client = get_zhipu_client()

        if st.session_state.boardroom_state == 1 and not st.session_state.boardroom_state1_done:
            financial_comparison = fetch_financial_comparison(
                supabase,
                st.session_state.boardroom_merchant_id,
                st.session_state.boardroom_target_month,
            )
            diagnostic_json = fetch_diagnostic_patterns(
                supabase,
                st.session_state.boardroom_merchant_id,
                st.session_state.boardroom_target_month,
            )
            st.session_state.boardroom_financial_comparison = financial_comparison
            st.session_state.boardroom_diagnostic_json = diagnostic_json

            sys_prompt, usr_prompt = analyst_interrogation_prompt(financial_comparison, diagnostic_json)
            questions = call_text_llm(llm_client, sys_prompt, usr_prompt, temperature=0.1)
            st.session_state.boardroom_analyst_questions = questions
            _push_chat("assistant", "Analyst", questions)

            st.session_state.boardroom_state1_done = True
            st.session_state.boardroom_state = 2
            st.rerun()

        if st.session_state.boardroom_state == 2:
            boss_reply = st.chat_input("State 2: Boss, answer the Analyst questions.")
            if boss_reply:
                st.session_state.boardroom_boss_answers = boss_reply.strip()
                _push_chat("user", "Boss", boss_reply.strip())
                st.session_state.boardroom_state = 3
                st.rerun()

        if st.session_state.boardroom_state == 3 and not st.session_state.boardroom_state3_done:
            diagnostic_json = st.session_state.boardroom_diagnostic_json or {}
            merchant_profile = fetch_merchant_profile(supabase, st.session_state.boardroom_merchant_id)
            st.session_state.boardroom_merchant_profile = merchant_profile
            external_signals = fetch_external_signals(
                merchant_profile,
                st.session_state.boardroom_target_month,
            )
            st.session_state.boardroom_external_signals = external_signals

            sys_prompt, usr_prompt = analyst_synthesis_prompt(
                merchant_profile=merchant_profile,
                diagnostic_json=diagnostic_json,
                boss_answers=st.session_state.boardroom_boss_answers,
                external_signals=external_signals,
                target_month=st.session_state.boardroom_target_month,
            )
            theory_v1 = call_text_llm(llm_client, sys_prompt, usr_prompt, temperature=0.2)
            st.session_state.boardroom_theory_v1 = theory_v1
            _push_chat("assistant", "Analyst", theory_v1)

            st.session_state.boardroom_state3_done = True
            st.session_state.boardroom_state = 4
            st.rerun()

        if st.session_state.boardroom_state == 4 and not st.session_state.boardroom_state4_done:
            diagnostic_json = st.session_state.boardroom_diagnostic_json or {}
            external_signals = st.session_state.boardroom_external_signals or {}

            sys_prompt, usr_prompt = supervisor_review_prompt(
                diagnostic_json=diagnostic_json,
                boss_answers=st.session_state.boardroom_boss_answers,
                theory_v1=st.session_state.boardroom_theory_v1,
                external_signals=external_signals,
            )
            supervisor_eval = call_text_llm(llm_client, sys_prompt, usr_prompt, temperature=0.1)
            st.session_state.boardroom_supervisor_eval = supervisor_eval
            _push_chat("assistant", "Supervisor", supervisor_eval)

            decision = extract_supervisor_decision(supervisor_eval)
            st.session_state.boardroom_supervisor_decision = decision
            st.session_state.boardroom_state4_done = True

            if decision == "APPROVED":
                st.session_state.boardroom_final_approved_theory = st.session_state.boardroom_theory_v1
                st.session_state.boardroom_state = 5
            else:
                st.session_state.boardroom_state = 4

            st.rerun()

        if st.session_state.boardroom_state == 5 and not st.session_state.boardroom_state5_done:
            diagnostic_json = st.session_state.boardroom_diagnostic_json or {}
            merchant_profile = st.session_state.boardroom_merchant_profile or ""

            sys_prompt, usr_prompt = strategist_action_plan_prompt(
                merchant_profile=merchant_profile,
                diagnostic_json=diagnostic_json,
                boss_answers=st.session_state.boardroom_boss_answers,
                final_approved_theory=st.session_state.boardroom_final_approved_theory,
            )
            strategist_plan = call_text_llm(llm_client, sys_prompt, usr_prompt, temperature=0.2)
            st.session_state.boardroom_strategist_plan = strategist_plan
            _push_chat("assistant", "Strategist", strategist_plan)

            st.session_state.boardroom_state5_done = True
            st.rerun()

        if st.session_state.boardroom_state == 4 and st.session_state.boardroom_state4_done:
            if st.session_state.boardroom_supervisor_decision == "APPROVED":
                st.info("State 4 approved. Proceeding to State 5 strategy generation.")
            else:
                st.warning("Boardroom loop stopped at State 4 because Supervisor did not approve the theory.")

        if st.session_state.boardroom_state == 5 and st.session_state.boardroom_state5_done:
            st.success("Boardroom loop complete. Strategic action plan generated.")

    except Exception as exc:
        st.error(f"Boardroom flow failed: {exc}")


def main() -> None:
    st.set_page_config(page_title="Tauke.ai ETL + Boardroom", layout="wide")
    st.title("Tauke.ai Operations Console")

    etl_tab, boardroom_tab = st.tabs(["ETL Processor", "Boardroom Audit"])

    with etl_tab:
        render_etl_tab()

    with boardroom_tab:
        render_boardroom_tab()


if __name__ == "__main__":
    main()
