# -----------------------------------------------------------------------------
# backend/app/ai/scoring/fraud.py
#
# Isolation Forest fraud detector (AI-FRD-002). IsolationForest is trained
# unsupervised on behavioural click features — no labels are needed during
# training. Its decision_function() produces anomaly scores (positive = normal,
# negative = anomalous) which are inverted and min-max scaled to 0–100 so that
# higher scores indicate higher fraud likelihood.
#
# The feature scaler (StandardScaler) and the score normalisation bounds
# (_score_min, _score_max) are persisted alongside the IsolationForest model so
# that inference is self-contained from a single joblib file.
#
# Graceful degradation: predict() catches all exceptions and returns 0.0 (no
# fraud detected) so that a missing model file or any inference error never
# surfaces to the caller (per the AI resilience principle in CLAUDE.md).
# -----------------------------------------------------------------------------

import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "fraud_detector.joblib"

FEATURE_NAMES = [
    "clicks_per_hour",
    "unique_ips_per_partner",
    "device_reuse_count",
    "time_between_clicks_seconds",
]


class FraudDetector:
    """Trains and serves a fraud likelihood score (0–100) using Isolation Forest.

    Feature dict contract (same shape for train records and predict calls):
        clicks_per_hour              (float) — click count from this IP in the past hour
        unique_ips_per_partner       (int)   — distinct IPs seen for this partner overall
        device_reuse_count           (int)   — other clicks sharing the same user-agent string
        time_between_clicks_seconds  (float) — seconds since the previous click from this IP
                                               (3600.0 for the first click from a given IP)

    Score semantics:
        0   — no anomaly detected
        100 — extreme anomaly (very likely fraudulent burst behaviour)
    """

    def __init__(self) -> None:
        self._model: Optional[IsolationForest] = None
        self._scaler: Optional[StandardScaler] = None
        # Training-set bounds for linear score normalisation.
        self._score_min: float = 0.0
        self._score_max: float = 1.0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_row(features: dict) -> list[float]:
        """Convert a feature dict to a flat numeric list in FEATURE_NAMES order."""
        return [
            float(features.get("clicks_per_hour", 0.0)),
            float(features.get("unique_ips_per_partner", 1)),
            float(features.get("device_reuse_count", 1)),
            float(features.get("time_between_clicks_seconds", 3600.0)),
        ]

    def _normalise(self, raw_score: float) -> float:
        """Invert and min-max scale an IsolationForest decision score to [0, 100]."""
        inverted = -raw_score
        if self._score_max == self._score_min:
            return 0.0
        scaled = (inverted - self._score_min) / (self._score_max - self._score_min) * 100.0
        return round(float(np.clip(scaled, 0.0, 100.0)), 2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def train(self, records: list[dict]) -> None:
        """Fit IsolationForest on the supplied records and persist to disk.

        Args:
            records: list of feature dicts (see class docstring for keys).
                     Labels are not required — IsolationForest is unsupervised.
        """
        if not records:
            raise ValueError("Cannot train on an empty record set")

        X = np.array([self._build_row(r) for r in records], dtype=float)

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        self._model = IsolationForest(contamination=0.2, random_state=42)
        self._model.fit(X_scaled)

        # Capture the training-set score range so predict() can normalise
        # consistently against real inference data.
        raw_scores = self._model.decision_function(X_scaled)
        inverted = -raw_scores
        self._score_min = float(inverted.min())
        self._score_max = float(inverted.max())

        _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self._model,
                "scaler": self._scaler,
                "score_min": self._score_min,
                "score_max": self._score_max,
            },
            _MODEL_PATH,
        )
        logger.info("FraudDetector saved to %s", _MODEL_PATH)

    def load(self) -> None:
        """Load the persisted model from disk.  No-op if file does not exist."""
        if not _MODEL_PATH.exists():
            logger.warning("FraudDetector model file not found at %s", _MODEL_PATH)
            return
        artifact = joblib.load(_MODEL_PATH)
        self._model = artifact["model"]
        self._scaler = artifact["scaler"]
        self._score_min = artifact["score_min"]
        self._score_max = artifact["score_max"]
        logger.info("FraudDetector loaded from %s", _MODEL_PATH)

    def predict(self, features: dict) -> float:
        """Return a fraud likelihood score in [0, 100].  Returns 0.0 on any error.

        Args:
            features: dict with the same keys as training records.

        Returns:
            float: fraud likelihood 0–100, or 0.0 if the model is unavailable
                   or any exception occurs during inference.
        """
        try:
            if self._model is None:
                self.load()
            if self._model is None:
                return 0.0
            x = np.array([self._build_row(features)], dtype=float)
            x_scaled = self._scaler.transform(x)  # type: ignore[union-attr]
            raw_score = float(self._model.decision_function(x_scaled)[0])
            return self._normalise(raw_score)
        except Exception:
            logger.exception("FraudDetector.predict failed — returning 0.0")
            return 0.0
