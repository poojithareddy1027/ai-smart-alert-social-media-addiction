"""
routers/screenshot.py

POST /api/analyze-screenshot
  - Accepts an image upload
  - Calls Claude Vision API (server-side — no CORS, key is safe in .env)
  - Returns structured JSON: apps, totals, date, weekly bars
"""

import os
import base64
import json
import re
import httpx
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL       = "claude-opus-4-5"


class AppUsage(BaseModel):
    name: str
    minutes: int
    category: str   # social_media | entertainment | productivity | communication | education | other
    color: Optional[str] = None


class ScreenshotResult(BaseModel):
    date: str
    total_minutes: int
    apps: list[AppUsage]
    weekly_data: Optional[list[dict]] = None
    notes: Optional[str] = None
    raw_ai_text: Optional[str] = None


PROMPT = """You are analyzing a smartphone Digital Wellbeing / Screen Time screenshot.

Extract ALL app usage data visible. Return ONLY valid JSON — no markdown, no explanation.

Format:
{
  "date": "e.g. Fri 6 Mar",
  "total_minutes": <number — convert h+m to total minutes>,
  "apps": [
    {"name": "Instagram", "minutes": 237, "category": "social_media"}
  ],
  "weekly_data": [
    {"day": "Mon", "hours": 4.5}
  ],
  "notes": "any extra visible info (notifications, unlocks etc)"
}

Category must be one of: social_media, entertainment, productivity, communication, education, other
Convert all times to minutes (3 hrs 57 mins = 237).
If weekly bar chart is visible, estimate each bar height in hours.
Return ONLY the JSON object."""


@router.post("/analyze-screenshot", response_model=ScreenshotResult)
async def analyze_screenshot(file: UploadFile = File(...)):
    """
    Upload a screenshot image.
    The server calls Claude Vision API and returns parsed usage data.
    API key never touches the browser.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY not set in .env — see README"
        )

    # Read & encode image
    image_bytes = await file.read()
    b64 = base64.b64encode(image_bytes).decode()
    mime = file.content_type or "image/jpeg"

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1024,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": mime, "data": b64}
                },
                {"type": "text", "text": PROMPT}
            ]
        }]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Claude API error {response.status_code}: {response.text[:300]}"
        )

    data = response.json()
    raw_text = "".join(b.get("text", "") for b in data.get("content", []))

    # Strip markdown fences if present
    clean = re.sub(r"```json|```", "", raw_text).strip()

    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail=f"Could not parse AI response as JSON. Raw: {raw_text[:400]}"
        )

    # Assign colors
    colors = ["#e8604a","#f09433","#f5c842","#4dd0b3","#5bc4f5","#b388ff","#d9d9d4","#f472b6"]
    for i, app in enumerate(parsed.get("apps", [])):
        app["color"] = colors[i % len(colors)]

    return ScreenshotResult(
        date=parsed.get("date", "Today"),
        total_minutes=parsed.get("total_minutes", 0),
        apps=[AppUsage(**a) for a in parsed.get("apps", [])],
        weekly_data=parsed.get("weekly_data"),
        notes=parsed.get("notes"),
        raw_ai_text=raw_text,
    )
