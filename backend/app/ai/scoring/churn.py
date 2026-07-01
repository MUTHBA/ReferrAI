# -----------------------------------------------------------------------------
# backend/app/ai/scoring/churn.py
#
# Partner churn predictor (AI-CHURN-001). Wraps a scikit-learn Pipeline
# (StandardScaler → GradientBoostingClassifier) that predicts the probability a
# partner will churn (stop generating referrals). The raw P(churn) probability
# is scaled to 0–100 for display.
#
# All five features are pre-computed numeric values — no categorical encoding
# is needed here, so no LabelEncoders are stored alongside the model.
#
# Graceful degradation: predict() catches all exceptions and returns 50.0 (a
# neutral midpoint, not 0.0) because churn risk is a two-sided uncertainty —
# we don't know whether the partner will churn or not, so the neutral score is
# more appropriate than the "definitely not churned" value of 0.0.
# -----------------------------------------------------------------------------

import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "churn_predictor.joblib"

FEATURE_NAMES = [
    "days_since_last_referral",
    "referral_count_30d",
    "referral_count_90d",
    "commission_trend",
    "tier_rank",
]


class ChurnPredictor:
    """Trains and serves a partner churn risk score (0–100).

    Feature dict contract (same shape for train records and predict calls):
        days_since_last_referral (float) — days since the partner's most recent
                                           conversion; 365.0 if no conversion exists
        referral_count_30d       (int)   — conversions in the last 30 days
        referral_count_90d       (int)   — conversions in the last 90 days
        commission_trend         (float) — sum(conversion_value last 90d) /
                                           (sum(conversion_value prior 90d) + 1.0);
                                           >1 = growing, <1 = declining, 0 = no activity
        tier_rank                (int)   — PartnerTier.rank_order; 0 if no tier assigned

    Label key (train() only, ignored by predict()):
        is_churned               (int)   — 1 if the partner has churned, 0 if active

    Score semantics:
        0   — very unlikely to churn
        100 — very likely to churn
        50  — returned on any inference error (model unavailable, etc.)
    """

    def __init__(self) -> None:
        self._pipeline: Optional[Pipeline] = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_row(features: dict) -> list[float]:
        """Convert a feature dict to a flat numeric list in FEATURE_NAMES order."""
        return [
            float(features.get("days_since_last_referral", 365.0)),
            float(features.get("referral_count_30d", 0)),
            float(features.get("referral_count_90d", 0)),
            float(features.get("commission_trend", 0.0)),
            float(features.get("tier_rank", 0)),
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def train(self, records: list[dict]) -> None:
        """Fit the Pipeline on the supplied records and persist to disk.

        Args:
            records: list of feature dicts (see class docstring). Each dict must
                     include ``is_churned`` (int, 0 or 1) as the training label.
        """
        if not records:
            raise ValueError("Cannot train on an empty record set")

        X = np.array([self._build_row(r) for r in records], dtype=float)
        y = np.array([int(r["is_churned"]) for r in records], dtype=int)

        self._pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", GradientBoostingClassifier(n_estimators=100, random_state=42)),
            ]
        )
        self._pipeline.fit(X, y)

        _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": self._pipeline}, _MODEL_PATH)
        logger.info("ChurnPredictor saved to %s", _MODEL_PATH)

    def load(self) -> None:
        """Load the persisted model from disk.  No-op if file does not exist."""
        if not _MODEL_PATH.exists():
            logger.warning("ChurnPredictor model file not found at %s", _MODEL_PATH)
            return
        artifact = joblib.load(_MODEL_PATH)
        self._pipeline = artifact["pipeline"]
        logger.info("ChurnPredictor loaded from %s", _MODEL_PATH)

    def predict(self, features: dict) -> float:
        """Return a churn risk score in [0, 100].  Returns 50.0 on any error.

        Args:
            features: dict with the same keys as training records (excluding
                      ``is_churned``).

        Returns:
            float: 100 × P(churned), or 50.0 if the model is unavailable
                   or any exception occurs during inference.
        """
        try:
            if self._pipeline is None:
                self.load()
            if self._pipeline is None:
                return 50.0
            x = np.array([self._build_row(features)], dtype=float)
            proba: float = float(self._pipeline.predict_proba(x)[0][1])
            return round(proba * 100.0, 2)
        except Exception:
            logger.exception("ChurnPredictor.predict failed — returning 50.0")
            return 50.0

    def get_feature_importances(self) -> dict[str, float]:
        """Return a mapping of feature name → importance from the trained booster.

        Raises:
            RuntimeError: if the model has not been trained or loaded yet.
        """
        if self._pipeline is None:
            self.load()
        if self._pipeline is None:
            raise RuntimeError("Model is not loaded — call train() or load() first")
        clf: GradientBoostingClassifier = self._pipeline.named_steps["clf"]
        return dict(zip(FEATURE_NAMES, clf.feature_importances_.tolist()))
