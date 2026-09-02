"""
routers/data.py

GET  /api/sample-data   — returns the built-in demo dataset
POST /api/upload-csv    — parse a CSV or JSON file upload
"""

import json
import csv
import io
from fastapi import APIRouter, File, UploadFile, HTTPException

router = APIRouter()


SAMPLE_DATA = {
    "date": "Fri 6 Mar",
    "total_minutes": 295,
    "apps": [
        {"name": "Instagram",  "minutes": 237, "category": "social_media",   "color": "#e8604a"},
        {"name": "LinkedIn",   "minutes": 10,  "category": "productivity",    "color": "#5bc4f5"},
        {"name": "YouTube",    "minutes": 9,   "category": "entertainment",   "color": "#f5c842"},
        {"name": "Other",      "minutes": 39,  "category": "other",           "color": "#d9d9d4"},
    ],
    "weekly_data": [
        {"day": "Mon", "hours": 4.5},
        {"day": "Tue", "hours": 4.2},
        {"day": "Wed", "hours": 4.8},
        {"day": "Thu", "hours": 5.4},
        {"day": "Fri", "hours": 4.9},
        {"day": "Sat", "hours": 0.0},
        {"day": "Sun", "hours": 0.0},
    ],
    "notes": "Sample data based on a real Digital Wellbeing screenshot",
}


@router.get("/sample-data")
def get_sample_data():
    """Return the built-in demo dataset."""
    return SAMPLE_DATA


@router.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """
    Parse a CSV or JSON file with columns:
    date, app_name, usage_minutes, notifications, unlock_count,
    session_count, usage_hour, app_category
    """
    content = await file.read()

    if file.filename.endswith(".json"):
        try:
            parsed = json.loads(content)
            return _normalize(parsed)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"JSON parse error: {e}")

    # CSV
    try:
        reader = csv.DictReader(io.StringIO(content.decode()))
        rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"CSV parse error: {e}")

    if not rows:
        raise HTTPException(status_code=422, detail="CSV is empty")

    # Aggregate by app
    app_totals: dict[str, dict] = {}
    total_minutes = 0
    for row in rows:
        name = row.get("app_name", "Unknown").strip()
        mins = int(row.get("usage_minutes", 0))
        cat  = row.get("app_category", "other").strip()
        total_minutes += mins
        if name not in app_totals:
            app_totals[name] = {"name": name, "minutes": 0, "category": cat}
        app_totals[name]["minutes"] += mins

    colors = ["#e8604a","#f09433","#f5c842","#4dd0b3","#5bc4f5","#b388ff","#d9d9d4","#f472b6"]
    apps = sorted(app_totals.values(), key=lambda a: a["minutes"], reverse=True)
    for i, app in enumerate(apps):
        app["color"] = colors[i % len(colors)]

    date = rows[0].get("date", "Today") if rows else "Today"

    return {
        "date": date,
        "total_minutes": total_minutes,
        "apps": apps,
        "weekly_data": None,
        "notes": f"Parsed from {file.filename} — {len(rows)} records, {len(apps)} apps",
    }


def _normalize(data):
    """Accept either our schema or a raw list of records."""
    if isinstance(data, list):
        # List of records
        app_totals = {}
        total = 0
        for row in data:
            name = row.get("app_name", "Unknown")
            mins = int(row.get("usage_minutes", 0))
            cat  = row.get("app_category", "other")
            total += mins
            if name not in app_totals:
                app_totals[name] = {"name": name, "minutes": 0, "category": cat}
            app_totals[name]["minutes"] += mins
        colors = ["#e8604a","#f09433","#f5c842","#4dd0b3","#5bc4f5","#b388ff","#d9d9d4"]
        apps = sorted(app_totals.values(), key=lambda a: a["minutes"], reverse=True)
        for i, a in enumerate(apps):
            a["color"] = colors[i % len(colors)]
        return {"date": "Today", "total_minutes": total, "apps": apps, "weekly_data": None}
    return data
