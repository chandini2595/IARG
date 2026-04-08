from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.config import settings
from src.services.drive_monitor_service import DriveMonitorService
from src.services.guardian_service import GuardianService
from src.services.storage import Storage

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize storage + service
    storage = Storage(settings.db_path)
    await storage.init()

    guardian_service = GuardianService(storage, settings)
    drive_monitor = DriveMonitorService(storage, guardian_service, settings)

    app.state.storage = storage
    app.state.guardian_service = guardian_service
    app.state.drive_monitor = drive_monitor

    poll_task: Optional[asyncio.Task] = None
    if settings.google_drive_monitor_enabled and drive_monitor.is_configured():

        async def _drive_poll_loop() -> None:
            await asyncio.sleep(3)
            while True:
                try:
                    await drive_monitor.poll_once()
                except asyncio.CancelledError:
                    break
                except Exception:
                    log.exception("Drive monitor poll failed")
                await asyncio.sleep(max(30, int(settings.google_drive_poll_interval_seconds)))

        poll_task = asyncio.create_task(_drive_poll_loop())
    elif settings.google_drive_monitor_enabled and not drive_monitor.is_configured():
        log.warning(
            "GOOGLE_DRIVE_MONITOR_ENABLED is true but OAuth or monitored IDs are missing; background poll disabled"
        )

    try:
        yield
    finally:
        if poll_task:
            poll_task.cancel()
            try:
                await poll_task
            except asyncio.CancelledError:
                pass
        await guardian_service.close()


app = FastAPI(
    title="IARG Guardian",
    description="Intangible-Asset Risk Guardian (MVP)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {"service": "iarg-guardian", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}

