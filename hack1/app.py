import sqlite3
import ollama  # <--- CHANGED: New Import
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import pickle
import pandas as pd
from datetime import datetime
import requests
import time

# --- DATABASE SETUP ---
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
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, farmer_name) VALUES (?, ?, ?)", 
                       ("admin", "farm123", "Rajesh Kumar"))
    conn.commit()
    conn.close()

init_db()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- 1. LOAD ML MODELS ---
model = pickle.load(open("model.pkl", "rb"))
scaler = pickle.load(open("scaler.pkl", "rb"))

# --- 2. CROP INTELLIGENCE DATABASE ---
crop_intelligence = {
    'rice': {'growth': 135, 'sell_month': 'January', 'price': 2369, 'life': 180, 'type': 'grain','min_temp': 20, 'max_temp': 35, 'sowing_months': [1, 2, 6, 7] },
    'maize': {'growth': 110, 'sell_month': 'November', 'price': 2400, 'life': 150, 'type': 'grain','min_temp': 18, 'max_temp': 32, 'sowing_months': [6, 7, 10, 11]},
    'chickpea': {'growth': 120, 'sell_month': 'May', 'price': 5875, 'life': 240, 'type': 'pulse','min_temp': 15, 'max_temp': 25, 'sowing_months': [10, 11]},
    'kidneybeans': {'growth': 100, 'sell_month': 'April', 'price': 6000, 'life': 180, 'type': 'pulse','min_temp': 15, 'max_temp': 25, 'sowing_months': [10, 11]},
    'pigeonpeas': {'growth': 170, 'sell_month': 'January', 'price': 7550, 'life': 240, 'type': 'pulse','min_temp': 20, 'max_temp': 30, 'sowing_months': [6, 7]},
    'mothbeans': {'growth': 80, 'sell_month': 'October', 'price': 5000, 'life': 180, 'type': 'pulse','min_temp': 25, 'max_temp': 35, 'sowing_months': [6, 7]},
    'mungbean': {'growth': 80, 'sell_month': 'September', 'price': 8768, 'life': 180, 'type': 'pulse','min_temp': 25, 'max_temp': 35, 'sowing_months': [2, 3, 6]},
    'blackgram': {'growth': 85, 'sell_month': 'October', 'price': 7800, 'life': 180, 'type': 'pulse','min_temp': 25, 'max_temp': 35, 'sowing_months': [2, 3, 6, 7]},
    'lentil': {'growth': 110, 'sell_month': 'April', 'price': 7000, 'life': 240, 'type': 'pulse','min_temp': 15, 'max_temp': 25, 'sowing_months': [10, 11]},
    'pomegranate': {'growth': 150, 'sell_month': 'August', 'price': 8500, 'life': 45, 'type': 'fruit','min_temp': 20, 'max_temp': 32, 'sowing_months': [1, 2, 6]},
    'banana': {'growth': 300, 'sell_month': 'July', 'price': 1800, 'life': 10, 'type': 'fruit','min_temp': 20, 'max_temp': 35, 'sowing_months': [6, 7]},
    'mango': {'growth': 120, 'sell_month': 'June', 'price': 3500, 'life': 15, 'type': 'fruit','min_temp': 24, 'max_temp': 35, 'sowing_months': [6, 7]},
    'grapes': {'growth': 150, 'sell_month': 'March', 'price': 4800, 'life': 20, 'type': 'fruit','min_temp': 15, 'max_temp': 30, 'sowing_months': [2, 3]},
    'watermelon': {'growth': 90, 'sell_month': 'May', 'price': 1300, 'life': 15, 'type': 'fruit','min_temp': 24, 'max_temp': 35, 'sowing_months': [1, 2, 3]},
    'muskmelon': {'growth': 85, 'sell_month': 'May', 'price': 1600, 'life': 12, 'type': 'fruit','min_temp': 24, 'max_temp': 35, 'sowing_months': [1, 2, 3]},
    'apple': {'growth': 180, 'sell_month': 'October', 'price': 7500, 'life': 120, 'type': 'fruit','min_temp': 7, 'max_temp': 21, 'sowing_months': [1, 2]},
    'orange': {'growth': 240, 'sell_month': 'January', 'price': 4000, 'life': 30, 'type': 'fruit','min_temp': 13, 'max_temp': 32, 'sowing_months': [1, 2, 6, 7]},
    'papaya': {'growth': 270, 'sell_month': 'October', 'price': 1600, 'life': 7, 'type': 'fruit','min_temp': 20, 'max_temp': 32, 'sowing_months': [2, 3, 10]},
    'coconut': {'growth': 365, 'sell_month': 'June', 'price': 12500, 'life': 90, 'type': 'fruit','min_temp': 20, 'max_temp': 35, 'sowing_months': [6, 7]},
    'cotton': {'growth': 180, 'sell_month': 'March', 'price': 7710, 'life': 365, 'type': 'comm','min_temp': 22, 'max_temp': 35, 'sowing_months': [4, 5, 6]},
    'jute': {'growth': 120, 'sell_month': 'August', 'price': 5650, 'life': 365, 'type': 'comm','min_temp': 24, 'max_temp': 35, 'sowing_months': [3, 4, 5]},
    'coffee': {'growth': 700, 'sell_month': 'February', 'price': 25000, 'life': 365, 'type': 'comm','min_temp': 15, 'max_temp': 28, 'sowing_months': [1, 2, 3, 4]}
}

CROP_MAP = {
    'rice': 'Paddy(Dhan)', 'maize': 'Maize', 'chickpea': 'Gram',
    'kidneybeans': 'Rajmash', 'pigeonpeas': 'Arhar (Tur/Red Gram)',
    'mothbeans': 'Moth Dal', 'mungbean': 'Moong(Green Gram)',
    'blackgram': 'Mash', 'lentil': 'Lentil (Masur)',
    'pomegranate': 'Pomegranate', 'banana': 'Banana', 'mango': 'Mango',
    'grapes': 'Grapes', 'watermelon': 'Water Melon', 'muskmelon': 'Musk Melon',
    'apple': 'Apple', 'orange': 'Orange', 'papaya': 'Papaya',
    'coconut': 'Coconut', 'cotton': 'Cotton', 'jute': 'Jute', 'coffee': 'Coffee'
}

# --- 3. HELPER FUNCTIONS ---
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
    except:
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
    except:
        return None

# --- 4. DATA MODELS ---
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

# --- 5. ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/predict")
async def predict_crop(data: SoilData):
    try:
        # STEP 1: VALIDATION
        if not (0 <= data.Nitrogen <= 140): return {"error": "Nitrogen must be between 0 and 140."}
        if not (5 <= data.phosphorus <= 145): return {"error": "Phosphorous must be between 5 and 145."}
        if not (5 <= data.potassium <= 205): return {"error": "Potassium must be between 5 and 205."}
        if not (10 <= data.temperature <= 50): return {"error": "Temperature must be between 10°C and 50°C."}
        if not (15 <= data.humidity <= 100): return {"error": "Humidity must be between 15% and 100%."}
        if not (3.5 <= data.ph <= 9.0): return {"error": "Soil pH must be between 3.5 and 9.0."}
        if not (20 <= data.rainfall <= 300): return {"error": "Rainfall must be between 20mm and 300mm."}

        # STEP 2: PREDICTION
        cols = ['Nitrogen', 'phosphorus', 'potassium', 'temperature', 'humidity', 'ph', 'rainfall']
        input_df = pd.DataFrame([[data.Nitrogen, data.phosphorus, data.potassium, data.temperature, data.humidity, data.ph, data.rainfall]], columns=cols)
        scaled_data = scaler.transform(input_df)
        crop_name = model.predict(scaled_data)[0].lower()
        
        info = crop_intelligence.get(crop_name, {'growth': 120, 'sell_month': 'Unknown', 'price': 3000, 'life': 30, 'type': 'grain'})
        live_price = get_live_mandi_price(crop_name)
        
        # STEP 4: ALERT LOGIC
        if info['type'] == 'fruit' and data.humidity > 70:
            alert = f"CRITICAL: Move to cold storage within {round(info['life']*0.2, 1)} days."
            status_ui = "danger"
        elif data.humidity > 80:
            alert = f"WARNING: High moisture. Move to dry storage within {round(info['life']*0.4, 1)} days."
            status_ui = "warning"
        else:
            alert = f"STABLE: Produce is safe for {info['life']} days post-harvest."
            status_ui = "success"

        return {
            "crop": crop_name.upper(),
            "status": "success",
            "sowing": f"Feasible now. Harvest in {info['growth']} days.",
            "price": live_price if live_price else info['price'],
            "growth_time": info['growth'],
            "sell_month": info['sell_month'],
            "alert": alert,
            "ui_status": status_ui
        }
    except Exception as e:
        return {"error": "Prediction Error. Check input values."}
class LifecycleRequest(BaseModel):
    city: str
    crop: str
    sowing_date: str

@app.post("/lifecycle-advice")
async def get_lifecycle_plan(data: LifecycleRequest):
    city=data.city
    crop = data.crop
    sowing_date = data.sowing_date
    weather = get_live_climate(city)
    if not weather: return {"error": f"City '{city}' not found."}

    crop_key = crop.lower()
    if crop_key not in crop_intelligence: return {"error": f"Crop '{crop}' not found."}

    crop_info = crop_intelligence[crop_key]
    temp = weather['main']['temp']
    humidity = weather['main']['humidity']
    condition = weather['weather'][0]['main'].lower()
    current_month = datetime.now().month

    try:
        sowing = datetime.strptime(sowing_date, "%Y-%m-%d")
        age_days = (datetime.now() - sowing).days
        if age_days < 0: return {"error": "Sowing date is in future."}
        progress = (age_days / crop_info['growth']) * 100
    except: return {"error": "Invalid date."}

    # ADVICE LOGIC
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
        stage = "🌱 SEEDLING" if progress < 30 else "🌿 GROWTH"
        advice = f"{stage}: {crop.capitalize()} is {round(progress)}% done. Temp {temp}°C is stable."

    return {"current_weather": f"{temp}°C, {condition.capitalize()}", "advice": advice, "days_old": age_days, "progress": round(progress, 1)}

# --- 6. LOCAL AI CHAT (OLLAMA) ---
@app.post("/chat")
async def chat_with_ai(data: ChatRequest):
    # This tells the local AI how to behave
    system_prompt = (
        "You are 'FarmCopilot Assistant'. "
        "Help with Indian farming, NPK values, and weather. "
        "Use simple English. Keep it under 80 words."
    )
    
    try:
        # <--- CHANGED: Now using local gemma2:2b instead of Gemini API
        response = ollama.chat(model='gemma2:2b', messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': data.message},
        ])
        return {"reply": response['message']['content']}
    except Exception as e:
        return {"reply": "Ollama is loading... check your terminal download status!"}

# --- 7. AUTH ROUTES ---
@app.post("/login")
async def login(data: LoginData):
    conn = sqlite3.connect("farm.db"); cursor = conn.cursor()
    cursor.execute("SELECT farmer_name FROM users WHERE username = ? AND password = ?", (data.username, data.password))
    user = cursor.fetchone(); conn.close()
    if user: return {"status": "success", "farmer_name": user[0]}
    return {"status": "error", "message": "Invalid Login"}

@app.post("/register")
async def register(data: RegisterData):
    try:
        conn = sqlite3.connect("farm.db"); cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, farmer_name) VALUES (?, ?, ?)", (data.username, data.password, data.farmer_name))
        conn.commit(); conn.close()
        return {"status": "success"}
    except: return {"status": "error", "message": "ID already exists"}


# import sqlite3

# # Initialize Database
# def init_db():
#     conn = sqlite3.connect("farm.db")
#     cursor = conn.cursor()
#     # Create users table if it doesn't exist
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS users (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             username TEXT UNIQUE NOT NULL,
#             password TEXT NOT NULL,
#             farmer_name TEXT
#         )
#     ''')
#     # Add a default farmer if the table is empty
#     cursor.execute("SELECT COUNT(*) FROM users")
#     if cursor.fetchone()[0] == 0:
#         cursor.execute("INSERT INTO users (username, password, farmer_name) VALUES (?, ?, ?)", 
#                        ("admin", "farm123", "Rajesh Kumar"))
#     conn.commit()
#     conn.close()

# init_db()

# from fastapi import FastAPI, Request
# from fastapi.responses import HTMLResponse
# from fastapi.templating import Jinja2Templates
# from pydantic import BaseModel
# import pickle
# import pandas as pd
# from datetime import datetime
# import requests
# import google.generativeai as genai
# import time

# # PASTE YOUR KEY HERE
# # Use the exact string you just provided
# # Line 41: Your confirmed key
# genai.configure(api_key="AIzaSyDvxUgdCbJXLiLLXt59zYLBrKxy9Gkfeuw") 

# # Line 43: Change to this specific version
# ai_model = genai.GenerativeModel('gemini-1.5-flash-001')

# app = FastAPI()
# templates = Jinja2Templates(directory="templates")

# # 1. LOAD THE ML MODELS
# # Ensure these files are in your 'hack1' folder
# model = pickle.load(open("model.pkl", "rb"))
# scaler = pickle.load(open("scaler.pkl", "rb"))

# # 2. CROP INTELLIGENCE DATABASE
# crop_intelligence = {
#     'rice': {'growth': 135, 'sell_month': 'January', 'price': 2369, 'life': 180, 'type': 'grain','min_temp': 20, 'max_temp': 35, 'sowing_months': [1, 2, 6, 7] },
#     'maize': {'growth': 110, 'sell_month': 'November', 'price': 2400, 'life': 150, 'type': 'grain','min_temp': 18, 'max_temp': 32, 'sowing_months': [6, 7, 10, 11]},
#     'chickpea': {'growth': 120, 'sell_month': 'May', 'price': 5875, 'life': 240, 'type': 'pulse','min_temp': 15, 'max_temp': 25, 'sowing_months': [10, 11]},
#     'kidneybeans': {'growth': 100, 'sell_month': 'April', 'price': 6000, 'life': 180, 'type': 'pulse','min_temp': 15, 'max_temp': 25, 'sowing_months': [10, 11]},
#     'pigeonpeas': {'growth': 170, 'sell_month': 'January', 'price': 7550, 'life': 240, 'type': 'pulse','min_temp': 20, 'max_temp': 30, 'sowing_months': [6, 7]},
#     'mothbeans': {'growth': 80, 'sell_month': 'October', 'price': 5000, 'life': 180, 'type': 'pulse','min_temp': 25, 'max_temp': 35, 'sowing_months': [6, 7]},
#     'mungbean': {'growth': 80, 'sell_month': 'September', 'price': 8768, 'life': 180, 'type': 'pulse','min_temp': 25, 'max_temp': 35, 'sowing_months': [2, 3, 6]},
#     'blackgram': {'growth': 85, 'sell_month': 'October', 'price': 7800, 'life': 180, 'type': 'pulse','min_temp': 25, 'max_temp': 35, 'sowing_months': [2, 3, 6, 7]},
#     'lentil': {'growth': 110, 'sell_month': 'April', 'price': 7000, 'life': 240, 'type': 'pulse','min_temp': 15, 'max_temp': 25, 'sowing_months': [10, 11]},
#     'pomegranate': {'growth': 150, 'sell_month': 'August', 'price': 8500, 'life': 45, 'type': 'fruit','min_temp': 20, 'max_temp': 32, 'sowing_months': [1, 2, 6]},
#     'banana': {'growth': 300, 'sell_month': 'July', 'price': 1800, 'life': 10, 'type': 'fruit','min_temp': 20, 'max_temp': 35, 'sowing_months': [6, 7]},
#     'mango': {'growth': 120, 'sell_month': 'June', 'price': 3500, 'life': 15, 'type': 'fruit','min_temp': 24, 'max_temp': 35, 'sowing_months': [6, 7]},
#     'grapes': {'growth': 150, 'sell_month': 'March', 'price': 4800, 'life': 20, 'type': 'fruit','min_temp': 15, 'max_temp': 30, 'sowing_months': [2, 3]},
#     'watermelon': {'growth': 90, 'sell_month': 'May', 'price': 1300, 'life': 15, 'type': 'fruit','min_temp': 24, 'max_temp': 35, 'sowing_months': [1, 2, 3]},
#     'muskmelon': {'growth': 85, 'sell_month': 'May', 'price': 1600, 'life': 12, 'type': 'fruit','min_temp': 24, 'max_temp': 35, 'sowing_months': [1, 2, 3]},
#     'apple': {'growth': 180, 'sell_month': 'October', 'price': 7500, 'life': 120, 'type': 'fruit','min_temp': 7, 'max_temp': 21, 'sowing_months': [1, 2]},
#     'orange': {'growth': 240, 'sell_month': 'January', 'price': 4000, 'life': 30, 'type': 'fruit','min_temp': 13, 'max_temp': 32, 'sowing_months': [1, 2, 6, 7]},
#     'papaya': {'growth': 270, 'sell_month': 'October', 'price': 1600, 'life': 7, 'type': 'fruit','min_temp': 20, 'max_temp': 32, 'sowing_months': [2, 3, 10]},
#     'coconut': {'growth': 365, 'sell_month': 'June', 'price': 12500, 'life': 90, 'type': 'fruit','min_temp': 20, 'max_temp': 35, 'sowing_months': [6, 7]},
#     'cotton': {'growth': 180, 'sell_month': 'March', 'price': 7710, 'life': 365, 'type': 'comm','min_temp': 22, 'max_temp': 35, 'sowing_months': [4, 5, 6]},
#     'jute': {'growth': 120, 'sell_month': 'August', 'price': 5650, 'life': 365, 'type': 'comm','min_temp': 24, 'max_temp': 35, 'sowing_months': [3, 4, 5]},
#     'coffee': {'growth': 700, 'sell_month': 'February', 'price': 25000, 'life': 365, 'type': 'comm','min_temp': 15, 'max_temp': 28, 'sowing_months': [1, 2, 3, 4]}
# }

# CROP_MAP = {
#     'rice': 'Paddy(Dhan)', 'maize': 'Maize', 'chickpea': 'Gram',
#     'kidneybeans': 'Rajmash', 'pigeonpeas': 'Arhar (Tur/Red Gram)',
#     'mothbeans': 'Moth Dal', 'mungbean': 'Moong(Green Gram)',
#     'blackgram': 'Mash', 'lentil': 'Lentil (Masur)',
#     'pomegranate': 'Pomegranate', 'banana': 'Banana', 'mango': 'Mango',
#     'grapes': 'Grapes', 'watermelon': 'Water Melon', 'muskmelon': 'Musk Melon',
#     'apple': 'Apple', 'orange': 'Orange', 'papaya': 'Papaya',
#     'coconut': 'Coconut', 'cotton': 'Cotton', 'jute': 'Jute', 'coffee': 'Coffee'
# }

# # 3. HELPER FUNCTIONS
# def get_live_mandi_price(crop_name):
#     api_crop_name = CROP_MAP.get(crop_name, crop_name)
#     API_KEY = "579b464db66ec23bdd0000017b0a938b050048b3421430109e2a19e1"
#     resource_id = "bc486650-6a75-450b-8012-78d9ed987da1"
#     url = f"https://api.data.gov.in/resource/{resource_id}?api-key={API_KEY}&format=json"
    
#     try:
#         response = requests.get(url, timeout=5)
#         data = response.json()
#         if data.get('records'):
#             for record in data['records']:
#                 if record.get('commodity', '').lower() in api_crop_name.lower():
#                     return record['modal_price']
#             return data['records'][0]['modal_price']
#         return None
#     except:
#         return None
# def get_live_climate(city):
#     API_KEY = "431ecadc055a1b3b113f33f7e74e221f"
#     url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&cachebust={time.time()}" 
#     # url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
#     try:
#         response = requests.get(url, timeout=5)
#         data = response.json()
#         if data.get("cod") != 200:
#             return None  # No more fake data!
#         return data
#     except:
#         return None

# # 4. DATA MODELS
# class SoilData(BaseModel):
#     Nitrogen: float
#     phosphorus: float
#     potassium: float
#     temperature: float
#     humidity: float
#     ph: float
#     rainfall: float

# # 5. ROUTES
# @app.get("/", response_class=HTMLResponse)
# async def home(request: Request):
#     return templates.TemplateResponse("index.html", {"request": request})

# @app.post("/predict")
# async def predict_crop(data: SoilData):
#     try:
#         # STEP 1: VALIDATION GATEKEEPER (Move this to the TOP)
#         if not (0 <= data.Nitrogen <= 140):
#             return {"error": "Nitrogen must be between 0 and 140."}
        
#         if not (5 <= data.phosphorus <= 145):
#             return {"error": "Phosphorous must be between 5 and 145."}
            
#         if not (5 <= data.potassium <= 205):
#             return {"error": "Potassium must be between 5 and 205."}
            
#         if not (10 <= data.temperature <= 50):
#             return {"error": "Temperature must be between 10°C and 50°C."}
            
#         if not (15 <= data.humidity <= 100):
#             return {"error": "Humidity must be between 15% and 100%."}
            
#         if not (3.5 <= data.ph <= 9.0):
#             return {"error": "Soil pH must be between 3.5 and 9.0."}
            
#         if not (20 <= data.rainfall <= 300):
#             return {"error": "Rainfall must be between 20mm and 300mm."}

#         # STEP 2: PREDICTION LOGIC (Only runs if Step 1 passes)
#         cols = ['Nitrogen', 'phosphorus', 'potassium', 'temperature', 'humidity', 'ph', 'rainfall']
#         input_df = pd.DataFrame([[
#             data.Nitrogen, data.phosphorus, data.potassium, 
#             data.temperature, data.humidity, data.ph, data.rainfall
#         ]], columns=cols)
        
#         scaled_data = scaler.transform(input_df)
#         crop_name = model.predict(scaled_data)[0].lower()
        
#         # STEP 3: DATA RETRIEVAL
#         info = crop_intelligence.get(crop_name, {'growth': 120, 'sell_month': 'Unknown', 'price': 3000, 'life': 30, 'type': 'grain'})
#         live_price = get_live_mandi_price(crop_name)
        
#         # STEP 4: ALERT LOGIC
#         if info['type'] == 'fruit' and data.humidity > 70:
#             alert = f"CRITICAL: Move to cold storage within {round(info['life']*0.2, 1)} days."
#             status_ui = "danger"
#         elif data.humidity > 80:
#             alert = f"WARNING: High moisture. Move to dry storage within {round(info['life']*0.4, 1)} days."
#             status_ui = "warning"
#         else:
#             alert = f"STABLE: Produce is safe for {info['life']} days post-harvest."
#             status_ui = "success"

#         # STEP 5: RETURN CLEAN DATA
#         return {
#             "crop": crop_name.upper(),
#             "status": "success",
#             "sowing": f"Feasible now. Harvest in {info['growth']} days.",
#             "price": live_price if live_price else info['price'],
#             "growth_time": info['growth'],
#             "sell_month": info['sell_month'],
#             "alert": alert,
#             "ui_status": status_ui # Renamed to avoid confusion with "status": "success"
#         }
        
#     except Exception as e:
#         print(f"Prediction Error: {e}")
#         return {"error": "Internal server error. Check input format."}

# # @app.post("/lifecycle-advice")
# # async def get_lifecycle_plan(city: str, crop: str, sowing_date: str):
# #     weather = get_live_climate(city)
    
# #     temp = weather['main']['temp']
# #     humidity = weather['main']['humidity']
# #     condition = weather['weather'][0]['main'].lower()


# @app.post("/lifecycle-advice")
# async def get_lifecycle_plan(city: str, crop: str, sowing_date: str):
#     # 1. Fetch live weather data
#     weather = get_live_climate(city)
#     if not weather or weather.get("cod") != 200:
#         return {"error": f"City '{city}' not found."}

#     # 2. CROP GATEKEEPER & DATA RETRIEVAL
#     crop_key = crop.lower()
#     if crop_key not in crop_intelligence:
#         return {"error": f"Crop '{crop}' not found in our database. Please select from the list."}

#     crop_info = crop_intelligence[crop_key]
#     target_growth = crop_info['growth']
    
#     temp = weather['main']['temp']
#     humidity = weather['main']['humidity']
#     condition = weather['weather'][0]['main'].lower()
#     current_month = datetime.now().month

#     # 3. DATE & PROGRESS CALCULATION
#     try:
#         sowing = datetime.strptime(sowing_date, "%Y-%m-%d")
#         now = datetime.now()
#         age_days = (now - sowing).days
        
#         if age_days < 0:
#             return {"error": "⚠️ Error: Sowing date cannot be in the future."}
        
#         progress = (age_days / target_growth) * 100
#     except ValueError:
#         return {"error": "Invalid date format."}

#     # 4. MODIFIED ADVICE LOGIC (Combining all features)

#     # FEATURE: OVERDUE CHECK
#     if age_days > (target_growth + 30):
#         advice = f"❌ OVERDUE: This {crop} was due for harvest {age_days - target_growth} days ago! Quality is likely degraded. Harvest immediately for animal feed or composting."

#     # FEATURE: SEASON CHECK
#     elif current_month not in crop_info['sowing_months'] and age_days < 15:
#         advice = f"⚠️ SEASON MISMATCH: {crop.capitalize()} is not usually sown in {datetime.now().strftime('%B')}. COPE: Use shade nets and organic mulch."

#     # FEATURE: HEAT CHECK
#     elif temp > crop_info['max_temp']:
#         advice = f"⚠️ HEAT STRESS: {temp}°C is too hot for {crop}! COPE: Increase irrigation in the evening and apply mulch."

#     # FEATURE: COLD CHECK
#     elif temp < crop_info['min_temp']:
#         advice = f"⚠️ COLD STRESS: {temp}°C is too cold! COPE: Cover seedlings with plastic sheets/straw to trap heat."

#     # FEATURE: HARVEST WINDOW (Weather-aware)
#     elif age_days >= target_growth:
#         if "rain" in condition or humidity > 75:
#             advice = f"🚨 WEATHER ALERT: {crop} is ready, but current humidity ({humidity}%) is too high. Risk of fungal rot. Wait 48 hours for dry weather."
#         else:
#             advice = f"✅ OPTIMAL HARVEST: Weather in {city} is dry. Harvest now to ensure maximum market price of ₹{crop_info['price']}/quintal."

#     # FEATURE: GROWTH STAGES
#     else:
#         if progress < 30:
#             advice = f"🌱 SEEDLING: {crop} is establishing roots. Current temp {temp}°C is ideal. Maintain soil moisture."
#         else:
#             advice = f"🌿 GROWTH: {crop} is {round(progress)}% through its cycle. Apply Nitrogen-based fertilizer before the next rain."

#     return {
#         "current_weather": f"{temp}°C, {condition.capitalize()}",
#         "advice": advice,
#         "days_old": age_days,
#         "progress": round(progress, 1) if progress < 100 else 100
#     }



# class LoginData(BaseModel):
#     username: str
#     password: str


# @app.post("/login")
# async def login(data: LoginData):
#     conn = sqlite3.connect("farm.db")
#     cursor = conn.cursor()
    
#     # Securely check for the user
#     cursor.execute("SELECT farmer_name FROM users WHERE username = ? AND password = ?", 
#                    (data.username, data.password))
#     user = cursor.fetchone()
#     conn.close()

#     if user:
#         return {
#             "status": "success", 
#             "message": "Access Granted", 
#             "farmer_name": user[0]
#         }
#     else:
#         return {"status": "error", "message": "Invalid Farmer ID or Password"}
    
# class RegisterData(BaseModel):
#     username: str
#     password: str
#     farmer_name: str

# @app.post("/register")
# async def register(data: RegisterData):
#     try:
#         conn = sqlite3.connect("farm.db")
#         cursor = conn.cursor()
#         # Insert new farmer
#         cursor.execute("INSERT INTO users (username, password, farmer_name) VALUES (?, ?, ?)", 
#                        (data.username, data.password, data.farmer_name))
#         conn.commit()
#         conn.close()
#         return {"status": "success", "message": "Farmer registered successfully!"}
#     except sqlite3.IntegrityError:
#         return {"status": "error", "message": "Farmer ID already exists!"}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}
# # This MUST come before the @app.post("/chat") line
# class ChatRequest(BaseModel):
#     message: str  
# @app.post("/chat")
# async def chat_with_ai(data: ChatRequest):
#     # System instructions to keep the AI focused
#     system_prompt = """
#     You are 'FarmCopilot Assistant'. 
#     - You help with soil NPK results (like the Rice recommendation seen on the dashboard).
#     - You provide weather-based advice for crops in India.
#     - If a farmer asks 'How to grow rice?', give them 3 clear steps.
#     - Keep answers under 100 words.
#     """
    
#     try:
#         # We combine the system prompt with the farmer's actual question
#         response = ai_model.generate_content(f"{system_prompt}\n\nFarmer asks: {data.message}")
#         return {"reply": response.text}
#     except Exception as e:
#         print(f"AI Error: {e}") # This prints the real error in your VS Code terminal
#         return {"reply": "I'm having trouble connecting to my brain. Please check the API key!"}