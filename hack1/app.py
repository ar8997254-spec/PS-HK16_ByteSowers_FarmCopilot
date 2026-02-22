import sqlite3
import ollama
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import pickle
import pandas as pd
from datetime import datetime
import requests
import time

# ─────────────────────────────────────────────
#  DATABASE SETUP
# ─────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("farm.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            farmer_name TEXT
        )
    ''')
    # Track prediction history per user
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            crop TEXT NOT NULL,
            price REAL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (username, password, farmer_name) VALUES (?, ?, ?)",
            ("admin", "farm123", "Rajesh Kumar")
        )
    conn.commit()
    conn.close()

init_db()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ─────────────────────────────────────────────
#  ML MODELS
# ─────────────────────────────────────────────
model  = pickle.load(open("model.pkl",  "rb"))
scaler = pickle.load(open("scaler.pkl", "rb"))

# ─────────────────────────────────────────────
#  CROP INTELLIGENCE DATABASE
# ─────────────────────────────────────────────
crop_intelligence = {
    'rice':        {'growth': 135, 'sell_month': 'January',  'price': 2369,  'life': 180, 'type': 'grain', 'min_temp': 20, 'max_temp': 35, 'sowing_months': [1, 2, 6, 7]},
    'maize':       {'growth': 110, 'sell_month': 'November', 'price': 2400,  'life': 150, 'type': 'grain', 'min_temp': 18, 'max_temp': 32, 'sowing_months': [6, 7, 10, 11]},
    'chickpea':    {'growth': 120, 'sell_month': 'May',      'price': 5875,  'life': 240, 'type': 'pulse', 'min_temp': 15, 'max_temp': 25, 'sowing_months': [10, 11]},
    'kidneybeans': {'growth': 100, 'sell_month': 'April',    'price': 6000,  'life': 180, 'type': 'pulse', 'min_temp': 15, 'max_temp': 25, 'sowing_months': [10, 11]},
    'pigeonpeas':  {'growth': 170, 'sell_month': 'January',  'price': 7550,  'life': 240, 'type': 'pulse', 'min_temp': 20, 'max_temp': 30, 'sowing_months': [6, 7]},
    'mothbeans':   {'growth': 80,  'sell_month': 'October',  'price': 5000,  'life': 180, 'type': 'pulse', 'min_temp': 25, 'max_temp': 35, 'sowing_months': [6, 7]},
    'mungbean':    {'growth': 80,  'sell_month': 'September','price': 8768,  'life': 180, 'type': 'pulse', 'min_temp': 25, 'max_temp': 35, 'sowing_months': [2, 3, 6]},
    'blackgram':   {'growth': 85,  'sell_month': 'October',  'price': 7800,  'life': 180, 'type': 'pulse', 'min_temp': 25, 'max_temp': 35, 'sowing_months': [2, 3, 6, 7]},
    'lentil':      {'growth': 110, 'sell_month': 'April',    'price': 7000,  'life': 240, 'type': 'pulse', 'min_temp': 15, 'max_temp': 25, 'sowing_months': [10, 11]},
    'pomegranate': {'growth': 150, 'sell_month': 'August',   'price': 8500,  'life': 45,  'type': 'fruit', 'min_temp': 20, 'max_temp': 32, 'sowing_months': [1, 2, 6]},
    'banana':      {'growth': 300, 'sell_month': 'July',     'price': 1800,  'life': 10,  'type': 'fruit', 'min_temp': 20, 'max_temp': 35, 'sowing_months': [6, 7]},
    'mango':       {'growth': 120, 'sell_month': 'June',     'price': 3500,  'life': 15,  'type': 'fruit', 'min_temp': 24, 'max_temp': 35, 'sowing_months': [6, 7]},
    'grapes':      {'growth': 150, 'sell_month': 'March',    'price': 4800,  'life': 20,  'type': 'fruit', 'min_temp': 15, 'max_temp': 30, 'sowing_months': [2, 3]},
    'watermelon':  {'growth': 90,  'sell_month': 'May',      'price': 1300,  'life': 15,  'type': 'fruit', 'min_temp': 24, 'max_temp': 35, 'sowing_months': [1, 2, 3]},
    'muskmelon':   {'growth': 85,  'sell_month': 'May',      'price': 1600,  'life': 12,  'type': 'fruit', 'min_temp': 24, 'max_temp': 35, 'sowing_months': [1, 2, 3]},
    'apple':       {'growth': 180, 'sell_month': 'October',  'price': 7500,  'life': 120, 'type': 'fruit', 'min_temp': 7,  'max_temp': 21, 'sowing_months': [1, 2]},
    'orange':      {'growth': 240, 'sell_month': 'January',  'price': 4000,  'life': 30,  'type': 'fruit', 'min_temp': 13, 'max_temp': 32, 'sowing_months': [1, 2, 6, 7]},
    'papaya':      {'growth': 270, 'sell_month': 'October',  'price': 1600,  'life': 7,   'type': 'fruit', 'min_temp': 20, 'max_temp': 32, 'sowing_months': [2, 3, 10]},
    'coconut':     {'growth': 365, 'sell_month': 'June',     'price': 12500, 'life': 90,  'type': 'fruit', 'min_temp': 20, 'max_temp': 35, 'sowing_months': [6, 7]},
    'cotton':      {'growth': 180, 'sell_month': 'March',    'price': 7710,  'life': 365, 'type': 'comm',  'min_temp': 22, 'max_temp': 35, 'sowing_months': [4, 5, 6]},
    'jute':        {'growth': 120, 'sell_month': 'August',   'price': 5650,  'life': 365, 'type': 'comm',  'min_temp': 24, 'max_temp': 35, 'sowing_months': [3, 4, 5]},
    'coffee':      {'growth': 700, 'sell_month': 'February', 'price': 25000, 'life': 365, 'type': 'comm',  'min_temp': 15, 'max_temp': 28, 'sowing_months': [1, 2, 3, 4]},
}

CROP_MAP = {
    'rice': 'Paddy(Dhan)', 'maize': 'Maize', 'chickpea': 'Gram',
    'kidneybeans': 'Rajmash', 'pigeonpeas': 'Arhar (Tur/Red Gram)',
    'mothbeans': 'Moth Dal', 'mungbean': 'Moong(Green Gram)',
    'blackgram': 'Mash', 'lentil': 'Lentil (Masur)',
    'pomegranate': 'Pomegranate', 'banana': 'Banana', 'mango': 'Mango',
    'grapes': 'Grapes', 'watermelon': 'Water Melon', 'muskmelon': 'Musk Melon',
    'apple': 'Apple', 'orange': 'Orange', 'papaya': 'Papaya',
    'coconut': 'Coconut', 'cotton': 'Cotton', 'jute': 'Jute', 'coffee': 'Coffee',
}

# ─────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────
def get_live_mandi_price(crop_name):
    api_crop_name = CROP_MAP.get(crop_name, crop_name)
    API_KEY = "579b464db66ec23bdd0000017b0a938b050048b3421430109e2a19e1"
    resource_id = "bc486650-6a75-450b-8012-78d9ed987da1"
    url = f"https://api.data.gov.in/resource/{resource_id}?api-key={API_KEY}&format=json"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get('records'):
            for record in data['records']:
                if record.get('commodity', '').lower() in api_crop_name.lower():
                    return record['modal_price']
            return data['records'][0]['modal_price']
        return None
    except Exception:
        return None

def get_live_climate(city):
    API_KEY = "431ecadc055a1b3b113f33f7e74e221f"
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&cachebust={time.time()}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get("cod") != 200:
            return None
        return data
    except Exception:
        return None

# ─────────────────────────────────────────────
#  DATA MODELS
# ─────────────────────────────────────────────
class SoilData(BaseModel):
    Nitrogen: float
    phosphorus: float
    potassium: float
    temperature: float
    humidity: float
    ph: float
    rainfall: float

class LoginData(BaseModel):
    username: str
    password: str

class RegisterData(BaseModel):
    username: str
    password: str
    farmer_name: str

class ChatRequest(BaseModel):
    message: str

class LifecycleRequest(BaseModel):
    city: str
    crop: str
    sowing_date: str

class WeatherRequest(BaseModel):
    city: str

# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/predict")
async def predict_crop(data: SoilData):
    try:
        if not (0   <= data.Nitrogen    <= 140): return {"error": "Nitrogen must be between 0 and 140."}
        if not (5   <= data.phosphorus  <= 145): return {"error": "Phosphorous must be between 5 and 145."}
        if not (5   <= data.potassium   <= 205): return {"error": "Potassium must be between 5 and 205."}
        if not (10  <= data.temperature <= 50):  return {"error": "Temperature must be between 10°C and 50°C."}
        if not (15  <= data.humidity    <= 100): return {"error": "Humidity must be between 15% and 100%."}
        if not (3.5 <= data.ph          <= 9.0): return {"error": "Soil pH must be between 3.5 and 9.0."}
        if not (20  <= data.rainfall    <= 300): return {"error": "Rainfall must be between 20mm and 300mm."}

        cols = ['Nitrogen', 'phosphorus', 'potassium', 'temperature', 'humidity', 'ph', 'rainfall']
        input_df    = pd.DataFrame([[data.Nitrogen, data.phosphorus, data.potassium,
                                     data.temperature, data.humidity, data.ph, data.rainfall]], columns=cols)
        scaled_data = scaler.transform(input_df)
        crop_name   = model.predict(scaled_data)[0].lower()

        info       = crop_intelligence.get(crop_name, {'growth': 120, 'sell_month': 'Unknown', 'price': 3000, 'life': 30, 'type': 'grain'})
        live_price = get_live_mandi_price(crop_name)

        if info['type'] == 'fruit' and data.humidity > 70:
            alert     = f"CRITICAL: Move to cold storage within {round(info['life']*0.2, 1)} days."
            status_ui = "danger"
        elif data.humidity > 80:
            alert     = f"WARNING: High moisture. Move to dry storage within {round(info['life']*0.4, 1)} days."
            status_ui = "warning"
        else:
            alert     = f"STABLE: Produce is safe for {info['life']} days post-harvest."
            status_ui = "success"

        return {
            "crop":        crop_name.upper(),
            "status":      "success",
            "sowing":      f"Feasible now. Harvest in {info['growth']} days.",
            "price":       live_price if live_price else info['price'],
            "growth_time": info['growth'],
            "sell_month":  info['sell_month'],
            "alert":       alert,
            "ui_status":   status_ui,
            "crop_type":   info['type'],
        }
    except Exception:
        return {"error": "Prediction Error. Check input values."}


@app.post("/lifecycle-advice")
async def get_lifecycle_plan(data: LifecycleRequest):
    weather = get_live_climate(data.city)
    if not weather:
        return {"error": f"City '{data.city}' not found."}

    crop_key = data.crop.lower()
    if crop_key not in crop_intelligence:
        return {"error": f"Crop '{data.crop}' not found."}

    crop_info     = crop_intelligence[crop_key]
    temp          = weather['main']['temp']
    humidity      = weather['main']['humidity']
    condition     = weather['weather'][0]['main'].lower()
    current_month = datetime.now().month

    try:
        sowing   = datetime.strptime(data.sowing_date, "%Y-%m-%d")
        age_days = (datetime.now() - sowing).days
        if age_days < 0:
            return {"error": "Sowing date is in the future."}
        progress = (age_days / crop_info['growth']) * 100
    except ValueError:
        return {"error": "Invalid date format."}

    if age_days > (crop_info['growth'] + 30):
        advice = f"❌ OVERDUE: Quality is likely degraded. Harvest immediately."
    elif current_month not in crop_info['sowing_months'] and age_days < 15:
        advice = f"⚠️ SEASON MISMATCH: Use shade nets and mulch."
    elif temp > crop_info['max_temp']:
        advice = f"⚠️ HEAT STRESS ({temp}°C): Increase evening irrigation."
    elif temp < crop_info['min_temp']:
        advice = f"⚠️ COLD STRESS ({temp}°C): Cover seedlings."
    elif age_days >= crop_info['growth']:
        if "rain" in condition or humidity > 75:
            advice = f"🚨 WEATHER ALERT: High humidity ({humidity}%). Wait 48hrs to harvest."
        else:
            advice = f"✅ OPTIMAL HARVEST: Price approx ₹{crop_info['price']}/quintal."
    else:
        stage  = "🌱 SEEDLING" if progress < 30 else "🌿 GROWTH"
        advice = f"{stage}: {data.crop.capitalize()} is {round(progress)}% done. Temp {temp}°C is stable."

    return {
        "current_weather": f"{temp}°C, {condition.capitalize()}",
        "advice":          advice,
        "days_old":        age_days,
        "progress":        round(progress, 1),
        "humidity":        humidity,
        "wind_speed":      weather.get('wind', {}).get('speed', 0),
    }


# ─── NEW: Dashboard weather widget ───────────────────────────
@app.post("/dashboard-weather")
async def dashboard_weather(data: WeatherRequest):
    """Lightweight weather fetch for the dashboard widget."""
    weather = get_live_climate(data.city)
    if not weather:
        return {"error": f"City '{data.city}' not found."}
    return {
        "city":       data.city.title(),
        "temp":       weather['main']['temp'],
        "feels_like": weather['main']['feels_like'],
        "humidity":   weather['main']['humidity'],
        "condition":  weather['weather'][0]['main'],
        "desc":       weather['weather'][0]['description'].title(),
        "wind":       weather.get('wind', {}).get('speed', 0),
        "icon":       weather['weather'][0]['icon'],
    }


# ─── NEW: Top crop prices for market ticker ──────────────────
@app.get("/market-prices")
async def market_prices():
    """Return current prices for top 6 crops for the dashboard ticker."""
    crops = ['rice', 'wheat', 'maize', 'cotton', 'mungbean', 'pigeonpeas']
    result = []
    for crop in crops:
        info  = crop_intelligence.get(crop, {})
        price = get_live_mandi_price(crop) or info.get('price', 0)
        result.append({
            "crop":  crop.capitalize(),
            "price": price,
            "unit":  "₹/qtl",
            "type":  info.get('type', 'grain'),
        })
    return {"prices": result}


# ─── NEW: Seasonal sowing calendar ───────────────────────────
@app.get("/sowing-calendar")
async def sowing_calendar():
    """Return which crops are ideal to sow this month and next."""
    current_month = datetime.now().month
    next_month    = (current_month % 12) + 1
    this_crops, next_crops = [], []
    for name, info in crop_intelligence.items():
        if current_month in info['sowing_months']:
            this_crops.append({"crop": name.capitalize(), "type": info['type'], "growth": info['growth'], "price": info['price']})
        if next_month in info['sowing_months']:
            next_crops.append({"crop": name.capitalize(), "type": info['type'], "growth": info['growth'], "price": info['price']})
    return {
        "this_month":  datetime.now().strftime("%B"),
        "next_month":  datetime(2000, next_month, 1).strftime("%B"),
        "sow_now":     this_crops,
        "sow_next":    next_crops,
    }


# ─── NEW: Crop comparison endpoint ───────────────────────────
@app.get("/compare-crops")
async def compare_crops(crop1: str = "rice", crop2: str = "maize"):
    """Compare two crops side-by-side."""
    c1 = crop_intelligence.get(crop1.lower())
    c2 = crop_intelligence.get(crop2.lower())
    if not c1 or not c2:
        return {"error": "One or both crops not found."}
    return {
        "crop1": {"name": crop1.capitalize(), **c1},
        "crop2": {"name": crop2.capitalize(), **c2},
    }


# ─── CHAT ─────────────────────────────────────────────────────
@app.post("/chat")
async def chat_with_ai(data: ChatRequest):
    system_prompt = (
        "You are 'FarmCopilot Assistant'. "
        "Help with Indian farming, NPK values, and weather. "
        "Use simple English. Keep it under 80 words."
    )
    try:
        response = ollama.chat(model='gemma2:2b', messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': data.message},
        ])
        return {"reply": response['message']['content']}
    except Exception:
        return {"reply": "Ollama is loading... check your terminal download status!"}


# ─── AUTH ─────────────────────────────────────────────────────
@app.post("/login")
async def login(data: LoginData):
    conn = sqlite3.connect("farm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT farmer_name FROM users WHERE username = ? AND password = ?",
                   (data.username, data.password))
    user = cursor.fetchone()
    conn.close()
    if user:
        return {"status": "success", "farmer_name": user[0]}
    return {"status": "error", "message": "Invalid Login"}


@app.post("/register")
async def register(data: RegisterData):
    try:
        conn = sqlite3.connect("farm.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, farmer_name) VALUES (?, ?, ?)",
                       (data.username, data.password, data.farmer_name))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception:
        return {"status": "error", "message": "ID already exists"}
