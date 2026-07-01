# -----------------------------------------------------------------------------
# backend/app/ai/scoring/quality.py
#
# Referral quality scorer (AI-QUAL-001). Wraps a scikit-learn Pipeline
# (StandardScaler → RandomForestClassifier) that predicts the probability a
# referral conversion is "high quality" (conversion_value above the training
# set median). The raw probability is scaled to 0–100 for display.
#
# Label encoders for the two categorical features (source_type, device_category)
# are trained alongside the Pipeline and persisted to the same joblib file, so
# encoding is always consistent between training and inference without any
# caller-side bookkeeping.
#
# Graceful degradation: predict() catches all exceptions and returns 50.0 so
# that a missing model file, unseen label, or any sklearn error never surfaces
# to callers (per the AI resilience principle in CLAUDE.md).
# -----------------------------------------------------------------------------

import logging
import statistics
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

logger = logging.getLogger(__name__)

# The joblib artifact stores the Pipeline + both LabelEncoders in a single dict.
_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "quality_scorer.joblib"

FEATURE_NAMES = [
    "time_to_convert_minutes",
    "source_type",
    "device_category",
    "conversion_value_normalized",
    "partner_tier_rank",
]


class ReferralQualityScorer:
    """Trains and serves a referral quality score (0–100) based on conversion features.

    Feature dict contract (same shape for train records and predict calls):
        time_to_convert_minutes (float)  — seconds from click to conversion / 60
        source_type             (str|None) — utm_source string e.g. "google", None
        device_category         (str|None) — device_type from device_info JSONB
        conversion_value_normalized (float) — raw conversion value (StandardScaler normalises)
        partner_tier_rank       (int)    — PartnerTier.rank_order, 0 if no tier assigned
    """

    def __init__(self) -> None:
        self._pipeline: Optional[Pipeline] = None
        self._source_encoder: Optional[LabelEncoder] = None
        self._device_encoder: Optional[LabelEncoder] = None
        # Training-set median stored so callers can reproduce the label threshold.
        self._label_median: float = 0.0

    # ------------------------------------------------------------------
    # Encoding helpers
    # ------------------------------------------------------------------

    def _encode_source(self, value: Optional[str]) -> int:
        """Encode utm_source string to int; returns 0 for None or unseen labels."""
        label = value if value is not None else "unknown"
        try:
            return int(self._source_encoder.transform([label])[0])  # type: ignore[union-attr]
        except (ValueError, AttributeError):
            return 0

    def _encode_device(self, value: Optional[str]) -> int:
        """Encode device_type string to int; returns 0 for None or unseen labels."""
        label = value if value is not None else "unknown"
        try:
            return int(self._device_encoder.transform([label])[0])  # type: ignore[union-attr]
        except (ValueError, AttributeError):
            return 0

    def _build_row(self, features: dict) -> list[float]:
        """Convert a feature dict to a flat numeric list in FEATURE_NAMES order."""
        return [
            float(features.get("time_to_convert_minutes", 0.0)),
            float(self._encode_source(features.get("source_type"))),
            float(self._encode_device(features.get("device_category"))),
            float(features.get("conversion_value_normalized", 0.0)),
            float(features.get("partner_tier_rank", 0)),
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def train(self, records: list[dict]) -> None:
        """Fit the Pipeline on the supplied records and persist to disk.

        Args:
            records: list of feature dicts (see class docstring for keys).
                     Each dict must also contain ``conversion_value_normalized``
                     which doubles as the raw value used to derive the binary
                     is_high_quality label (> training-set median → 1).
        """
        if not records:
            raise ValueError("Cannot train on an empty record set")

        # --- Fit label encoders on the full training corpus ---
        sources = [r.get("source_type") or "unknown" for r in records]
        devices = [r.get("device_category") or "unknown" for r in records]

        self._source_encoder = LabelEncoder()
        self._source_encoder.fit(sources)

        self._device_encoder = LabelEncoder()
        self._device_encoder.fit(devices)

        # --- Build feature matrix and labels ---
        raw_values = [float(r["conversion_value_normalized"]) for r in records]
        self._label_median = statistics.median(raw_values)

        X = np.array([self._build_row(r) for r in records], dtype=float)
        y = np.array(
            [1 if v > self._label_median else 0 for v in raw_values], dtype=int
        )

        # --- Fit Pipeline ---
        self._pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", RandomForestClassifier(n_estimators=100, random_state=42)),
            ]
        )
        self._pipeline.fit(X, y)

        # --- Persist ---
        _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "pipeline": self._pipeline,
                "source_encoder": self._source_encoder,
                "device_encoder": self._device_encoder,
                "label_median": self._label_median,
            },
            _MODEL_PATH,
        )
        logger.info("ReferralQualityScorer saved to %s", _MODEL_PATH)

    def load(self) -> None:
        """Load the persisted model from disk.  No-op if file does not exist."""
        if not _MODEL_PATH.exists():
            logger.warning("ReferralQualityScorer model file not found at %s", _MODEL_PATH)
            return
        artifact = joblib.load(_MODEL_PATH)
        self._pipeline = artifact["pipeline"]
        self._source_encoder = artifact["source_encoder"]
        self._device_encoder = artifact["device_encoder"]
        self._label_median = artifact.get("label_median", 0.0)
        logger.info("ReferralQualityScorer loaded from %s", _MODEL_PATH)

    def predict(self, features: dict) -> float:
        """Return a quality score in [0, 100].  Returns 50.0 on any error.

        Args:
            features: dict with the same keys as training records.

        Returns:
            float: 100 × P(high_quality), or 50.0 if the model is unavailable
                   or any exception occurs during inference.
        """
        try:
            if self._pipeline is None:
                self.load()
            if self._pipeline is None:
                return 50.0
            x = np.array([self._build_row(features)], dtype=float)
            # predict_proba returns [[P(low), P(high)]]; we want P(high)
            proba: float = float(self._pipeline.predict_proba(x)[0][1])
            return round(proba * 100.0, 2)
        except Exception:
            logger.exception("ReferralQualityScorer.predict failed — returning 50.0")
            return 50.0

    def get_feature_importances(self) -> dict[str, float]:
        """Return a mapping of feature name → importance from the trained forest.

        Raises:
            RuntimeError: if the model has not been trained or loaded yet.
        """
        if self._pipeline is None:
            self.load()
        if self._pipeline is None:
            raise RuntimeError("Model is not loaded — call train() or load() first")
        forest: RandomForestClassifier = self._pipeline.named_steps["clf"]
        return dict(zip(FEATURE_NAMES, forest.feature_importances_.tolist()))
