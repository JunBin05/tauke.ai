import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()


def _require_api_key(env_name: str) -> str:
    api_key = os.getenv(env_name)
    if not api_key:
        raise ValueError(f"Missing {env_name} environment variable")
    return api_key


def _normalize_date_range(date_range: Any) -> Tuple[str, str]:
    """
    Accepts one of:
    - (start_date, end_date)
    - [start_date, end_date]
    - {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    - "YYYY-MM-DD,YYYY-MM-DD"
    """
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        return str(date_range[0]), str(date_range[1])

    if isinstance(date_range, dict):
        start = date_range.get("start")
        end = date_range.get("end")
        if start and end:
            return str(start), str(end)

    if isinstance(date_range, str):
        parts = [p.strip() for p in date_range.split(",")]
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1]

    raise ValueError(
        "date_range must be (start,end), [start,end], {'start':..., 'end':...}, or 'start,end'"
    )


def search_news(query: str) -> Dict[str, Any]:
    """
    search_news(query) [GNEWS_API_KEY]
    Use this specifically to search for official news articles, university press releases,
    public holidays, or major economic events.
    """
    gnews_api_key = _require_api_key("GNEWS_API_KEY")
    url = "https://gnews.io/api/v4/search"
    params = {
        "query": query,
        "lang": "en",
        "max": 10,
        "sortby": "publishedAt",
        "apikey": gnews_api_key,
    }

    response = requests.get(url, params=params, timeout=25)
    response.raise_for_status()
    payload = response.json()
    articles = payload.get("articles", []) if isinstance(payload, dict) else []

    normalized = [
        {
            "title": row.get("title", ""),
            "description": row.get("description", ""),
            "source": (row.get("source") or {}).get("name", "") if isinstance(row.get("source"), dict) else "",
            "published_at": row.get("publishedAt", ""),
            "url": row.get("url", ""),
        }
        for row in articles
        if isinstance(row, dict)
    ]

    return {"provider": "gnews", "query": query, "results": normalized}


def search_web(query: str) -> Dict[str, Any]:
    """
    search_web(query) [SERPER_API_KEY]
    Use this for general Google Search (competitor promos, reddit chatter,
    local social mentions, unofficial local events).
    """
    serper_api_key = _require_api_key("SERPER_API_KEY")
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": serper_api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": 10, "gl": "my", "hl": "en"}

    response = requests.post(url, headers=headers, json=payload, timeout=25)
    response.raise_for_status()
    body = response.json()
    organic = body.get("organic", []) if isinstance(body, dict) else []

    normalized = [
        {
            "title": row.get("title", ""),
            "snippet": row.get("snippet", ""),
            "source": row.get("source", ""),
            "date": row.get("date", ""),
            "url": row.get("link", ""),
        }
        for row in organic
        if isinstance(row, dict)
    ]

    return {"provider": "serper", "query": query, "results": normalized}


def search_places(location_query: str) -> Dict[str, Any]:
    """
    search_places(location_query) [GOOGLE_PLACES_API_KEY]
    Use this via Google Places Text Search to find nearby competitors,
    permanent closures, and opening-hours context.
    """
    places_api_key = _require_api_key("GOOGLE_PLACES_API_KEY")
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": location_query,
        "key": places_api_key,
    }

    response = requests.get(url, params=params, timeout=25)
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results", []) if isinstance(payload, dict) else []

    normalized = [
        {
            "name": row.get("name", ""),
            "formatted_address": row.get("formatted_address", ""),
            "business_status": row.get("business_status", ""),
            "rating": row.get("rating"),
            "user_ratings_total": row.get("user_ratings_total"),
            "open_now": ((row.get("opening_hours") or {}).get("open_now") if isinstance(row.get("opening_hours"), dict) else None),
        }
        for row in results
        if isinstance(row, dict)
    ]

    return {"provider": "google_places", "query": location_query, "results": normalized}


def get_historical_weather(location: str, date_range: Any) -> Dict[str, Any]:
    """
    get_historical_weather(location, date_range) [OPENWEATHER_API_KEY]
    Uses OpenWeather geocoding + historical timemachine endpoint.
    """
    weather_api_key = _require_api_key("OPENWEATHER_API_KEY")
    start_date, end_date = _normalize_date_range(date_range)

    geocode_url = "https://api.openweathermap.org/geo/1.0/direct"
    geocode_params = {"q": location, "limit": 1, "appid": weather_api_key}
    geo_resp = requests.get(geocode_url, params=geocode_params, timeout=20)
    geo_resp.raise_for_status()
    geo_rows = geo_resp.json()
    if not geo_rows:
        raise ValueError("OpenWeather geocoding returned no location results")

    geo = geo_rows[0]
    lat = float(geo.get("lat"))
    lon = float(geo.get("lon"))

    dt_start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    dt_end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if dt_end < dt_start:
        raise ValueError("date_range end must be on or after start")

    daily_points: List[Dict[str, Any]] = []
    current = dt_start
    while current <= dt_end:
        ts = int(current.replace(hour=12, minute=0, second=0, microsecond=0).timestamp())
        weather_url = "https://api.openweathermap.org/data/3.0/onecall/timemachine"
        params = {
            "lat": lat,
            "lon": lon,
            "dt": ts,
            "appid": weather_api_key,
            "units": "metric",
        }
        response = requests.get(weather_url, params=params, timeout=25)
        response.raise_for_status()
        payload = response.json()

        entries = payload.get("data", []) if isinstance(payload, dict) else []
        if entries:
            temps = [float(x.get("temp", 0.0)) for x in entries if isinstance(x, dict)]
            rain = [float((x.get("rain") or {}).get("1h", 0.0)) for x in entries if isinstance(x, dict)]
            daily_points.append(
                {
                    "date": current.strftime("%Y-%m-%d"),
                    "avg_temp_c": round(sum(temps) / len(temps), 2) if temps else None,
                    "rain_mm": round(sum(rain), 2) if rain else 0.0,
                }
            )

        current += timedelta(days=1)

    avg_temp_values = [p["avg_temp_c"] for p in daily_points if p.get("avg_temp_c") is not None]
    total_rain = round(sum(p.get("rain_mm", 0.0) for p in daily_points), 2)

    return {
        "provider": "openweather",
        "location": f"{geo.get('name', '')}, {geo.get('country', '')}",
        "date_range": {"start": start_date, "end": end_date},
        "summary": {
            "days_sampled": len(daily_points),
            "avg_temp_c": round(sum(avg_temp_values) / len(avg_temp_values), 2) if avg_temp_values else None,
            "total_rain_mm": total_rain,
        },
        "daily": daily_points,
    }


def get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY environment variables"
        )

    return create_client(supabase_url, supabase_key)


def _month_bounds(month_str: str) -> Tuple[str, str]:
    start_dt = datetime.strptime(month_str, "%Y-%m").replace(tzinfo=timezone.utc)
    if start_dt.month == 12:
        end_dt = start_dt.replace(year=start_dt.year + 1, month=1)
    else:
        end_dt = start_dt.replace(month=start_dt.month + 1)
    return start_dt.isoformat(), end_dt.isoformat()


def _safe_pct_change(baseline: float, target: float) -> Optional[float]:
    if baseline == 0:
        if target == 0:
            return 0.0
        return None
    return round(((target - baseline) / baseline) * 100.0, 2)


def _fetch_sales_logs_month(supabase: Client, merchant_id: str, month_str: str) -> pd.DataFrame:
    start_iso, end_iso = _month_bounds(month_str)

    response = (
        supabase.table("sales_logs")
        .select("id, merchant_id, order_id, item_name, quantity, price, logged_at")
        .eq("merchant_id", merchant_id)
        .gte("logged_at", start_iso)
        .lt("logged_at", end_iso)
        .limit(50000)
        .execute()
    )

    rows: List[Dict[str, Any]] = response.data or []

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["logged_at"] = pd.to_datetime(df["logged_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["logged_at"]).copy()
    if df.empty:
        return df

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
    df["item_name"] = df["item_name"].fillna("UNKNOWN_ITEM").astype(str)

    df["order_id"] = df["order_id"].fillna("").astype(str).str.strip()
    df["effective_order_id"] = df["order_id"]
    no_order_mask = df["effective_order_id"] == ""
    df.loc[no_order_mask, "effective_order_id"] = "NO_ORDER_" + df.loc[no_order_mask, "id"].astype(str)

    df["revenue"] = df["quantity"] * df["price"]

    return df


def _compute_core_metrics(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {
            "unique_orders": 0.0,
            "total_revenue": 0.0,
            "total_quantity": 0.0,
            "aov": 0.0,
            "upt": 0.0,
            "multi_item_order_rate": 0.0,
        }

    unique_orders = float(df["effective_order_id"].nunique())
    total_revenue = float(df["revenue"].sum())
    total_quantity = float(df["quantity"].sum())

    aov = (total_revenue / unique_orders) if unique_orders else 0.0
    upt = (total_quantity / unique_orders) if unique_orders else 0.0

    order_units = df.groupby("effective_order_id")["quantity"].sum()
    multi_item_orders = float((order_units > 1).sum())
    multi_item_order_rate = (multi_item_orders / unique_orders) if unique_orders else 0.0

    return {
        "unique_orders": round(unique_orders, 2),
        "total_revenue": round(total_revenue, 2),
        "total_quantity": round(total_quantity, 2),
        "aov": round(aov, 2),
        "upt": round(upt, 2),
        "multi_item_order_rate": round(multi_item_order_rate, 4),
    }


def _time_of_day_revenue(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {"Morning": 0.0, "Lunch": 0.0, "Afternoon": 0.0, "Evening": 0.0}

    out = {
        "Morning": float(df.loc[(df["hour"] >= 6) & (df["hour"] < 11), "revenue"].sum()),
        "Lunch": float(df.loc[(df["hour"] >= 11) & (df["hour"] < 14), "revenue"].sum()),
        "Afternoon": float(df.loc[(df["hour"] >= 14) & (df["hour"] < 18), "revenue"].sum()),
        "Evening": float(df.loc[(df["hour"] >= 18) & (df["hour"] < 24), "revenue"].sum()),
    }
    return {k: round(v, 2) for k, v in out.items()}


def _day_type_revenue(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {"Weekdays": 0.0, "Weekends": 0.0}

    weekdays = float(df.loc[~df["is_weekend"], "revenue"].sum())
    weekends = float(df.loc[df["is_weekend"], "revenue"].sum())
    return {"Weekdays": round(weekdays, 2), "Weekends": round(weekends, 2)}


def _peak_order_hour(df: pd.DataFrame) -> Optional[int]:
    if df.empty:
        return None

    dedup_orders = df[["effective_order_id", "hour"]].drop_duplicates(subset=["effective_order_id"])
    if dedup_orders.empty:
        return None

    hour_counts = dedup_orders["hour"].value_counts().sort_values(ascending=False)
    if hour_counts.empty:
        return None

    return int(hour_counts.index[0])


def _product_views(df_baseline: pd.DataFrame, df_target: pd.DataFrame) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[str], List[str]]:
    baseline = (
        df_baseline.groupby("item_name", as_index=False)
        .agg(baseline_revenue=("revenue", "sum"), baseline_qty=("quantity", "sum"))
        if not df_baseline.empty
        else pd.DataFrame(columns=["item_name", "baseline_revenue", "baseline_qty"])
    )

    target = (
        df_target.groupby("item_name", as_index=False)
        .agg(target_revenue=("revenue", "sum"), target_qty=("quantity", "sum"))
        if not df_target.empty
        else pd.DataFrame(columns=["item_name", "target_revenue", "target_qty"])
    )

    merged = baseline.merge(target, on="item_name", how="outer").fillna(0)
    if merged.empty:
        return [], [], [], [], []

    merged["baseline_revenue"] = pd.to_numeric(merged["baseline_revenue"], errors="coerce").fillna(0.0)
    merged["target_revenue"] = pd.to_numeric(merged["target_revenue"], errors="coerce").fillna(0.0)
    merged["baseline_qty"] = pd.to_numeric(merged["baseline_qty"], errors="coerce").fillna(0.0)
    merged["target_qty"] = pd.to_numeric(merged["target_qty"], errors="coerce").fillna(0.0)

    merged["combined_qty"] = merged["baseline_qty"] + merged["target_qty"]

    # Filter out products with fewer than 5 total unit sales across both months.
    movers_pool = merged[merged["combined_qty"] >= 5].copy()

    movers_pool = movers_pool[
        (movers_pool["baseline_revenue"] > 0) & (movers_pool["target_revenue"] > 0)
    ].copy()

    if movers_pool.empty:
        top_5_risers: List[Dict[str, Any]] = []
        top_5_fallers: List[Dict[str, Any]] = []
    else:
        movers_pool["revenue_growth_pct"] = (
            (movers_pool["target_revenue"] - movers_pool["baseline_revenue"]) / movers_pool["baseline_revenue"]
        ) * 100.0

        risers_df = movers_pool[movers_pool["revenue_growth_pct"] > 0].sort_values(
            "revenue_growth_pct", ascending=False
        )
        fallers_df = movers_pool[movers_pool["revenue_growth_pct"] < 0].sort_values(
            "revenue_growth_pct", ascending=True
        )

        top_5_risers = [
            {
                "item_name": row["item_name"],
                "baseline_revenue": round(float(row["baseline_revenue"]), 2),
                "target_revenue": round(float(row["target_revenue"]), 2),
                "growth_pct": round(float(row["revenue_growth_pct"]), 2),
            }
            for _, row in risers_df.head(5).iterrows()
        ]

        top_5_fallers = [
            {
                "item_name": row["item_name"],
                "baseline_revenue": round(float(row["baseline_revenue"]), 2),
                "target_revenue": round(float(row["target_revenue"]), 2),
                "growth_pct": round(float(row["revenue_growth_pct"]), 2),
            }
            for _, row in fallers_df.head(5).iterrows()
        ]

    anchors_pool = merged[merged["target_qty"] >= 5].copy()
    anchors_pool = anchors_pool.sort_values("target_revenue", ascending=False)
    top_3_anchors = [
        {
            "item_name": row["item_name"],
            "target_revenue": round(float(row["target_revenue"]), 2),
        }
        for _, row in anchors_pool.head(3).iterrows()
    ]

    ghosts_df = merged[(merged["baseline_qty"] > 5) & (merged["target_qty"] == 0)]
    new_arrivals_df = merged[(merged["baseline_qty"] == 0) & (merged["target_qty"] > 0)]

    ghost_items = ghosts_df.sort_values("baseline_qty", ascending=False)["item_name"].tolist()
    new_arrivals = new_arrivals_df.sort_values("target_qty", ascending=False)["item_name"].tolist()

    return top_5_risers, top_5_fallers, top_3_anchors, ghost_items, new_arrivals


def analyze_sales_patterns(merchant_id: str, baseline_month: str, target_month: str) -> Dict[str, Any]:
    """
    Analyze two months of sales logs and persist diagnostics into monthly_summaries.diagnostic_patterns.

    Args:
        merchant_id: UUID of the merchant.
        baseline_month: Month in YYYY-MM format used as baseline.
        target_month: Month in YYYY-MM format used as target.

    Returns:
        Dictionary containing omni-pattern diagnostics.
    """
    supabase = get_supabase_client()

    baseline_df = _fetch_sales_logs_month(supabase, merchant_id, baseline_month)
    target_df = _fetch_sales_logs_month(supabase, merchant_id, target_month)

    # Convert to Malaysian timezone before extracting temporal features.
    if not baseline_df.empty:
        baseline_df["logged_at"] = pd.to_datetime(baseline_df["logged_at"]).dt.tz_convert("Asia/Kuala_Lumpur")
        baseline_df["hour"] = baseline_df["logged_at"].dt.hour
        baseline_df["is_weekend"] = baseline_df["logged_at"].dt.dayofweek >= 5

    if not target_df.empty:
        target_df["logged_at"] = pd.to_datetime(target_df["logged_at"]).dt.tz_convert("Asia/Kuala_Lumpur")
        target_df["hour"] = target_df["logged_at"].dt.hour
        target_df["is_weekend"] = target_df["logged_at"].dt.dayofweek >= 5

    baseline_core = _compute_core_metrics(baseline_df)
    target_core = _compute_core_metrics(target_df)

    baseline_tod = _time_of_day_revenue(baseline_df)
    target_tod = _time_of_day_revenue(target_df)

    baseline_daytype = _day_type_revenue(baseline_df)
    target_daytype = _day_type_revenue(target_df)

    top_5_risers, top_5_fallers, top_3_anchors, ghost_items, new_arrivals = _product_views(
        baseline_df, target_df
    )

    final_omni_json_dict: Dict[str, Any] = {
        "merchant_id": merchant_id,
        "baseline_month": baseline_month,
        "target_month": target_month,
        "order_volume_shift": _safe_pct_change(
            baseline_core["unique_orders"], target_core["unique_orders"]
        ),
        "aov_shift": _safe_pct_change(baseline_core["aov"], target_core["aov"]),
        "upt_shift": _safe_pct_change(baseline_core["upt"], target_core["upt"]),
        "multi_item_order_rate_shift": _safe_pct_change(
            baseline_core["multi_item_order_rate"], target_core["multi_item_order_rate"]
        ),
        "time_of_day_shifts": {
            segment: _safe_pct_change(baseline_tod[segment], target_tod[segment])
            for segment in ["Morning", "Lunch", "Afternoon", "Evening"]
        },
        "day_of_week_shifts": {
            "Weekdays": _safe_pct_change(baseline_daytype["Weekdays"], target_daytype["Weekdays"]),
            "Weekends": _safe_pct_change(baseline_daytype["Weekends"], target_daytype["Weekends"]),
        },
        "peak_hour_baseline": _peak_order_hour(baseline_df),
        "peak_hour_target": _peak_order_hour(target_df),
        "top_5_risers": top_5_risers,
        "top_5_fallers": top_5_fallers,
        "top_3_anchors": top_3_anchors,
        "ghost_items": ghost_items,
        "new_arrivals": new_arrivals,
    }

    (
        supabase.table("monthly_summaries")
        .update({"diagnostic_patterns": final_omni_json_dict})
        .eq("merchant_id", merchant_id)
        .eq("report_month", target_month)
        .execute()
    )

    return final_omni_json_dict


if __name__ == "__main__":
    # Replace with your real merchant UUID before running.
    TEST_MERCHANT_ID = "af065e86-3643-4ef6-8a37-eaff5258f82b"
    BASELINE_MONTH = "2026-03"
    TARGET_MONTH = "2026-04"

    result = analyze_sales_patterns(
        merchant_id=TEST_MERCHANT_ID,
        baseline_month=BASELINE_MONTH,
        target_month=TARGET_MONTH,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))