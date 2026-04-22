import joblib
import pandas as pd
import numpy as np

# =========================
# LOAD MODEL
# =========================
model = joblib.load("app/ai/model.pkl")
columns = joblib.load("app/ai/columns.pkl")


# =========================
# RULE FILTER (soft logic)
# =========================
def rule_filter(climate_zone, season, sunlight_hours):

    crops = ["rice", "wheat", "maize", "potato", "tomato",
             "beans", "cucumber", "spinach", "lentil", "chili"]

    if sunlight_hours < 4:
        return ["potato", "spinach"]

    if season.lower() == "winter":
        return ["wheat", "lentil", "peas"]

    if climate_zone.lower() == "mountain":
        return ["potato", "barley", "millet"]

    return crops


# =========================
# EXPLAINABLE AI
# =========================
def explain_crop(input_data, crop):

    reasons = []

    soil = input_data.get("soil_type", "")
    season = input_data.get("season", "")
    temp = float(input_data.get("temperature") or 0)
    sunlight = float(input_data.get("sunlight_hours") or 0)
    zone = input_data.get("climate_zone", "")

    # 🌾 crop-specific logic
    if crop == "rice":
        if soil == "Alluvial_Soil":
            reasons.append("Best soil for rice")
        if season in ["monsoon", "summer"]:
            reasons.append("Ideal growing season")

    elif crop == "chili":
        if temp > 20:
            reasons.append("Needs warm temperature")
        if season == "summer":
            reasons.append("Grows well in summer")

    elif crop == "cucumber":
        if temp > 20:
            reasons.append("Prefers warm climate")
        if sunlight >= 5:
            reasons.append("Needs good sunlight")

    elif crop == "wheat":
        if season == "winter":
            reasons.append("Best grown in winter")

    elif crop == "potato":
        if zone == "Mountain":
            reasons.append("Prefers cooler regions")

    elif crop == "beans":
        if soil in ["Arid_Soil", "Red_Soil"]:
            reasons.append("Suitable soil for beans")

    # 🌞 general fallback (only if empty)
    if not reasons:
        if sunlight >= 5:
            reasons.append("Enough sunlight")
        if temp > 18:
            reasons.append("Good temperature")

    return reasons


# =========================
# MAIN PREDICTION FUNCTION
# =========================
def predict_crop(input_data):

    # -------------------------
    # 1. Prepare input
    # -------------------------
    df = pd.DataFrame([input_data])
    df = pd.get_dummies(df)
    df = df.reindex(columns=columns, fill_value=0)

    # -------------------------
    # 2. Predict probabilities
    # -------------------------
    probs = model.predict_proba(df)[0]
    classes = model.classes_   # ✅ FIXED

    # 🔥 smoothing (fix 1.0 issue)
    probs = probs ** 0.2   # 🔥 strong smoothing
    probs = probs / probs.sum()

    # -------------------------
    # 3. Build results
    # -------------------------
    results = []

    for i, crop in enumerate(classes):
        results.append({
            "crop": crop,
            "confidence": round(float(probs[i]), 4),
            "why": explain_crop(input_data, crop)
        })

    # -------------------------
    # 4. SORT FIRST
    # -------------------------
    results = sorted(results, key=lambda x: x["confidence"], reverse=True)

    # -------------------------
    # 5. SOFT RULE BOOST (NOT FILTER ❗)
    # -------------------------
    allowed = rule_filter(
        input_data.get("climate_zone", ""),
        input_data.get("season", ""),
        float(input_data.get("sunlight_hours") or 0)
    )

    for r in results:
        if r["crop"] in allowed:
            r["confidence"] += 0.05 # boost good crops

    # normalize again after boost
    total = sum(r["confidence"] for r in results)
    for r in results:
        r["confidence"] = round(r["confidence"] / total, 4)

    # -------------------------
    # 6. FINAL SORT + TOP 3
    # -------------------------
    results = sorted(results, key=lambda x: x["confidence"], reverse=True)

    return results[:3]