# -----------------------------------------------------------------------------
# backend/app/ai/registry.py
#
# Loads, stores and serves trained models. Artifacts live in
# settings.AI_MODEL_DIR as  <name>.joblib  (the sklearn pipeline) plus
# <name>.meta.json  (feature list, metrics, library versions, calibration).
#
# * get(name) returns the in-memory bundle, reloading it if the file on disk
#   changed (so every uvicorn worker picks up a retrain), or None if the model
#   has not been trained — callers then store a NULL score (graceful
#   degradation), never a made-up value.
# * save() writes atomically (temp file + rename).
# * predict_*() are synchronous CPU work; async callers wrap them with
#   anyio.to_thread.run_sync so the event loop is never blocked.
# -----------------------------------------------------------------------------

from __future__ import annotations

import json
import logging
import math
import os
import pathlib
import tempfile
import threading
from dataclasses import dataclass
from typing import Any, Optional

import joblib

from app.core.config import settings

logger = logging.getLogger(__name__)

MODEL_NAMES = ("quality", "fraud", "churn")


@dataclass
class ModelBundle:
    name: str
    pipeline: Any
    meta: dict
    mtime: float

    @property
    def version(self) -> str:
        return self.meta.get("version", "unknown")

    @property
    def features(self) -> list[str]:
        return list(self.meta["features"])


_lock = threading.Lock()
_bundles: dict[str, ModelBundle] = {}


def model_dir() -> pathlib.Path:
    return pathlib.Path(settings.AI_MODEL_DIR)


def _paths(name: str) -> tuple[pathlib.Path, pathlib.Path]:
    d = model_dir()
    return d / f"{name}.joblib", d / f"{name}.meta.json"


def _load(name: str) -> Optional[ModelBundle]:
    model_path, meta_path = _paths(name)
    if not model_path.exists() or not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text())
        pipeline = joblib.load(model_path)
        return ModelBundle(name, pipeline, meta, model_path.stat().st_mtime)
    except Exception:
        logger.exception("Failed to load model %s from %s", name, model_path)
        return None


def get(name: str) -> Optional[ModelBundle]:
    model_path, _ = _paths(name)
    try:
        mtime = model_path.stat().st_mtime
    except FileNotFoundError:
        with _lock:
            _bundles.pop(name, None)
        return None
    with _lock:
        cached = _bundles.get(name)
        if cached is not None and cached.mtime == mtime:
            return cached
    bundle = _load(name)
    with _lock:
        if bundle is None:
            _bundles.pop(name, None)
        else:
            _bundles[name] = bundle
    return bundle


def load_all() -> dict[str, bool]:
    """Warm the cache at startup. Returns {name: loaded}."""
    status = {name: get(name) is not None for name in MODEL_NAMES}
    logger.info("AI models loaded: %s (dir=%s)", status, model_dir())
    return status


def save(name: str, pipeline: Any, meta: dict) -> pathlib.Path:
    d = model_dir()
    d.mkdir(parents=True, exist_ok=True)
    model_path, meta_path = _paths(name)
    for target, writer in (
        (model_path, lambda f: joblib.dump(pipeline, f)),
        (meta_path, lambda f: f.write(json.dumps(meta, indent=2, default=str).encode())),
    ):
        fd, tmp = tempfile.mkstemp(dir=d, prefix=f".{target.name}.")
        try:
            with os.fdopen(fd, "wb") as f:
                writer(f)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    with _lock:
        _bundles.pop(name, None)
    get(name)
    return model_path


def describe() -> list[dict]:
    """Model status for the admin UI."""
    from app.ai.features import FEATURE_LABELS

    out = []
    for name in MODEL_NAMES:
        b = get(name)
        if b is None:
            out.append({"name": name, "trained": False})
        else:
            m = b.meta
            out.append(
                {
                    "name": name,
                    "trained": True,
                    "version": b.version,
                    "trained_at": m.get("trained_at"),
                    "algorithm": m.get("algorithm"),
                    "features": m.get("features"),
                    "feature_labels": [FEATURE_LABELS.get(f, f) for f in (m.get("features") or [])],
                    "metrics": m.get("metrics"),
                    "training_rows": m.get("training_rows"),
                }
            )
    return out


# ---------------------------------------------------------------------------
# Prediction helpers (synchronous)
# ---------------------------------------------------------------------------


def _frame(bundle: ModelBundle, features: dict):
    import pandas as pd

    return pd.DataFrame([{k: features[k] for k in bundle.features}], columns=bundle.features)


def predict_proba(bundle: ModelBundle, features: dict) -> float:
    """0-100 probability of the positive class (quality: good referral; churn: churns)."""
    return float(bundle.pipeline.predict_proba(_frame(bundle, features))[0, 1]) * 100.0


def predict_fraud(bundle: ModelBundle, features: dict) -> float:
    """0-100 fraud risk from the Isolation Forest.

    The forest's anomaly score (-decision_function: >0 means anomalous) is
    mapped through a logistic calibration fitted on labelled training clicks,
    so the output reads as "probability this click is fraudulent".
    """
    raw = float(-bundle.pipeline.decision_function(_frame(bundle, features))[0])
    cal = bundle.meta["calibration"]
    z = cal["coef"] * raw + cal["intercept"]
    return 100.0 / (1.0 + math.exp(-z))


def frame_for(bundle: ModelBundle, features: dict):
    return _frame(bundle, features)
