from __future__ import annotations

import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.poller import Poller
from app.models.watch_config import WatchConfig
from app.api import environments, poll_runs, changes, rollback, history, playground

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_poller: Poller | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _poller
    watch_config = WatchConfig.load(settings.watch_config_path)
    _poller = Poller(watch_config, settings.sqlite_data_dir)
    _poller.start()
    logger.info("light-cdc started")
    yield
    if _poller:
        _poller.stop()
    logger.info("light-cdc stopped")


app = FastAPI(title="light-cdc", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


PREFIX = "/api/v1"
app.include_router(environments.router, prefix=PREFIX)
app.include_router(poll_runs.router, prefix=PREFIX)
app.include_router(changes.router, prefix=PREFIX)
app.include_router(rollback.router, prefix=PREFIX)
app.include_router(history.router, prefix=PREFIX)
app.include_router(playground.router, prefix=PREFIX)


def get_poller() -> Poller:
    if _poller is None:
        raise RuntimeError("Poller not initialised")
    return _poller
