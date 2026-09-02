"""
routers/predict.py

POST /api/predict
  - Accepts structured usage data
  - Runs feature engineering
  - Loads trained Random Forest model (models/rf_model.pkl)
  - Falls back to rule-based logic if model file not found
  - Returns score, risk level, alerts, and recommendations
"""

import os
import math
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# ── Lazy-load ML model (loaded once on first request) ─────────────────
_model  = None
_scaler = None
_le     = None

def _load_model():
    global _model, _scaler, _le
    if _model is not None:
        return True
    try:
        import joblib
        base = Path(__file__).parent.parent.parent / "models"
        _model  = joblib.load(base / "rf_model.pkl")
        _scaler = joblib.load(base / "scaler.pkl")
        _le     = joblib.load(base / "label_encoder.pkl")
        return True
    except Exception:
        return False


# ── Input schema ──────────────────────────────────────────────────────
class AppInput(BaseModel):
    name: str
    minutes: int
    category: str
    color: Optional[str] = None


class PredictRequest(BaseModel):
    date: str
    total_minutes: int
    apps: list[AppInput]
    weekly_data: Optional[list[dict]] = None


# ── Output schema ─────────────────────────────────────────────────────
class FeatureSet(BaseModel):
    total_daily_screen_time: int
    social_media_minutes: int
    social_media_ratio: float
    productivity_ratio: float
    top_app_name: str
    top_app_minutes: int
    entertainment_minutes: int
    app_count: int
    top_app_ratio: float


class Prediction(BaseModel):
    health_score: int
    addiction_risk_score: int
    risk_level: str
    risk_label: str
    risk_color: str
    classification_confidence: float
    model_used: str
    features: FeatureSet
    cluster: int
    cluster_name: str
    alerts: list[dict]
    recommendations: list[dict]


# ── Feature Engineering ───────────────────────────────────────────────
def extract_features(req: PredictRequest) -> FeatureSet:
    total = req.total_minutes or 1
    apps  = req.apps

    social_mins        = sum(a.minutes for a in apps if a.category == "social_media")
    productivity_mins  = sum(a.minutes for a in apps if a.category == "productivity")
    entertainment_mins = sum(a.minutes for a in apps if a.category == "entertainment")

    top = sorted(apps, key=lambda a: a.minutes, reverse=True)
    top = top[0] if top else AppInput(name="Unknown", minutes=0, category="other")

    return FeatureSet(
        total_daily_screen_time=total,
        social_media_minutes=social_mins,
        social_media_ratio=round(social_mins / total, 3),
        productivity_ratio=round(productivity_mins / total, 3),
        top_app_name=top.name,
        top_app_minutes=top.minutes,
        entertainment_minutes=entertainment_mins,
        app_count=len(apps),
        top_app_ratio=round(top.minutes / total, 3),
    )


# ── ML model classification ───────────────────────────────────────────
def classify_ml(features: FeatureSet):
    import numpy as np

    X = [[
        features.total_daily_screen_time,
        features.social_media_minutes,
        max(0, features.total_daily_screen_time
            - features.social_media_minutes
            - features.entertainment_minutes),
        features.entertainment_minutes,
        round(features.top_app_minutes / max(features.total_daily_screen_time, 1), 3),
        features.social_media_ratio,
        features.productivity_ratio,
        features.app_count,
    ]]

    X_sc  = _scaler.transform(X)
    label = _le.inverse_transform(_model.predict(X_sc))[0]
    proba = _model.predict_proba(X_sc)[0].max()

    health_map = {"healthy": 80, "moderate": 55, "high": 25}
    base_score = health_map.get(label, 50)

    sr = features.social_media_ratio
    offset = int((0.5 - sr) * 20)
    score = max(5, min(100, base_score + offset))

    addiction = min(100, int((100 - score) * 1.1))
    return score, addiction, label, round(float(proba), 3)


# ── Rule-based fallback ───────────────────────────────────────────────
def classify_rules(features: FeatureSet):
    score = 100
    sr = features.social_media_ratio
    if sr > 0.6:    score -= 35
    elif sr > 0.4:  score -= 22
    elif sr > 0.25: score -= 10

    t = features.total_daily_screen_time
    if t > 480:   score -= 25
    elif t > 360: score -= 15
    elif t > 240: score -= 8

    score += round(features.productivity_ratio * 15)
    score = max(5, min(100, score))

    addiction = min(100, int((100 - score) * 1.1))

    if score >= 70:   level = "healthy"
    elif score >= 45: level = "moderate"
    else:             level = "high"

    confidence = 0.75 + abs(score - 50) / 50 * 0.20
    return score, addiction, level, round(confidence, 3)


# ── Alert generation ──────────────────────────────────────────────────
def generate_alerts(features: FeatureSet, risk_level: str) -> list[dict]:
    alerts = []
    social_pct = round(features.social_media_ratio * 100)

    def fmt(m):
        h, mn = divmod(m, 60)
        return f"{h}h {mn}m" if h else f"{mn}m"

    if social_pct > 55:
        alerts.append({
            "level": "high", "emoji": "🌀",
            "title": f"Social media at {social_pct}% of your screen time",
            "desc":  f"{fmt(features.social_media_minutes)} on social apps. "
                     "Research links this level to increased anxiety and disrupted sleep.",
            "tag": "HIGH RISK",
        })
    elif social_pct > 30:
        alerts.append({
            "level": "medium", "emoji": "🌀",
            "title": f"Social media ratio elevated at {social_pct}%",
            "desc":  f"{fmt(features.social_media_minutes)} on social apps. Aim to keep this under 25-30%.",
            "tag": "MEDIUM",
        })

    if features.total_daily_screen_time > 360:
        alerts.append({
            "level": "high", "emoji": "⏱️",
            "title": f"Screen time exceeds {fmt(features.total_daily_screen_time)}",
            "desc":  "Extended screen time is linked to eye strain, disrupted sleep, and reduced wellbeing.",
            "tag": "HIGH RISK",
        })
    elif features.total_daily_screen_time > 240:
        alerts.append({
            "level": "medium", "emoji": "⏱️",
            "title": "Above-average screen time today",
            "desc":  f"{fmt(features.total_daily_screen_time)} is above the recommended daily average.",
            "tag": "MEDIUM",
        })

    if risk_level == "high":
        alerts.append({
            "level": "high", "emoji": "🚨",
            "title": "Digital addiction risk detected",
            "desc":  "Combined usage patterns indicate a high risk of compulsive phone use.",
            "tag": "HIGH RISK",
        })

    if not alerts:
        alerts.append({
            "level": "low", "emoji": "✅",
            "title": "Usage looks healthy today!",
            "desc":  "No major red flags. Keep it up!",
            "tag": "GOOD",
        })

    return alerts


# ── Recommendations ───────────────────────────────────────────────────
def generate_recommendations(features: FeatureSet) -> list[dict]:
    top = features.top_app_name

    recs = [
        {
            "num": "01",
            "title": "Activate Bedtime Mode at 10 PM",
            "desc": "Enable grayscale + Do Not Disturb. Grayscale makes your phone visually boring, "
                    "reducing late-night usage significantly.",
            "stars": "★★★★☆", "impact": "High impact",
        },
        {
            "num": "02",
            "title": f"Move {top} off your home screen",
            "desc": f"Put {top} in a folder on page 2. This friction barrier reduces mindless opens by ~30%.",
            "stars": "★★★☆☆", "impact": "Easy win",
        },
        {
            "num": "03",
            "title": "Schedule 2 phone-free hours daily",
            "desc": "Block 2-4 PM as a phone-free window. Keeping your phone in another room improves focus.",
            "stars": "★★★★☆", "impact": "High impact",
        },
    ]

    if features.social_media_ratio > 0.35:
        recs.insert(0, {
            "num": "00",
            "title": "Replace your morning scroll with a ritual",
            "desc": f"Your first {top} session sets your dopamine baseline for the day. "
                    "Replace it with a 10-min walk or breakfast without your phone.",
            "stars": "★★★★★", "impact": "Highest impact",
        })

    return recs


# ── Main endpoint ─────────────────────────────────────────────────────
@router.post("/predict", response_model=Prediction)
def predict(req: PredictRequest):
    features = extract_features(req)

    model_loaded = _load_model()
    if model_loaded:
        score, addiction, lvl, confidence = classify_ml(features)
        model_used = "RandomForest"
    else:
        score, addiction, lvl, confidence = classify_rules(features)
        model_used = "rule-based"


    # K-Means cluster assignment (rule-based approximation)
    sr = features.social_media_ratio
    tt = features.total_daily_screen_time
    if tt < 180 and sr < 0.3:
        cluster, cluster_name = 0, "Light Users"
    elif tt < 300 and sr < 0.45:
        cluster, cluster_name = 1, "Balanced Users"
    elif sr >= 0.5:
        cluster, cluster_name = 2, "Social-Heavy"
    else:
        cluster, cluster_name = 3, "High-Usage Multitaskers"

    alerts = generate_alerts(features, lvl)
    recs   = generate_recommendations(features)

    RISK_COLORS = {
        "healthy":  "var(--ok)",
        "moderate": "var(--warn)",
        "high":     "var(--danger)",
    }
    RISK_LABELS = {
        "healthy":  "✅ Healthy",
        "moderate": "⚠️ Moderate Risk",
        "high":     "🚨 High Risk",
    }

    return Prediction(
        health_score=score,
        addiction_risk_score=addiction,
        risk_level=lvl,
        risk_label=RISK_LABELS[lvl],
        risk_color=RISK_COLORS[lvl],
        classification_confidence=confidence,
        model_used=model_used,
        cluster=cluster,
        cluster_name=cluster_name,
        features=features,
        alerts=alerts,
        recommendations=recs,
    )
