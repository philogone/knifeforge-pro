import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import SessionLocal
from app.routers import auth, knife_models, materials, orders, production, saw_blades, settings, treatments
from app.services.seed_service import seed_mock_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("knifeforge")
app_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if app_settings.seed_mock_data_on_startup:
        db = SessionLocal()
        try:
            created = seed_mock_data(db)
            if created:
                logger.info("Seeded %s mock material(s)", created)
        finally:
            db.close()
    yield


app = FastAPI(title="KnifeForge Manager", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[app_settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(materials.router)
app.include_router(saw_blades.router)
app.include_router(treatments.router)
app.include_router(knife_models.router)
app.include_router(orders.router)
app.include_router(production.router)
app.include_router(settings.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
