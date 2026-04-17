import os
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.session import create_user_session, get_current_user
from passlib.context import CryptContext
import requests
import shutil
from app.ai.diseasepredict import predict_disease
from app.ai.soil_predict import predict_soil
from app.database import get_db, engine
from app import models
from app.models import User
from typing import Optional
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends
from app.models import Tool    
from datetime import datetime   
from app.models import Notification, NotificationView
# Get the project root (N:\KaresaBari)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = FastAPI(title="KaresaBari")

# ---------------------------------
# MIDDLEWARE
# ---------------------------------
app.add_middleware(
    SessionMiddleware,
    secret_key="karesabari_secret_key_123"
)

# ---------------------------------
# WEATHER API CONFIG
# ---------------------------------
WEATHER_API_KEY = "355c67e3e68a25b1156c13be3b922faf"
CITY = "Kathmandu"

# ---------------------------------
# DATABASE SETUP
# ---------------------------------
models.Base.metadata.create_all(bind=engine)

# ---------------------------------
# PASSWORD HASHING
# ---------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password.strip()[:72])

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password.strip()[:72], hashed_password)

# ---------------------------------
# Admin Password
# ---------------------------------
hashed_pw = hash_password("Sam@707stha")
print(hashed_pw)
# ---------------------------------
# STATIC FILES
# ---------------------------------
# Ensure uploads directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/css", StaticFiles(directory=os.path.join(BASE_DIR, "css")), name="css")
app.mount("/public", StaticFiles(directory=os.path.join(BASE_DIR, "public")), name="public")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Get absolute path to storelocation inside pages
current_dir = os.path.dirname(os.path.realpath(__file__))  # app/
project_root = os.path.abspath(os.path.join(current_dir, ".."))  # N:\KaresaBari
storelocation_path = os.path.join(project_root, "pages", "storelocation")

# Check if it exists
if not os.path.isdir(storelocation_path):
    raise RuntimeError(f"Directory '{storelocation_path}' does not exist! Check your folder.")
else:
    app.mount("/storelocation", StaticFiles(directory=storelocation_path), name="storelocation")
    print(f"✅ Mounted storelocation at: {storelocation_path}")

# ---------------------------------
# TEMPLATES
# ---------------------------------
# Templates folder path
templates_path = os.path.join(BASE_DIR, "pages")
templates = Jinja2Templates(directory=templates_path)

# ---------------------------------
# WEATHER ROUTE
# ---------------------------------
@app.get("/weather")
def get_weather():
    url = f"https://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={WEATHER_API_KEY}&units=metric"
    
    try:
        response = requests.get(url)
        data = response.json()

        if data.get("cod") != 200:
            return JSONResponse({"error": "Invalid weather data"}, status_code=400)

        weather_main = data["weather"][0]["main"].lower()

        return {
            "city": CITY,
            "temperature": data["main"]["temp"],
            "humidity": data["main"]["humidity"],
            "condition": data["weather"][0]["main"],
            "description": data["weather"][0]["description"],
            "rain": "rain" in weather_main   # ✅ NEW (very important)
        }

    except Exception:
        return JSONResponse({"error": "Weather fetch failed"}, status_code=500)

# ---------------------------------
# ROUTES (PAGES)
# ---------------------------------
@app.get("/", response_class=HTMLResponse)
def landing_page(request: Request):
    return templates.TemplateResponse("auth/landing.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})

# 1. SHOW THE PAGE
@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse("auth/forgot-password.html", {"request": request})

# 2. PROCESS THE EMAIL
@app.post("/forgot-password")
def handle_forgot_password(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return templates.TemplateResponse("auth/forgot-password.html", {
            "request": request, 
            "error": "This email is not registered with us! ⚠️"
        })
    # If user exists, send them to the reset page
    return templates.TemplateResponse("auth/reset-password.html", {
        "request": request, 
        "email": email
    })

# 3. UPDATE THE PASSWORD
@app.post("/reset-password")
def handle_reset_password(
    request: Request, 
    email: str = Form(...), 
    new_password: str = Form(...), 
    confirm_password: str = Form(...), 
    db: Session = Depends(get_db)
):
    if new_password != confirm_password:
        return templates.TemplateResponse("auth/reset-password.html", {
            "request": request, "email": email, "error": "Passwords do not match! ⚠️"
        })
    
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.hashed_password = hash_password(new_password)
        db.commit()
        return templates.TemplateResponse("auth/login.html", {
            "request": request, 
            "success": "Password reset successfully! Log in now. 🌿"
        })
    return RedirectResponse("/login")

# ---------------------------------
# REGISTER (AUTH)
# ---------------------------------
@app.post("/register")
def register_user(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    if password != confirm_password:
        return templates.TemplateResponse("auth/register.html", {
            "request": request, 
            "error": "Passwords do not match! ⚠️"
        })

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return templates.TemplateResponse("auth/register.html", {
            "request": request, 
            "error": "Email already registered! ⚠️"
        })

    user = User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return RedirectResponse(url="/login", status_code=303)

# ---------------------------------
# LOGIN (AUTH)
# ---------------------------------
    
@app.post("/login")
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.hashed_password):
    # This re-renders the login page and sends the 'error' variable to your popup logic
        return templates.TemplateResponse("auth/login.html", {
            "request": request, 
            "error": "Invalid email or password! ⚠️"
        })

    # ✅ ADD THIS PART (VERY IMPORTANT)
    user.last_login = datetime.utcnow()
    db.commit()

    # Create session
    create_user_session(request, user)

    # Redirect based on admin flag
    if user.is_admin:
        return RedirectResponse(url="/admin/analytics", status_code=303)
    else:
        return RedirectResponse(url="/mygarden", status_code=303)
# ---------------------------------
# For dependency 
# ---------------------------------
from fastapi import HTTPException

def admin_required(request: Request, db: Session = Depends(get_db)):
    email = request.session.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Login required")

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
# ---------------------------------
# Analystics 
# ---------------------------------
from sqlalchemy import func
from datetime import datetime, timedelta

@app.get("/admin/analytics", response_class=HTMLResponse)
def admin_analytics(request: Request, db: Session = Depends(get_db), user: User = Depends(admin_required)):
    # --- 1. REAL 7-DAY HISTORY LOGIC ---
    chart_labels = []
    chart_data = []
    now = datetime.utcnow()

    for i in range(6, -1, -1):
        # Calculate the date for each of the last 7 days
        target_date = (now - timedelta(days=i)).date()
        chart_labels.append(target_date.strftime("%a")) # Mon, Tue, etc.

        # Count Soil Scans for this specific day
        soil_count = db.query(models.SoilHistory).filter(
            func.date(models.SoilHistory.created_at) == target_date
        ).count()

        # Count Disease Scans for this specific day
        disease_count = db.query(models.DiseaseHistory).filter(
            func.date(models.DiseaseHistory.created_at) == target_date
        ).count()

        # Total interactions for that day
        chart_data.append(soil_count + disease_count)

    # --- 2. REAL AI ACCURACY ---
    # Average confidence from SoilHistory
    avg_conf = db.query(func.avg(models.SoilHistory.confidence)).scalar() or 0
    ai_accuracy = round(float(avg_conf), 1) if avg_conf > 0 else 85.0

    # --- 3. BASIC STATS ---
    total_users = db.query(User).count()
    soil_scans = db.query(models.SoilHistory).count()
    disease_scans = db.query(models.DiseaseHistory).count()
    active_crops = db.query(models.MyGarden).count()

    stats = {
        "total_users": total_users,
        "soil_scans": soil_scans,
        "disease_scans": disease_scans,
        "active_crops": active_crops,
        "total_interactions": soil_scans + disease_scans + active_crops,
        "ai_accuracy": ai_accuracy,
        "chart_labels": chart_labels,
        "chart_data": chart_data
    }

    # --- 4. RECENT ACTIVITY TABLE ---
    recent_soil = db.query(models.SoilHistory).order_by(models.SoilHistory.id.desc()).limit(3).all()
    
    # Process Disease JSON results for the table
    raw_disease = db.query(models.DiseaseHistory).order_by(models.DiseaseHistory.id.desc()).limit(3).all()
    processed_disease = []
    for d in raw_disease:
        try:
            res = json.loads(d.result)
            processed_disease.append({
                "name": res.get("disease", "Unknown"),
                "confidence": res.get("confidence", 0),
                "created_at": d.created_at
            })
        except:
            processed_disease.append({"name": "Plant Scan", "confidence": 0, "created_at": d.created_at})

    return templates.TemplateResponse("admin/analytics.html", {
        "request": request,
        "username": user.full_name,
        "stats": stats,
        "recent_soil": recent_soil,
        "recent_disease": processed_disease
    })
@app.get("/admin/toolsmanagement", response_class=HTMLResponse)
def admin_tools(request: Request, page: int = 1, db: Session = Depends(get_db), user: User = Depends(admin_required)):
    limit = 5
    offset = (page - 1) * limit

    tools = db.query(models.Tool).offset(offset).limit(limit).all()
    total = db.query(models.Tool).count()

    return templates.TemplateResponse("admin/toolsmanagement.html", {
        "request": request,
        "tools": tools,
        "page": page,
        "total_pages": (total // limit) + 1
    })
# ---------------------------------
# User PAGE
# ---------------------------------
from datetime import datetime, timedelta

@app.get("/admin/user", response_class=HTMLResponse)
def admin_users(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(admin_required)
):
    users = db.query(User).order_by(User.is_admin.desc(), User.full_name.asc()).all()

    now = datetime.utcnow()

    total_users = len(users)

    active_users = 0
    for u in users:
        if u.last_login and (now - u.last_login).days <= 15:
            active_users += 1

    return templates.TemplateResponse("admin/user.html", {
        "request": request,
        "users": users,
        "total_users": total_users,
        "active_users": active_users,
        "now": now
    })
# ---------------------------------
# User delete auth
# ---------------------------------
@app.post("/admin/delete-user/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required)
):
    user = db.query(User).filter(User.id == user_id).first()

    if user:
        if user.id == admin.id:
            return HTMLResponse("You cannot delete yourself", status_code=400)

        db.delete(user)
        db.commit()

    return RedirectResponse(url="/admin/user", status_code=303)
# ---------------------------------
# LOGOUT
# ---------------------------------
@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)

# ---------------------------------
# MyGarden
# ---------------------------------
from datetime import datetime

# --- main.py changes ---
@app.get("/mygarden", response_class=HTMLResponse)
def mygarden_page(request: Request, db: Session = Depends(get_db)):
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse("/login", status_code=303)

    user = db.query(models.User).filter(models.User.email == user_email).first()
    full_name = user.full_name if user else "Gardener"

    crops = db.query(models.MyGarden).filter(models.MyGarden.user_email == user_email).all()
    soil_count = db.query(models.SoilHistory).count()
    disease_count = db.query(models.DiseaseHistory).count()

    crop_list = []
    for c in crops:
        days_passed = (datetime.utcnow() - c.planted_at).days
        growth_days = c.growth_days or 30
        progress = int((days_passed / growth_days) * 100)
        progress = max(0, min(progress, 100))

        crop_list.append({
            "id": c.id, 
            "crop": c.crop,
            "image": c.image,
            "growth_days": growth_days,
            "days": days_passed,
            "progress": progress
        })

    # Update this part below:
    return templates.TemplateResponse("mygarden.html", {
        "request": request,
        "full_name": full_name,
        "crops": crop_list,
        "soil_count": soil_count,
        "disease_count": disease_count,
        "now": datetime.utcnow()  # <--- ADD THIS LINE HERE
    })

# 4. New Delete Route
@app.post("/delete-crop/{crop_id}")
def delete_crop(crop_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse("/login", status_code=303)

    crop = db.query(models.MyGarden).filter(
        models.MyGarden.id == crop_id, 
        models.MyGarden.user_email == user_email
    ).first()

    if crop:
        db.delete(crop)
        db.commit()

    return RedirectResponse("/mygarden", status_code=303)
# ---------------------------------
# SOIL ANALYSIS PAGE
# ---------------------------------
@app.get("/soilanalysis", response_class=HTMLResponse)
def soil_analysis_page(request: Request):
    return templates.TemplateResponse("soilanalysis.html", {"request": request})

# ---------------------------------
# RECOMMENDATION PAGE
# ---------------------------------
@app.get("/recommendation", response_class=HTMLResponse)
def recommendation_page(request: Request):
    return templates.TemplateResponse("recommendation.html", {"request": request})

# ---------------------------------
# DISEASE PAGE
# ---------------------------------
@app.get("/disease", response_class=HTMLResponse)
def disease_page(request: Request, db: Session = Depends(get_db)):
    # Check for the latest scan in history
    latest = db.query(models.DiseaseHistory).order_by(models.DiseaseHistory.id.desc()).first()
    
    # If a scan exists, redirect to its report so it doesn't disappear
    if latest:
        return RedirectResponse(f"/disease/report/{latest.id}", status_code=303)

    # If no scans at all, show empty page
    return templates.TemplateResponse("disease.html", {
        "request": request,
        "result": None,
        "history": []
    })

# ---------------------------------
# TOOLS PAGE
# ---------------------------------
@app.get("/tools", response_class=HTMLResponse)
def tools_page(request: Request, db: Session = Depends(get_db)):
    tools = db.query(models.Tool).all()   # 👈 fetch tools from DB

    return templates.TemplateResponse("tools.html", {
        "request": request,
        "tools": tools   # 👈 send to frontend
    })

# ---------------------------------
# ABOUT US
# ---------------------------------
@app.get("/aboutus", response_class=HTMLResponse)
def aboutus_page(request: Request):
    return templates.TemplateResponse("aboutus.html", {"request": request})

# ---------------------------------
# DASHBOARD
# ---------------------------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse("<h1>Login Successful </h1><p>Welcome to KaresaBari</p>")

@app.get("/header", response_class=HTMLResponse)
def header_preview(request: Request):
    return templates.TemplateResponse("components/header.html", {"request": request})


# ---------------------------------
# PROFILE PAGE
# ---------------------------------
# --- Updated Profile Route ---
@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_db)):
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse("/login", status_code=303)

    user = db.query(User).filter(User.email == user_email).first()
    
    # 1. Calculate Dynamic Stats
    # Count total crops this user has added
    total_crops = db.query(models.MyGarden).filter(models.MyGarden.user_email == user_email).count()
    
    # Count soil reports and disease checks
    soil_reports = db.query(models.SoilHistory).count() # You might want to filter by user if your model supports it
    health_checks = db.query(models.DiseaseHistory).count()
    
    # 2. Determine Garden Status
    garden_status = "Thriving" if total_crops > 2 else "Getting Started"
    
    # 3. Format "Member Since" (Assuming your User model has a created_at field)
    # If your model doesn't have created_at, it will fallback to "Joined Recently"
    member_since = "Joined Recently"
    if hasattr(user, 'created_at') and user.created_at:
        member_since = user.created_at.strftime("%B %Y")
    elif user.id < 10: # Just as a fallback example logic
        member_since = "Early Adopter"

    profile_image = request.session.get("profile_image") or "default.png"

    return templates.TemplateResponse("profile.html", {
        "request": request, 
        "user": user, 
        "profile_image": profile_image,
        "total_crops": total_crops,
        "soil_reports": soil_reports,
        "health_checks": health_checks,
        "garden_status": garden_status,
        "member_since": member_since
    })

@app.post("/profile/update")
async def update_profile(
    request: Request,
    full_name: str = Form(...),
    new_password: str = Form(None),
    confirm_password: str = Form(None),
    db: Session = Depends(get_db)
):
    user_email = request.session.get("user_email")
    user = db.query(User).filter(User.email == user_email).first()

    # 1. Handle Password Logic
    if new_password:
        if new_password != confirm_password:
            # REDIRECT WITH ERROR PARAM
            return RedirectResponse("/profile?error=password_mismatch", status_code=303)
        
        user.hashed_password = hash_password(new_password)

    # 2. Update Name
    user.full_name = full_name
    db.commit()

    # REDIRECT WITH SUCCESS PARAM
    return RedirectResponse("/profile?msg=password_success", status_code=303)

# ---------------------------------
# DISEASE DETECTION POST
# ---------------------------------
import json # Add this at the top of main.py

# --- 1. VIEW OLD REPORT ---
@app.get("/disease/report/{report_id}", response_class=HTMLResponse)
def view_disease_report(report_id: int, request: Request, db: Session = Depends(get_db)):
    report = db.query(models.DiseaseHistory).filter(models.DiseaseHistory.id == report_id).first()
    if not report:
        return RedirectResponse("/disease", status_code=303)
    
    # Reconstruct the result dictionary from the stored string
    # We use try/except in case old data isn't in JSON format
    try:
        result_data = json.loads(report.result)
    except:
        # Fallback for old records
        result_data = {"plant": "Unknown", "disease": report.result, "confidence": 0, "severity": 1}

    history = db.query(models.DiseaseHistory).order_by(models.DiseaseHistory.id.desc()).all()
    
    return templates.TemplateResponse("disease.html", {
        "request": request,
        "result": result_data,
        "uploaded_file": report.image,
        "history": history
    })

# --- 2. DELETE REPORT ---
@app.post("/disease/delete/{report_id}")
def delete_disease_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(models.DiseaseHistory).filter(models.DiseaseHistory.id == report_id).first()
    if report:
        db.delete(report)
        db.commit()
    return RedirectResponse("/disease", status_code=303)

@app.post("/disease/upload")
async def upload_disease_image(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = predict_disease(file_path)

    # ERROR CHECK: If AI confidence is too low or plant is unknown
    if result.get("confidence", 0) < 30:
        return templates.TemplateResponse("disease.html", {
            "request": request,
            "error_msg": "Invalid Image: Please upload a clear photo of a plant leaf.",
            "history": db.query(models.DiseaseHistory).order_by(models.DiseaseHistory.id.desc()).all()
        })

    # Save full result as JSON string so we can re-load severity/roadmap later
    new_entry = models.DiseaseHistory(
        result=json.dumps(result),
        image=file.filename
    )
    db.add(new_entry)
    db.commit()

    return RedirectResponse(f"/disease/report/{new_entry.id}", status_code=303)
# ---------------------------------
# SOIL PREDICTION POST
# ---------------------------------
@app.post("/predict-soil")
async def predict_soil_api(file: UploadFile = File(...), db: Session = Depends(get_db)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    soil, confidence = predict_soil(file_path)

    # --- NEW: Check if it's actually soil ---
    # If confidence is too low, we return the result but DON'T save to database
    if confidence < 40:
        return {"soil": "Unknown / Not Soil", "confidence": confidence, "image": file_path, "is_valid": False}

    # If it is valid soil, save it
    new_entry = models.SoilHistory(soil_type=soil, confidence=confidence, image_path=file_path)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    return {"id": new_entry.id, "soil": soil, "confidence": confidence, "image": file_path, "is_valid": True}

@app.get("/soil-history")
def get_soil_history(db: Session = Depends(get_db)):
    history = db.query(models.SoilHistory).order_by(models.SoilHistory.id.desc()).all()
    return [{"id": item.id, "soil": item.soil_type, "confidence": item.confidence, "image": item.image_path} for item in history]

@app.delete("/soil-history/{item_id}")
def delete_soil_history(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.SoilHistory).filter(models.SoilHistory.id == item_id).first()
    if not item:
        return JSONResponse({"error": "Item not found"}, status_code=404)
    
    # Optional: Delete the file from the disk
    if os.path.exists(item.image_path):
        os.remove(item.image_path)
        
    db.delete(item)
    db.commit()
    return {"message": "Deleted successfully"}
# ---------------------------------
# tools POST
# ---------------------------------
@app.post("/admin/add-tool")
async def add_tool(
    name: str = Form(...),
    store_name: str = Form(...),
    location: str = Form(...),
    description: str = Form(...),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db)
):
    if not image or image.filename == "":
        # Friendly HTML alert
        return HTMLResponse("""
            <script>
                alert("Please upload a photo of the tool before adding!");
                window.history.back();
            </script>
        """)
    
    # Save image
    file_path = f"uploads/{image.filename}"
    with open(file_path, "wb") as f:
        f.write(await image.read())
    
    # Save to DB
    new_tool = Tool(
        name=name,
        store_name=store_name,
        location=location,
        description=description,
        image=image.filename
    )
    db.add(new_tool)
    db.commit()
    return RedirectResponse("/admin/toolsmanagement", status_code=303)

@app.post("/admin/delete-tool/{tool_id}")
def delete_tool(tool_id: int, db: Session = Depends(get_db), user: User = Depends(admin_required)):
    tool = db.query(models.Tool).filter(models.Tool.id == tool_id).first()

    if tool:
        db.delete(tool)
        db.commit()

    return RedirectResponse(url="/admin/toolsmanagement", status_code=303)

@app.get("/admin/edit-tool/{tool_id}", response_class=HTMLResponse)
def edit_tool_page(tool_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(admin_required)):
    tool = db.query(models.Tool).filter(models.Tool.id == tool_id).first()

    return templates.TemplateResponse("admin/edit_tool.html", {
        "request": request,
        "tool": tool
    })

@app.post("/admin/edit-tool/{tool_id}")
async def edit_tool(
    tool_id: int,
    name: str = Form(...),
    store_name: str = Form(...),
    location: str = Form(...),
    description: str = Form(...),
    image: UploadFile | None = File(None),  # Optional image
    db: Session = Depends(get_db)          # Inject DB session
):
    # Get the tool from the database
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        return RedirectResponse("/admin/toolsmanagement", status_code=303)

    # Update fields
    tool.name = name
    tool.store_name = store_name
    tool.location = location
    tool.description = description

    # Only update the image if a new file is uploaded
    if image and image.filename != "":
        file_path = f"uploads/{image.filename}"
        with open(file_path, "wb") as f:
            f.write(await image.read())
        tool.image = image.filename

    # Commit changes to database
    db.commit()

    return RedirectResponse("/admin/toolsmanagement", status_code=303)

# ---------------------------------
# Notification
# ---------------------------------
from pytz import timezone
@app.get("/admin/notification", response_class=HTMLResponse)
def notification_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(admin_required)
):
    # 🔥 Call weather check
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(url).json()

        if "rain" in response.get("weather")[0]["main"].lower():
            message = f"Rain expected in {CITY}: {response['weather'][0]['description']}."

            db.add(Notification(
                title="🌧️ Weather Alert",
                message=message,
                type="weather"
            ))
            db.commit()
    except:
        pass

    # Fetch notifications
    notifications = db.query(Notification).order_by(Notification.created_at.desc()).all()

    #  Convert timestamps to Nepal Time
    from pytz import timezone
    NEPAL_TZ = timezone("Asia/Kathmandu")
    for n in notifications:
        n.created_at = n.created_at.astimezone(NEPAL_TZ)

    # Send to template
    return templates.TemplateResponse("admin/notification.html", {
        "request": request,
        "notifications": notifications
    })
from app.models import Notification

@app.post("/send-notification")
def send_notification(
    title: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(admin_required)
):
    new_notif = Notification(
        title=title,
        message=message,
        type="user"
    )
    db.add(new_notif)
    db.commit()
    db.refresh(new_notif)

    return RedirectResponse("/admin/notification", status_code=303)

@app.get("/check-weather-notification")
def weather_notification(db: Session = Depends(get_db)):
    import requests
    url = f"https://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={WEATHER_API_KEY}&units=metric"
    response = requests.get(url).json()

    # Example: notify if rain expected
    if "rain" in response.get("weather")[0]["main"].lower():
        message = f"Rain expected in {CITY}: {response['weather'][0]['description']}."
        new_notif = Notification(title="🌧️ Weather Alert", message=message, type="weather")
        db.add(new_notif)
        db.commit()

    return {"status": "checked"}

from datetime import timedelta

@app.get("/notifications", response_class=JSONResponse)
def get_notifications(db: Session = Depends(get_db)):
    notifications = db.query(Notification).order_by(Notification.created_at.desc()).all()

    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime("%Y-%m-%d %H:%M")
        } for n in notifications
    ]

from datetime import datetime, timedelta
from app.models import Notification

def create_weather_notification(db: Session):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(url).json()
        weather_main = response.get("weather")[0]["main"].lower()

        if "rain" in weather_main:
            # check last weather notification
            last_notif = db.query(Notification)\
                .filter(Notification.type == "weather")\
                .order_by(Notification.created_at.desc()).first()

            now = datetime.utcnow()

            # create only if last alert was more than 1 hour ago
            if not last_notif or (now - last_notif.created_at) > timedelta(hours=1):
                message = f"Rain expected in {CITY}: {response['weather'][0]['description']}."
                new_notif = Notification(
                    title="🌧️ Weather Alert",
                    message=message,
                    type="weather"
                )
                db.add(new_notif)
                db.commit()
                print(f"[Weather Notification] Created at {now}")
    except Exception as e:
        print(f"[Weather Notification Error]: {e}")

from fastapi import BackgroundTasks

@app.on_event("startup")
def start_weather_task():
    import threading
    import time

    def run_weather_loop():
        while True:
            db = next(get_db())
            create_weather_notification(db)
            time.sleep(60 * 60)  # every 1 hour

    thread = threading.Thread(target=run_weather_loop, daemon=True)
    thread.start()
    
@app.post("/notifications/mark-read/{notification_id}")
def mark_notification_read(notification_id: int, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notification_id).first()

    if notif:
        notif.is_read = True
        db.commit()

    return {"status": "ok"}

@app.post("/admin/delete-notification/{id}")
def delete_notification(id: int, db: Session = Depends(get_db), user: User = Depends(admin_required)):
    notif = db.query(Notification).filter(Notification.id == id).first()

    if notif:
        db.delete(notif)
        db.commit()

    return RedirectResponse("/admin/notification", status_code=303)

@app.post("/notifications/view/{notification_id}")
def view_notification(notification_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = request.session.get("user_email")
    if not user_email:
        return {"status": "error", "msg": "Login required"}

    # check if this user already viewed this notification
    existing = db.query(NotificationView).filter(
        NotificationView.notification_id == notification_id,
        NotificationView.user_email == user_email
    ).first()

    if not existing:
        # create new view
        new_view = NotificationView(
            notification_id=notification_id,
            user_email=user_email
        )
        db.add(new_view)

        # increment total unique views
        notif = db.query(Notification).filter(Notification.id == notification_id).first()
        if notif:
            notif.views = (notif.views or 0) + 1

        db.commit()

    return {"status": "ok"}

@app.post("/notifications/click/{notif_id}")
def mark_notification_clicked(notif_id: int, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if notif:
        notif.click_rate = (notif.click_rate or 0) + 1
        db.commit()
    return {"status": "ok"}
# ---------------------------------
# Messages
# ---------------------------------
@app.get("/admin/messages", response_class=HTMLResponse)
def get_messages(request: Request, db: Session = Depends(get_db), filter: Optional[str] = None):
    query = db.query(models.ContactMessage).order_by(models.ContactMessage.created_at.desc())

    if filter == "unread":
        query = query.filter(models.ContactMessage.is_read == False)
    elif filter == "read":
        query = query.filter(models.ContactMessage.is_read == True)

    messages = query.all()

    return templates.TemplateResponse("admin/messages.html", {
        "request": request,
        "messages": messages,
        "filter": filter or "all"
    })
# ---------------------------------
# Contact Us
# ---------------------------------
@app.get("/contactus", response_class=HTMLResponse)
def contact_page(request: Request):
    return templates.TemplateResponse("contactus.html", {"request": request})


@app.post("/contact")
async def submit_contact(
    full_name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db)
):
    # Logic to save to database
    new_msg = models.ContactMessage(
        full_name=full_name,
        email=email,
        subject=subject,
        message=message
    )
    db.add(new_msg)
    db.commit()

    # REDIRECT BACK TO CONTACT PAGE WITH SUCCESS MESSAGE
    return RedirectResponse(url="/contactus?msg=sent", status_code=303)

@app.get("/admin/message/{msg_id}", response_class=HTMLResponse)
def view_message(msg_id: int, request: Request, db: Session = Depends(get_db)):
    # 1. Fetch the message from database
    msg = db.query(models.ContactMessage).filter(models.ContactMessage.id == msg_id).first()
    
    if not msg:
        return HTMLResponse("Message not found", status_code=404)

    # 2. Mark the message as read since the admin is now looking at it
    msg.is_read = True
    db.commit()

    # 3. Open the detail page
    # IMPORTANT: We use "message": msg so it matches the {{ message.xxx }} in your HTML
    return templates.TemplateResponse("admin/message_detail.html", {
        "request": request,
        "message": msg 
    })

@app.post("/reply/{msg_id}")
def reply_to_message(msg_id: int, reply: str = Form(...), db: Session = Depends(get_db)):
    msg = db.query(models.ContactMessage).filter(models.ContactMessage.id == msg_id).first()
    
    if msg:
        msg.reply = reply
        msg.is_replied = True
        db.commit()
    
    # Redirect back to the inbox after replying
    return RedirectResponse(url="/admin/messages", status_code=303)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
from app.ai.hybrid import predict_crop 
import os

def get_crop_image(crop_name: str):
    base_path = os.path.join(BASE_DIR, "static", "images")

    jpg_path = os.path.join(base_path, f"{crop_name}.jpg")
    webp_path = os.path.join(base_path, f"{crop_name}.webp")

    if os.path.exists(jpg_path):
        return f"/static/images/{crop_name}.jpg"
    elif os.path.exists(webp_path):
        return f"/static/images/{crop_name}.webp"
    else:
        return "/static/images/default.jpg"
    
@app.post("/recommend", response_class=HTMLResponse)
async def recommend(request: Request):
    form = await request.form()

    input_data = {
        "soil_type": form.get("soil_type", ""),
        "season": form.get("season", ""),
        "sunlight_hours": int(form.get("sunlight_hours") or 0),
        "climate_zone": form.get("climate_zone", ""),
        "temperature": float(form.get("temperature") or 25)
    }

    results = predict_crop(input_data)

    top3 = sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)[:3]

    formatted_results = []

    for r in top3:
        crop_name = r.get("crop").lower().strip()

        formatted_results.append({
            "crop": crop_name.title(),
            "image": get_crop_image(crop_name),
            "why": ", ".join(r.get("why", [])) if r.get("why") else "Good overall match for your conditions"
        })

    return templates.TemplateResponse("recommendation.html", {
        "request": request,
        "results": formatted_results
    })


from datetime import datetime, timedelta

def delete_old_notifications(db: Session):
    now = datetime.utcnow()
    cutoff = now - timedelta(days=1)

    old_notifications = db.query(Notification)\
        .filter(Notification.created_at < cutoff)\
        .all()

    for n in old_notifications:
        db.delete(n)

    db.commit()
import threading
import time

def run_weather_loop():
    while True:
        db = next(get_db())

        create_weather_notification(db)
        delete_old_notifications(db)

        time.sleep(60 * 60)  # every 1 hour

thread = threading.Thread(target=run_weather_loop, daemon=True)
thread.start()

@app.post("/start-growing/{crop_name}")
def start_growing(crop_name: str, request: Request, db: Session = Depends(get_db)):
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse("/login", status_code=303)

    new_crop = models.MyGarden(
        user_email=user_email,
        crop=crop_name.title(),   # ✅ Change 'crop_name=' to 'crop='
        image=get_crop_image(crop_name),
        growth_days=30,
        planted_at=datetime.utcnow() # Use the column name from your model
    )

    db.add(new_crop)
    db.commit()

    return RedirectResponse("/mygarden", status_code=303)

