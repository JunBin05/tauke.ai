import os
import csv
import io
import requests
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional, List, Dict, Any 
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client
from fastapi import BackgroundTasks
from pydantic import BaseModel

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Specifically allow your React frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# connect Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

class SignupRequest(BaseModel):
    email: str
    password: str
    name: str          
    shop_type: str     

class LoginRequest(BaseModel):
    email: str
    password: str
    
class GoogleSyncRequest(BaseModel):
    access_token: str  # The token the frontend receives from Google login
    name: str          
    shop_type: str     

class LocationUpdateRequest(BaseModel):
    merchant_id: str
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    place_id: Optional[str] = None

def check_and_notify_costs(merchant_id: str):
    now = datetime.now()
    current_year, current_month = now.year, now.month
    
    
    try:
        response = supabase.table("monthly_overheads") \
            .select("*") \
            .eq("merchant_id", merchant_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
            
        records = response.data
        needs_update = True
        
        if len(records) > 0:
            last_record = records[0]
            last_date = datetime.fromisoformat(last_record["created_at"].split(".")[0])
            if last_date.year == current_year and last_date.month == current_month:
                needs_update = False
                
        if needs_update:
            print(f"⚠️ [Background Task] Merchant {merchant_id} hasn't updated costs for {current_month}!")
            print(f"🔔 [Simulated Notification] Sent to Boss: Please update this month's rent and utilities!")
        else:
            print(f"✅ [Background Task] Merchant {merchant_id}'s costs are up to date.")
    except Exception as e:
        print(f"Background task error: {e}")


@app.get("/")
def read_root():
    return {"message": "MicroEdge Backend 运行中!"}

@app.post("/auth/signup")
async def signup(req: SignupRequest): # <--- REMOVED extra string params
    try:
        auth_response = supabase.auth.sign_up({
            "email": req.email,
            "password": req.password
        })
        
        if auth_response.user:
            user_id = auth_response.user.id
            merchant_data = {
                "owner_id": user_id,
                "name": req.name,
                "type": req.shop_type
            }
            supabase.table("merchants").insert(merchant_data).execute()
            return {"status": "success", "owner_id": user_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# --- 2. Login Endpoint ---
@app.post("/auth/login")
async def login(req: LoginRequest):
    try:
        # Supabase automatically verifies the password
        response = supabase.auth.sign_in_with_password({
            "email": req.email, 
            "password": req.password
        })
        
        return {
            "status": "success",
            "message": "Login successful!",
            "access_token": response.session.access_token, # Token to keep frontend logged in
            "owner_id": response.user.id                   # The unified ID for your database
        }
    except Exception as e:
        return {"status": "error", "message": f"Login failed: {e}"}

# feature: save the AI analysis cost 
@app.post("/add-ingredient")
async def add_ingredient(name: str, price: float, m_id: str):
    data = {"merchant_id": m_id, "item_name": name, "price_per_unit": price}
    response = supabase.table("ingredient_costs").insert(data).execute()
    return {"status": "success", "data": response.data}

# --- 3. Google Profile Sync Endpoint ---
@app.post("/auth/sync-google-profile")
async def sync_google_profile(req: GoogleSyncRequest):
    try:
        # 1. Verify the access token from the frontend to ensure it's legit
        user_response = supabase.auth.get_user(req.access_token)
        if not user_response.user:
            return {"status": "error", "message": "Invalid access token"}

        user_id = user_response.user.id
        
        # 2. Check if this Google user already has a shop in the merchants table
        existing_shop = supabase.table("merchants").select("*").eq("owner_id", user_id).execute()
        
        # If the shop exists, just welcome them back
        if existing_shop.data:
            return {
                "status": "success", 
                "message": "Welcome back, Google user!", 
                "owner_id": user_id
            }

        # 3. If it's a brand new Google user, create a new shop profile for them
        merchant_data = {
            "owner_id": user_id,
            "name": req.name,
            "type": req.shop_type
        }
        supabase.table("merchants").insert(merchant_data).execute()
        
        return {
            "status": "success", 
            "message": "Google profile linked! Shop created.", 
            "owner_id": user_id
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Google sync failed: {e}"}

@app.post("/add-menu-item")
async def add_menu_item(merchant_id: str, item_name: str, original_price: float):

    data = {
        "merchant_id": merchant_id,
        "item_name": item_name,
        "original_price": original_price,
        "is_active": True 
    }
    
    try:
        response = supabase.table("menu_items").insert(data).execute()
        return {
            "status": "success", 
            "message": f"Successfully added dish: {item_name} (RM {original_price})", 
            "data": response.data
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/upload-sales-logs-csv")
async def upload_sales_logs_csv(merchant_id: str = Form(...), file: UploadFile = File(...)):
    if not merchant_id.strip():
        raise HTTPException(status_code=400, detail="merchant_id is required")

    if not file.filename:
        raise HTTPException(status_code=400, detail="CSV file is required")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        csv_text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(csv_text))
    required_columns = ["order_id", "date", "time", "item_name", "quantity", "unit_price"]

    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV header row is missing")

    normalized_headers = [h.strip() if isinstance(h, str) else h for h in reader.fieldnames]
    missing_columns = [col for col in required_columns if col not in normalized_headers]
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required CSV columns: {', '.join(missing_columns)}",
        )

    valid_rows = []
    invalid_rows = []
    seen_in_file = set()
    duplicate_in_file_count = 0

    for row_index, row in enumerate(reader, start=2):
        row = {(k.strip() if isinstance(k, str) else k): v for k, v in row.items()}

        if not any((value or "").strip() for value in row.values() if isinstance(value, str)):
            continue

        try:
            order_id_raw = (row.get("order_id") or "").strip()
            order_id = order_id_raw if order_id_raw else None

            date_raw = (row.get("date") or "").strip()
            log_date = datetime.strptime(date_raw, "%d/%m/%Y").date().isoformat()

            time_raw = (row.get("time") or "").strip()
            try:
                log_time = datetime.strptime(time_raw, "%H:%M").time().strftime("%H:%M:%S")
            except ValueError:
                log_time = datetime.strptime(time_raw, "%H:%M:%S").time().strftime("%H:%M:%S")

            item_name = (row.get("item_name") or "").strip()
            if not item_name:
                raise ValueError("item_name is required")

            quantity_raw = (row.get("quantity") or "").strip()
            quantity = int(quantity_raw)
            if quantity < 0:
                raise ValueError("quantity must be >= 0")

            unit_price_raw = (row.get("unit_price") or "").strip()
            unit_price = Decimal(unit_price_raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            dedupe_key = (
                merchant_id,
                order_id or "",
                log_date,
                log_time,
                item_name,
                quantity,
                str(unit_price),
            )
            if dedupe_key in seen_in_file:
                duplicate_in_file_count += 1
                continue
            seen_in_file.add(dedupe_key)

            valid_rows.append(
                {
                    "merchant_id": merchant_id,
                    "order_id": order_id,
                    "log_date": log_date,
                    "log_time": log_time,
                    "item_name": item_name,
                    "quantity": quantity,
                    "unit_price": float(unit_price),
                }
            )

        except (ValueError, InvalidOperation) as exc:
            invalid_rows.append({"line": row_index, "reason": str(exc)})

    if not valid_rows:
        return {
            "success": False,
            "message": "No valid rows to insert",
            "inserted_rows": 0,
            "invalid_rows": len(invalid_rows),
            "duplicate_rows_in_file": duplicate_in_file_count,
            "errors": invalid_rows[:20],
        }

    min_date = min(r["log_date"] for r in valid_rows)
    max_date = max(r["log_date"] for r in valid_rows)

    existing_result = (
        supabase.table("sales_logs")
        .select("order_id, log_date, log_time, item_name, quantity, unit_price")
        .eq("merchant_id", merchant_id)
        .gte("log_date", min_date)
        .lte("log_date", max_date)
        .execute()
    )
    existing_rows = existing_result.data or []

    existing_keys = set()
    for existing in existing_rows:
        existing_keys.add(
            (
                merchant_id,
                (existing.get("order_id") or ""),
                str(existing.get("log_date") or ""),
                str(existing.get("log_time") or ""),
                str(existing.get("item_name") or ""),
                int(existing.get("quantity") or 0),
                str(Decimal(str(existing.get("unit_price") or 0)).quantize(Decimal("0.01"))),
            )
        )

    rows_to_insert = []
    duplicate_existing_count = 0
    for row in valid_rows:
        row_key = (
            merchant_id,
            row.get("order_id") or "",
            row["log_date"],
            row["log_time"],
            row["item_name"],
            int(row["quantity"]),
            str(Decimal(str(row["unit_price"])).quantize(Decimal("0.01"))),
        )
        if row_key in existing_keys:
            duplicate_existing_count += 1
            continue
        rows_to_insert.append(row)

    inserted_rows = 0
    if rows_to_insert:
        batch_size = 500
        for start in range(0, len(rows_to_insert), batch_size):
            batch = rows_to_insert[start : start + batch_size]
            supabase.table("sales_logs").insert(batch).execute()
            inserted_rows += len(batch)

    return {
        "success": True,
        "message": "CSV processed",
        "total_rows_read": len(valid_rows) + len(invalid_rows) + duplicate_in_file_count,
        "valid_rows": len(valid_rows),
        "inserted_rows": inserted_rows,
        "duplicate_rows_in_file": duplicate_in_file_count,
        "duplicate_rows_existing": duplicate_existing_count,
        "invalid_rows": len(invalid_rows),
        "errors": invalid_rows[:20],
    }


@app.get("/analyze-surroundings/{merchant_id}")
async def analyze_surroundings(merchant_id: str, lat: float, lon: float):

    # It uses the latitude and longitude to find schools within a 500m radius.
    schools = get_nearby_schools(lat, lon)

    # 2. Logic to generate a summary message
    # We check if the 'schools' list contains any data.
    if schools:
        # If schools are found, we create a friendly message for the merchant.
        # It mentions how many were found and the name of the closest one.
        message = f"Found {len(schools)} schools nearby: {schools[0]['name']} etc."
    else:
        # If the list is empty, we inform the merchant that no major schools were detected.
        message = "No major schools found nearby."

    # 3. The Response
    # This returns a JSON object back to the requester (the mobile app or the AI agent).
    # It includes the specific ID, the raw data, and our generated summary note.
    return {"merchant_id": merchant_id, "school_context": schools, "note": message}
    
@app.post("/merchants/update-location")
async def update_location(req: LocationUpdateRequest):
    try:
        final_lat, final_lon = req.lat, req.lon
        final_address = req.address

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

        # Save to Supabase
        update_data = {
            "address": final_address,
            "latitude": final_lat,
            "longitude": final_lon
        }
        
        supabase.table("merchants").update(update_data).eq("owner_id", req.merchant_id).execute()

        return {
            "status": "success",
            "message": "Shop location updated!",
            "updated_data": update_data
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
def analyze_sales_trends(merchant_id: str) -> list:
    # 1. Fetch raw data from Supabase (fetching last 7 days for this Hackathon demo)
    response = supabase.table("sales_logs") \
        .select("quantity_sold, log_date, menu_items(item_name)") \
        .eq("merchant_id", merchant_id) \
        .order("log_date", desc=True) \
        .execute()
    
    raw_data = response.data
    
    if not raw_data:
        return ["No data available for analysis."]

    # 2. Flatten the data for Pandas DataFrame
    # Supabase returns nested JSON, we need to extract 'item_name' cleanly
    flat_data = []
    for row in raw_data:
        flat_data.append({
            "date": row["log_date"],
            "item_name": row["menu_items"]["item_name"],
            "quantity": row["quantity_sold"]
        })

    # 3. Load data into a Pandas DataFrame and convert string dates to Datetime objects
    df = pd.DataFrame(flat_data)
    df['date'] = pd.to_datetime(df['date'])

    # 4. Define Time Periods
    # For this Hackathon demo (since we only seeded 7 days of data), 
    # we will compare "Recent 3 Days" vs "Previous 3 Days".
    # Note: In production, change 'days=3' to 'days=7' for WoW (Week-over-Week) 
    # or 'days=30' for MoM (Month-over-Month).
    today = datetime.now()
    period_end = today
    period_mid = today - timedelta(days=3)
    period_start = today - timedelta(days=6)

    # 5. Split DataFrame into two timeframes
    recent_df = df[(df['date'] > period_mid) & (df['date'] <= period_end)]
    previous_df = df[(df['date'] > period_start) & (df['date'] <= period_mid)]

    # 6. Group by item_name and sum the quantities
    recent_agg = recent_df.groupby('item_name')['quantity'].sum()
    previous_agg = previous_df.groupby('item_name')['quantity'].sum()

    # 7. Calculate Percentage Change and generate AI insights
    insights = []
    for item in recent_agg.index:
        recent_qty = recent_agg[item]
        prev_qty = previous_agg.get(item, 0) # Use 0 if item wasn't sold previously
        
        if prev_qty > 0:
            # Formula: ((New - Old) / Old) * 100
            change_pct = ((recent_qty - prev_qty) / prev_qty) * 100
            
            # 8. Filter for significant changes (e.g., more than 20% drop or spike)
            if change_pct <= -20:
                insights.append(f"CRITICAL DROP: {item} sales dropped by {abs(change_pct):.0f}% compared to the previous period.")
            elif change_pct >= 20:
                insights.append(f"SPIKE: {item} sales increased by {change_pct:.0f}%. Keep it up!")

    # If everything is stable (between -20% and 20%)
    if not insights:
        return ["All sales are relatively stable. No drastic fluctuations detected."]
    
    return insights

# --- AI Generate Interrogation ---
@app.post("/generate-ai-interrogation/{merchant_id}")
async def generate_interrogation(merchant_id: str, context_package: dict):
# Here we will pass the large JSON (context_package) we just saw in Swagger to Z.AI
# Let Z.AI ask a profound question based on the contradiction of high foot traffic, good weather, but poor sales
# Pseudocode approach:
# prompt = f"Context: {context_package}. Found the contradiction and asked the boss."
# Temporarily store it in the database so the frontend can retrieve this Pending question.
    question = "I noticed high foot traffic but low sales. Did you change your menu prices recently?" 
    
    data = {
        "merchant_id": merchant_id,
        "question": question,
        "status": "pending"
    }
    supabase.table("ai_interrogations").insert(data).execute()
    return {"status": "success", "ai_question": question}

@app.get("/get-ai-decision-package/{merchant_id}")
async def get_package(merchant_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(check_and_notify_costs, merchant_id)
    
    # 1. Fetch location from DB
    res = supabase.table("merchants").select("*").eq("owner_id", merchant_id).execute()
    
    if not res.data:
        return {"status": "error", "message": "Merchant not found"}
        
    m_data = res.data[0]
    lat = m_data.get("latitude")
    lon = m_data.get("longitude")
    address = m_data.get("address", "Unknown")

    if not lat or not lon:
        return {"status": "error", "message": "Please update your shop location first!"}

    # Gather data using your helper functions
    weather = get_weather_context(lat, lon)
    traffic = get_traffic_context(lat, lon)
    foot_traffic = get_foot_traffic_context(lat, lon) 
    
    return {
        "merchant_id": merchant_id,
        "location": address,
        "environmental_context": {
            "weather": weather,
            "traffic": traffic,
            "foot_traffic": foot_traffic
        }
    }

# AI Interrogation Endpoints 

# 1. AI uses this to post a question to the Boss
@app.post("/add-interrogation")
async def add_interrogation(merchant_id: str, question: str):
    data = {
        "merchant_id": merchant_id,
        "question": question,
        "status": "pending"
    }
    try:
        response = supabase.table("ai_interrogations").insert(data).execute()
        return {"status": "success", "data": response.data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 2. Boss (via Frontend) uses this to submit an answer
@app.patch("/submit-answer/{interrogation_id}")
async def submit_answer(interrogation_id: str, answer: str):
    try:
        # Update the specific interrogation with the answer and change status
        response = supabase.table("ai_interrogations") \
            .update({"user_answer": answer, "status": "answered"}) \
            .eq("id", interrogation_id) \
            .execute()
        return {"status": "success", "message": "Answer saved!", "data": response.data}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Strategy & Bubble Endpoints 

# 3. AI uses this to generate the 3 Strategy Bubbles
@app.post("/create-strategy-proposals")
async def create_proposals(merchant_id: str, proposals: list):
    # 'proposals' should be a list of dicts like: 
    # [{"bubble_type": "Aggressive", "ai_logic": "..."}, ...]
    for p in proposals:
        p["merchant_id"] = merchant_id
    
    try:
        response = supabase.table("strategy_proposals").insert(proposals).execute()
        return {"status": "success", "data": response.data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 4. Boss selects one Bubble to trigger Swarm Debate
@app.patch("/select-strategy/{proposal_id}")
async def select_strategy(proposal_id: str):
    try:
        # Step A: Reset all choices for this merchant (optional, but cleaner)
        # Step B: Mark the selected bubble as user_choice = True
        response = supabase.table("strategy_proposals") \
            .update({"user_choice": True}) \
            .eq("id", proposal_id) \
            .execute()
        
        # NOTE: After this, you can trigger the Swarm AI agent logic
        return {"status": "success", "message": "Strategy selected. Swarm Debate starting!", "data": response.data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/debate/save-proposals")
async def save_proposals(merchant_id: str, proposals: List[Dict[str, Any]]):
    # proposals must be a list of dicts with keys: perspective, risk, logic, is_most_preferred (boolean)
    # [
    #   {"perspective": "Challenger", "risk": "High", "logic": "...", "is_most_preferred": True},
    #   {"perspective": "Conservative", "risk": "Low", "logic": "..."},
    #   {"perspective": "Human", "risk": "Medium", "logic": "..."}
    # ]
    try:
        # save in database for record-keeping and future analysis
        supabase.table("strategy_proposals").insert(proposals).execute()
        return {"status": "success", "message": "Debate results stored."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
@app.get("/debate/get-proposals/{merchant_id}")
async def get_proposals(merchant_id: str):
    # pass the risk levels and logic of each perspective to the frontend for display in the UI
    res = supabase.table("strategy_proposals") \
        .select("*") \
        .eq("merchant_id", merchant_id) \
        .order("risk_level") \
        .execute()
    return {"status": "success", "data": res.data}

# Places API (New)
def get_nearby_schools(lat, lon, radius=500):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    url = "https://places.googleapis.com/v1/places:searchNearby"
    
    # Google requires a FieldMask to specify which data fields to return
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.types"
    }

    # Define the search criteria
    payload = {
        "includedTypes": ["school"], # Filter results to only include schools
        "maxResultCount": 5,        # Limit to the nearest 5 locations
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": radius # Search radius in meters
            }
        }
    }

    try:
        # Send the POST request to Google's server
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        # Extract specific details from the JSON response
        schools = []
        if "places" in data:
            for place in data["places"]:
                schools.append({
                    "name": place["displayName"]["text"],
                    "address": place.get("formattedAddress", "No address")
                })
        return schools
    except Exception as e:
        print(f"Places API Error: {e}")
        return []

#use Geocoding API
#This is the foundation of all the functions. Cannot just give the AI ​​"Jalan University"; you need to convert it to latitude and longitude (lat/lon) so that can access the functions for weather, traffic conditions, and searching for schools.
def get_coordinates(address):
    # Use your Google Maps API Key
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
    
    try:
        response = requests.get(url)
        data = response.json()
        if data["status"] == "OK":
            # Extract latitude and longitude
            location = data["results"][0]["geometry"]["location"]
            return location["lat"], location["lng"]
        return None, None
    except Exception as e:
        print(f"Geocoding Error: {e}")
        return None, None
    
    # Turns coordinates back into a human-readable address
def reverse_geocode(lat: float, lon: float):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={api_key}"
    
    try:
        response = requests.get(url).json()
        if response["status"] == "OK":
            # Returns the most formatted address (e.g., the full street address)
            return response["results"][0]["formatted_address"]
        return "Unknown Location"
    except Exception as e:
        return f"Error: {e}"
    
def get_details_from_place_id(place_id: str):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&key={api_key}"
    response = requests.get(url).json()
    if response["status"] == "OK":
        location = response["result"]["geometry"]["location"]
        return location["lat"], location["lng"]
    return None, None

#use Routes API for detect road situations
#By comparing "normal time" and "traffic prediction time," AI can determine whether current road conditions are severely impacting business.
def get_traffic_context(origin_lat, origin_lon):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        # Requesting duration with and without traffic for comparison
        "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.condition"
    }
    
    # We simulate a short trip to measure local traffic density
    payload = {
        "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lon}}},
        "destination": {"location": {"latLng": {"latitude": origin_lat + 0.01, "longitude": origin_lon + 0.01}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE" # This is key for real-time traffic
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        # Logic: If duration > staticDuration, it means there is traffic
        duration = int(data["routes"][0]["duration"][:-1]) # Remove 's'
        static_duration = int(data["routes"][0]["staticDuration"][:-1])
        
        delay = duration - static_duration
        status = "Heavy Traffic" if delay > 300 else "Clear" # More than 5 mins delay
        
        return {"status": status, "delay_seconds": delay}
    except:
        return {"status": "Normal", "delay_seconds": 0}
    
# Foot Traffic API Integration 
def get_foot_traffic_context(lat: float, lon: float):
    """
    Fetches foot traffic data using BestTime.py (or a similar provider).
    This tells the AI if the area is currently 'Busy', 'Normal', or 'Quiet'.
    """
    api_key = os.getenv("BESTTIME_API_KEY") # You will need to add this to .env
    
    # If you don't have an API key yet, we'll return a 'Simulation' for the Hackathon
    if not api_key:
        print("⚠️ BestTime API Key missing. Returning simulated foot traffic data.")
        return {
            "status": "Busy",
            "live_intensity": 85,  # Percentage of peak busyness
            "note": "Simulated: High foot traffic due to nearby lunch crowd."
        }

    url = "https://besttime.app/api/v1/forecasts/now"
    params = {
        "api_key_private": api_key,
        "lat": lat,
        "lng": lon
    }

    try:
        # Note: BestTime usually requires a specific venue/address to be accurate
        # Here we simulate the query based on the merchant's coordinates
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get("status") == "OK":
            analysis = data.get("analysis", {})
            return {
                "status": analysis.get("venue_forecast_status", "Normal"),
                "live_intensity": analysis.get("venue_live_busyness", 50),
                "note": "Live data from BestTime API."
            }
        return {"status": "Normal", "live_intensity": 50, "note": "API call failed, defaulted to Normal."}
    except Exception as e:
        print(f"Foot Traffic API Error: {e}")
        return {"status": "Unknown", "live_intensity": 0, "note": "Connection error."}

# use Maps Grounding Lite for detect day festivals
def get_event_grounding(merchant_location, user_query):
    # Your friend (AI Engineer) will use this data to ground the GLM [cite: 39]
    # You provide the context; the model queries the Map database
    grounding_prompt = f"Based on the location {merchant_location}, are there any festivals or road closures like 'Pasar Ramadhan' today?"
    
    # The Backend passes this intent to the AI Module
    return {"instruction": "Query Google Maps for local events", "location": merchant_location}

#OpenWeather API for see weather use google geocoding API to get place and then this API will detect the weather
def get_weather_context(lat, lon):
    # Fetch the API key from environment variables
    api_key = os.getenv("OPENWEATHER_API_KEY")
    
    # Construct the API URL (units=metric ensures Celsius)
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    
    try:
        # Send a GET request to OpenWeatherMap
        response = requests.get(url)
        data = response.json()
        
        # Check if the request was successful (HTTP 200)
        if response.status_code == 200:
            # Extract key weather information for the AI agent
            weather_data = {
                "main_condition": data['weather'][0]['main'], # e.g., 'Rain', 'Clouds', 'Clear'
                "description": data['weather'][0]['description'], # e.g., 'moderate rain'
                "temperature": data['main']['temp'], # Temperature in Celsius
                "humidity": data['main']['humidity'] # Humidity percentage
            }
            return weather_data
        else:
            print(f"Weather API Error: {data.get('message')}")
            return None
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

#  API 1: GNews API for Market Context 
def get_market_news(query: str = "University of Malaya"):
    # Fetch the API key from .env
    api_key = os.getenv("GNEWS_API_KEY")
    if not api_key:
        return ["GNews API key missing. Please add to .env"]
        
    # Endpoint to search for news in Malaysia (country=my), max 3 articles
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country=my&max=3&apikey={api_key}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if "articles" in data:
            # Extract the top 3 news titles and descriptions
            news_list = []
            for article in data["articles"]:
                # Combine title and description for the AI to read
                news_list.append(f"Headline: {article['title']} - Summary: {article['description']}")
            return news_list
        return ["No significant local news found."]
    except Exception as e:
        print(f"GNews API Error: {e}")
        return ["Failed to fetch market news due to connection error."]


# API 2: Serper Dev API for Competitor Intelligence 
def get_competitor_prices(location: str):
    # Fetch the API key from .env
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return ["Serper API key missing. Please add to .env"]
        
    url = "https://google.serper.dev/search"
    
    # Crafting a specific query to find cafe prices or promos near the location
    search_query = f"cafe menu prices OR coffee promotion near {location} Malaysia"
    
    # Payload for the Google Search, 'gl': 'my' forces Malaysia search results
    payload = {
        "q": search_query, 
        "gl": "my" 
    }
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    
    try:
        # Note: Serper uses POST request, unlike OpenWeather
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        snippets = []
        if "organic" in data:
            # Get the text snippets from the top 3 Google search results
            for item in data["organic"][:3]:
                snippets.append(item.get("snippet", ""))
        return snippets if snippets else ["No recent competitor pricing found."]
    except Exception as e:
        print(f"Serper API Error: {e}")
        return ["Failed to fetch competitor data."]
    
# --- State Machine Control Console: Informs the front-end about the current stage ---
@app.get("/get-merchant-state/{merchant_id}")
async def get_merchant_state(merchant_id: str):
    try:
        # 1. Phase 3: Check for pending AI interrogation
        interrogation_res = supabase.table("ai_interrogations") \
            .select("*") \
            .eq("merchant_id", merchant_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
            
        latest_interrogation = interrogation_res.data[0] if interrogation_res.data else None
        if latest_interrogation and latest_interrogation["status"] == "pending":
            return {
                "current_phase": "PHASE_3_INTERROGATION",
                "message": "AI has a question for the Boss.",
                "data": latest_interrogation
            }

        # 2. Phase 5: Check if the boss has ALREADY selected a strategy
        selected_res = supabase.table("strategy_proposals") \
            .select("*") \
            .eq("merchant_id", merchant_id) \
            .eq("user_choice", True) \
            .limit(1) \
            .execute()
            
        if selected_res.data:
            return {
                "current_phase": "PHASE_5_SWARM_DEBATE",
                "message": "Swarm debate is active based on user choice.",
                "data": selected_res.data[0]
            }

        # 3. Phase 4 (First Step): Show the "Most Preferred" strategy
        preferred_res = supabase.table("strategy_proposals") \
            .select("*") \
            .eq("merchant_id", merchant_id) \
            .eq("is_preferred", True) \
            .eq("is_skipped", False) \
            .execute()
        
        if preferred_res.data:
            return {
                "current_phase": "PHASE_4_PREFERRED_CHOICE",
                "message": "AI has a top recommendation for you.",
                "data": preferred_res.data[0] # return the most preferred strategy that has not been skipped
            }

        # 4. Phase 4 (Give-in Step): Show extra suggestions if the preferred one was skipped
        extra_res = supabase.table("strategy_proposals") \
            .select("*") \
            .eq("merchant_id", merchant_id) \
            .eq("is_preferred", False) \
            .order("risk_level") \
            .limit(3) \
            .execute()
            
        if extra_res.data:
            return {
                "current_phase": "PHASE_4_GIVE_IN_SUGGESTIONS",
                "message": "Here are 3 extra suggestions based on your feedback.",
                "data": extra_res.data 
            }

        # 5. Phase 1/2: Default State
        return {
            "current_phase": "PHASE_NORMAL",
            "message": "All good. System is analyzing background data."
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
    