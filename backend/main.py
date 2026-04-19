import os
import uuid
import requests
from fastapi import FastAPI, UploadFile, File
from dotenv import load_dotenv
from supabase import create_client, Client
from fastapi import BackgroundTasks
from datetime import datetime

load_dotenv()
app = FastAPI()

AI_SERVICE_URL = "http://urfriendPC:8001/analyze" #junbin must place AI interface address here

# connect Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

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

# feature: save the AI analysis cost 
@app.post("/add-ingredient")
async def add_ingredient(name: str, price: float, m_id: str):
    data = {"merchant_id": m_id, "item_name": name, "price_per_unit": price}
    response = supabase.table("ingredient_costs").insert(data).execute()
    return {"status": "success", "data": response.data}


@app.post("/upload-receipt/{merchant_id}")
async def upload_receipt(merchant_id: str, file: UploadFile = File(...)):
    # create file and prevent same
    file_extension = file.filename.split(".")[-1]
    file_name = f"{uuid.uuid4()}.{file_extension}"
    file_path = f"{merchant_id}/{file_name}"

    # read the file and upload to Supabase Storage
    contents = await file.read()
    supabase.storage.from_("receipts").upload(file_path, contents)

    # get the public URL from pic (send to teammate taht handle AI part)
    image_url = supabase.storage.from_("receipts").get_public_url(file_path)

    # 2. simultate AI connect (Z AI GLM logic)
    # In a real-world scenario, use `requests.post(AI_API_URL, json={"url": image_url})`
    # simulate the JSON result returned by the AI.
    mock_ai_result = [
        {"item": "Chicken Breast", "price": 15.50},
        {"item": "Cooking Oil", "price": 45.00}
    ]

    # Feed the link to AI through API
    payload = {"receipt_url": image_url}
    
    try:
        # Send a POST request to the AI ​​interface
        response = requests.post(AI_SERVICE_URL, json=payload)
        
        # Get the JSON result analysis by AI
        ai_data = response.json()

        # 3. store analysis results in database
        saved_items = []
        for entry in mock_ai_result:
            data = {
                "merchant_id": merchant_id,
                "item_name": entry["item"],
                "price_per_unit": entry["price"]
            }
            res = supabase.table("ingredient_costs").insert(data).execute()
            saved_items.append(res.data)

        return {
            "status": "Success",
            "image_url": image_url,
            "parsed_data": saved_items
        }
    except Exception as e:
            return {"error": "Fail connect to AI service", "details": str(e)}

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
    
@app.get("/get-ai-decision-package/{merchant_id}")
async def get_package(merchant_id: str, address: str, background_tasks: BackgroundTasks): # 2. 这里加上参数
    
    background_tasks.add_task(check_and_notify_costs, merchant_id)
    
    lat, lon = get_coordinates(address)
    if lat is None:
        return {"error": "Invalid address"}

    weather = get_weather_context(lat, lon)
    traffic = get_traffic_context(lat, lon)
    schools = get_nearby_schools(lat, lon)

    return {
        "merchant_id": merchant_id,
        "environment": {
            "weather": weather,
            "traffic": traffic,
            "schools": schools
        },
        "timestamp": datetime.now().isoformat()
    }

    # Send this to your friend's Multi-Agent Debate module
    # response = requests.post(AI_API, json=context_package)
    return context_package


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
    