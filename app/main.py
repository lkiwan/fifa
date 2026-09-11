import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import seed, scheduler
from app.config import BASE_DIR
from app.database import Base, engine
from app.routers import data as data_router
from app.routers import game as game_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fifa")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    count = seed.count_players()
    if count == 0:
        logger.info("Database empty. Running a first quick scrape (list only)...")
        try:
            seed.update_from_web(scrape_profiles=False)
        except Exception:  # noqa: BLE001
            logger.exception("Initial seed failed. Run `python scripts/update_data.py` later.")

    scheduler.start_scheduler()
    yield
    scheduler.scheduler.shutdown(wait=False)


app = FastAPI(title="FIFA Quiz", lifespan=lifespan)

app.include_router(data_router.router, prefix="/api")
app.include_router(game_router.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


STATIC_DIR = os.path.join(BASE_DIR, "app", "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")