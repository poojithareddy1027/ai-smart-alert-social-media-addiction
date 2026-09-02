"""
ScreenSense — Digital Wellbeing AI
FastAPI Backend  |  app.py

Endpoints:
  POST /api/analyze-screenshot   — Claude Vision reads your screenshot
  POST /api/analyze-csv          — Parse CSV / JSON upload
  GET  /api/sample-data          — Load built-in demo data
  POST /api/predict              — ML classification + clustering
  GET  /api/recommendations      — Generate smart recs from last result
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
from pathlib import Path

from routers import screenshot, predict, data
from dotenv import load_dotenv
load_dotenv()

# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="ScreenSense API",
    description="AI-powered Digital Wellbeing Analysis",
    version="1.0.0",
)

# ── CORS — allow browser to call this server ─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────
app.include_router(screenshot.router, prefix="/api", tags=["Screenshot AI"])
app.include_router(predict.router,    prefix="/api", tags=["ML Prediction"])
app.include_router(data.router,       prefix="/api", tags=["Data"])

# ── Serve frontend ────────────────────────────────────────────────────
FRONTEND = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND / "static")), name="static")

@app.get("/", include_in_schema=False)
def root():
    return FileResponse(str(FRONTEND / "index.html"))

@app.get("/health")
def health():
    return {"status": "ok", "service": "ScreenSense API v1.0"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
