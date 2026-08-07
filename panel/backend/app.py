import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, JSONResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .api_extras import router as extras_router
from .api_monitor import get_status, start_monitor
from .auth import router as auth_router
from .proxy import router as proxy_router
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
DIST_DIR = Path(__file__).resolve().parent.parent / "dist"
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_monitor()
    logger.info("GW VPN panel backend started")
    yield
    logger.info("GW VPN panel backend stopped")
app = FastAPI(title="GW VPN Admin Panel", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(proxy_router)
app.include_router(extras_router)
@app.get("/api/monitor/status")
async def monitor_status():
    return get_status()
@app.get("/api/health")
async def health():
    return {"success": True, "service": "gw-panel"}
@app.get("/favicon.ico")
async def favicon():
    fav = DIST_DIR / "favicon.png"
    if fav.is_file():
        return FileResponse(fav, media_type="image/png")
    return JSONResponse({"detail": "not found"}, status_code=404)
@app.get("/favicon.png")
async def favicon_png():
    fav = DIST_DIR / "favicon.png"
    if fav.is_file():
        return FileResponse(fav, media_type="image/png")
    return JSONResponse({"detail": "not found"}, status_code=404)
    return {"success": True, "service": "gw-panel"}
if DIST_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=DIST_DIR / "assets"),
        name="assets",
    )
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path:
            candidate = (DIST_DIR / full_path).resolve()
            try:
                candidate.relative_to(DIST_DIR.resolve())
            except ValueError:
                return JSONResponse({"detail": "not found"}, status_code=404)
            if candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
