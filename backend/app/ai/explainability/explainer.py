# -----------------------------------------------------------------------------
# backend/app/ai/explainability/explainer.py
#
# SHAP-based explanation utilities for all AI score types (AI-XAI-001).
# Provides two public methods:
#
#   explain_tree() — wraps shap.TreeExplainer to return the top-3 features by
#       absolute SHAP value for any tree-based sklearn estimator. Designed for
#       the RandomForest (quality), GradientBoosting (churn), and IsolationForest
#       (fraud) models stored in the ai/models/ directory.
#
#   to_plain_language() — converts the top-factor dict into a one-sentence
#       human-readable explanation tailored to each score type.
#
# Both methods are stateless (no __init__ state needed beyond the class) and
# wrap all exceptions so callers never need to handle Explainer failures.
# -----------------------------------------------------------------------------

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Explainer:
    """Generates SHAP-based explanations and plain-language summaries for AI scores."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def explain_tree(
        self,
        model: Any,
        features: dict,
        feature_names: list[str],
    ) -> dict[str, float]:
        """Compute the top-3 SHAP values for a single prediction.

        Runs shap.TreeExplainer against the model's final pipeline step (the
        actual tree estimator, not the StandardScaler wrapper). Handles both
        plain estimators and sklearn Pipeline objects transparently.

        Args:
            model:         A fitted sklearn estimator or Pipeline whose last step
                           is a tree-based model (RandomForest, GradientBoosting,
                           IsolationForest, etc.).
            features:      Feature dict used for the prediction — keys must match
                           feature_names order.
            feature_names: Ordered list of feature names corresponding to the
                           columns the model was trained on.

        Returns:
            Dict of up to 3 feature names mapped to their SHAP values, ordered
            by descending absolute value. Returns an empty dict on any failure.
        """
        try:
            import shap  # type: ignore[import]
            import numpy as np
            from sklearn.pipeline import Pipeline  # type: ignore[import]

            # Unwrap Pipeline to reach the tree estimator — TreeExplainer does
            # not accept Pipeline objects directly.
            estimator = model
            if isinstance(model, Pipeline):
                estimator = model.steps[-1][1]

            explainer = shap.TreeExplainer(estimator)

            # Build the single-row feature matrix in the correct column order.
            row = np.array(
                [float(features.get(name, 0.0)) for name in feature_names],
                dtype=float,
            ).reshape(1, -1)

            shap_values = explainer.shap_values(row)

            # shap_values shape varies by model type:
            #   - binary classifier (RF/GBM): list of two arrays → take class-1
            #   - single-output regressor / IsolationForest: single 2-D array
            if isinstance(shap_values, list):
                # Binary classifier: index 1 = positive-class (fraud / churn)
                values_1d = shap_values[1][0]
            else:
                values_1d = shap_values[0]

            # Pair names with values, sort by |shap| descending, take top 3.
            named = list(zip(feature_names, values_1d.tolist()))
            named.sort(key=lambda pair: abs(pair[1]), reverse=True)
            return {name: float(val) for name, val in named[:3]}

        except Exception:
            logger.exception("Explainer.explain_tree failed")
            return {}

    def to_plain_language(self, score_type: str, top_factors: dict) -> str:
        """Render top SHAP factors as a one-sentence human-readable explanation.

        Args:
            score_type:   One of 'quality', 'fraud_risk', 'churn_risk', 'ranking'.
            top_factors:  Dict of feature_name → shap_value (keys used as labels).

        Returns:
            A plain English string. Returns a generic fallback sentence if
            score_type is unrecognised or top_factors is empty.
        """
        factor_names = list(top_factors.keys())

        if not factor_names:
            return "No explanation factors available."

        factors_str = ", ".join(factor_names)

        if score_type == "quality":
            # Determine high/low from the sign of the dominant SHAP value.
            dominant_val = next(iter(top_factors.values()), 0.0)
            quality_label = "high" if dominant_val >= 0 else "low"
            return (
                f"This referral scored {quality_label} quality. "
                f"Key factors: {factors_str}."
            )

        if score_type == "fraud_risk":
            return f"Fraud risk flagged due to: {factors_str}."

        if score_type == "churn_risk":
            return f"Churn risk driven by: {factors_str}."

        if score_type == "ranking":
            return f"Partner ranking influenced by: {factors_str}."

        return f"Score influenced by: {factors_str}."
