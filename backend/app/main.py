import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import get_settings
from app.database import SessionLocal
from app.routers import (
    auth,
    calibration,
    customers,
    dashboard,
    designs,
    knife_models,
    materials,
    nesting,
    orders,
    production,
    sales_documents,
    saw_blades,
    settings,
    treatments,
)
from app.services.seed_service import seed_mock_data, seed_mock_designs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("knifeforge")
app_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if app_settings.demo:
        from app.services.demo_service import rebuild

        db = SessionLocal()
        try:
            rebuild(db)
            logger.info("Demo workshop rebuilt (read-only)")
        finally:
            db.close()
    elif app_settings.seed_mock_data_on_startup:
        db = SessionLocal()
        try:
            created = seed_mock_data(db)
            if created:
                logger.info("Seeded %s mock material(s)", created)
            designs_created = seed_mock_designs(db)
            if designs_created:
                logger.info("Seeded %s mock design(s)", designs_created)
        finally:
            db.close()
    stop = threading.Event()
    if app_settings.desktop:
        from app.services.auto_backup import start_scheduler

        start_scheduler(stop)
    yield
    stop.set()


app = FastAPI(title="KnifeForge Pro", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[app_settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if app_settings.demo:
    from app.services.demo_service import write_allowed

    @app.middleware("http")
    async def read_only_demo(request: Request, call_next):
        if request.url.path.startswith("/api/") and not write_allowed(request.method, request.url.path):
            return JSONResponse({"detail": "Read-only demo"}, status_code=403)
        return await call_next(request)


app.include_router(auth.router)
app.include_router(materials.router)
app.include_router(saw_blades.router)
app.include_router(treatments.router)
app.include_router(knife_models.router)
app.include_router(orders.router)
app.include_router(production.router)
app.include_router(designs.router)
app.include_router(nesting.router)
app.include_router(settings.router)
app.include_router(customers.router)
app.include_router(sales_documents.router)
app.include_router(dashboard.router)
app.include_router(calibration.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "knifeforge-pro", "desktop": app_settings.desktop}


# ---- desktop build: the backend also serves the built interface (nginx does it under Docker)
# Same security headers as frontend/nginx.conf: everything comes from this origin, no inline or
# eval script.
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-src 'self' blob:; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

if app_settings.frontend_dist:
    dist = Path(app_settings.frontend_dist).resolve()

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.get("/{path:path}", include_in_schema=False)
    def interface(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        file = (dist / path).resolve()
        if path and file.is_file() and dist in file.parents:
            # hashed asset names never change: cache them; index.html is always revalidated
            cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
            return FileResponse(file, headers={"Cache-Control": cache})
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})
