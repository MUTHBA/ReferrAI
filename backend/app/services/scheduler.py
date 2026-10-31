# -----------------------------------------------------------------------------
# backend/app/services/scheduler.py
#
# In-process scheduler for batch AI scoring (AI-CHURN-001 "scheduled"): every
# `ai.batch_scoring_interval_hours` (settings table; 0 disables) it recomputes
# churn scores and then ranking scores for all active partners.
#
# With several uvicorn workers each process runs this loop, so a PostgreSQL
# advisory lock makes sure only one of them does the work per cycle.
# Started/stopped by the FastAPI lifespan in app/main.py; disabled with
# ENABLE_SCHEDULER=false (the test suite does this).
# -----------------------------------------------------------------------------

import asyncio
import logging
from typing import Optional

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.services import ai_service
from app.services.setting_service import SettingService

logger = logging.getLogger(__name__)

_LOCK_KEY = 815_204_771  # arbitrary, app-wide constant
_INITIAL_DELAY_S = 60
_RECHECK_S = 3600  # how often to re-read the interval when disabled


async def run_batch_once() -> bool:
    """Run churn then ranking for all partners if this process wins the lock."""
    async with AsyncSessionLocal() as session:
        got = (await session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _LOCK_KEY})).scalar()
        if not got:
            return False
        try:
            churn = await ai_service.score_all_active_partners(ai_service.score_churn)
            ranked = await ai_service.score_all_active_partners(ai_service.score_ranking)
            logger.info("Scheduled scoring: churn=%d ranking=%d partners", churn, ranked)
        finally:
            await session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_KEY})
            await session.commit()
    return True


async def _loop() -> None:
    await asyncio.sleep(_INITIAL_DELAY_S)
    while True:
        try:
            async with AsyncSessionLocal() as session:
                hours = int(await SettingService(session).get("ai.batch_scoring_interval_hours"))
            if hours <= 0:
                await asyncio.sleep(_RECHECK_S)
                continue
            await run_batch_once()
            await asyncio.sleep(hours * 3600)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled scoring failed; retrying in an hour")
            await asyncio.sleep(_RECHECK_S)


_task: Optional[asyncio.Task] = None


def start() -> None:
    global _task
    if _task is None:
        _task = asyncio.get_running_loop().create_task(_loop())


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):
            pass
        _task = None
