"""
Drone Fleet API - Main FastAPI Application

A REST API for AI-driven drone orchestration in AirSim.

This API allows external AI teammates to command drones using plain English
interpreted into API calls. The AI teammate handles natural language - this
API provides the clean, well-documented endpoints.

Usage:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

Swagger docs: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .config import settings
from .routers import drones_router, fleet_router, status_router

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="""
## Drone Control API for LLM Integration

Simple REST API to control drones in AirSim. Designed for LLMs to call directly.

### Quick Start
1. Start AirSim with drones
2. Run: `python run_api.py`
3. Open http://localhost:8000/docs for API explorer
4. Open http://localhost:8000/ for live drone map

### Key Endpoints

| Action | Endpoint | Body |
|--------|----------|------|
| Go to house | `POST /drones/{id}/goto-house` | `{"house": "A"}` |
| Take off | `POST /drones/{id}/takeoff` | `{}` |
| Land | `POST /drones/{id}/land` | - |
| Move to XY | `POST /drones/{id}/move` | `{"x": 10, "y": 20}` |
| Hover/stop | `POST /drones/{id}/hover` | - |
| Take photo | `POST /drones/{id}/photo` | `{}` |
| Get status | `GET /drones/{id}` | - |
| List houses | `GET /drones/houses` | - |
| Fleet status | `GET /status/fleet` | - |
| Emergency stop | `POST /fleet/emergency-stop` | - |

### Notes
- Drone IDs are case-insensitive: `drone1`, `Drone1`, `d1` all work
- Drones auto-initialize and auto-takeoff when needed
- All movement commands are async (non-blocking) by default
    """,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for web interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(drones_router)
app.include_router(fleet_router)
app.include_router(status_router)

# Serve static web files
web_path = Path(__file__).parent.parent / "web"
if web_path.exists():
    app.mount("/static", StaticFiles(directory=str(web_path)), name="static")


@app.get("/", include_in_schema=False)
async def root():
    """Serve the web map interface."""
    index_path = web_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "message": "Drone Fleet API",
        "docs": "/docs",
        "status": "/status/health"
    }


@app.get("/style.css", include_in_schema=False)
async def get_css():
    """Serve CSS file."""
    return FileResponse(str(web_path / "style.css"), media_type="text/css")


@app.get("/map.js", include_in_schema=False)
async def get_js():
    """Serve JavaScript file."""
    return FileResponse(str(web_path / "map.js"), media_type="application/javascript")


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    print(f"\n{'='*60}")
    print(f"  {settings.app_name} v{settings.app_version}")
    print(f"{'='*60}")
    print(f"  API Docs:     http://localhost:{settings.port}/docs")
    print(f"  Web Map:      http://localhost:{settings.port}/")
    print(f"  WebSocket:    ws://localhost:{settings.port}/status/ws")
    print(f"{'='*60}\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("\nShutting down Drone Fleet API...")


# Run with: uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
