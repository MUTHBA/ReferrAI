# -----------------------------------------------------------------------------
# backend/app/services/model_training_service.py
#
# Runs model training on request from the admin UI. Training is CPU-bound, so
# it runs in a worker thread in the background; start() returns immediately
# and status() reports progress. Only one training run per process at a time.
# Admin fraud reviews in the database are loaded first and reported as an
# extra real-world evaluation set. Results are written to AI_MODEL_DIR, where
# every worker picks them up automatically (see app/ai/registry.py).
# -----------------------------------------------------------------------------

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

import anyio

from app.ai import registry

logger = logging.getLogger(__name__)

_state_lock = threading.Lock()
_state: dict = {"state": "idle", "started_at": None, "finished_at": None, "models": [], "error": None, "results": {}}
_task: Optional[asyncio.Task] = None


class TrainingAlreadyRunningError(Exception):
    pass


def status() -> dict:
    with _state_lock:
        return {**_state, "available_models": registry.describe()}


async def _run(models: tuple[str, ...], n_partners: int, seed: int) -> None:
    from app.ai.train import load_review_labels, train_models
    from app.core.database import AsyncSessionLocal

    try:
        reviews = None
        async with AsyncSessionLocal() as session:
            reviews = await load_review_labels(session)
        results = await anyio.to_thread.run_sync(lambda: train_models(models, n_partners, seed, reviews))
        with _state_lock:
            _state.update(
                state="succeeded",
                finished_at=datetime.now(timezone.utc).isoformat(),
                results={k: {"version": v["version"], "metrics": v["metrics"]} for k, v in results.items()},
            )
    except Exception as exc:
        logger.exception("Model training failed")
        with _state_lock:
            _state.update(state="failed", finished_at=datetime.now(timezone.utc).isoformat(), error=str(exc))


def start(models: tuple[str, ...], n_partners: int, seed: int) -> dict:
    global _task
    with _state_lock:
        if _state["state"] == "running":
            raise TrainingAlreadyRunningError()
        _state.update(
            state="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            finished_at=None,
            models=list(models),
            error=None,
            results={},
        )
    _task = asyncio.get_running_loop().create_task(_run(models, n_partners, seed))
    return status()


async def wait() -> None:
    """Await the current run (used by tests)."""
    if _task is not None:
        await _task
