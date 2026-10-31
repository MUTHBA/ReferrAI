# -----------------------------------------------------------------------------
# backend/app/ai/explain.py
#
# Per-prediction explanations (AI-XAI). explain() returns the contribution of
# each ORIGINAL feature (one-hot columns are summed back to their source
# feature) on the 0-100 score scale, plus a plain-language sentence.
#
# Method:
#   1. SHAP TreeExplainer on the fitted tree model, applied to the input AFTER
#      the pipeline's preprocessing (so it sees exactly what the model saw).
#      Handles both the 2-D and 3-D shap_values layouts and IsolationForest.
#   2. If SHAP is unavailable or fails, an occlusion fallback: replace one
#      feature at a time with its typical training value (stored in the model
#      metadata) and measure how much the score moves.
# Positive contribution = pushes the score UP.
# -----------------------------------------------------------------------------

from __future__ import annotations

import logging
from typing import Callable, Optional

import numpy as np

from app.ai import registry
from app.ai.features import FEATURE_LABELS

logger = logging.getLogger(__name__)


def _original_name(transformed: str, features: list[str]) -> str:
    # ColumnTransformer names look like "num__x" or "cat__source_type_search".
    core = transformed.split("__", 1)[-1]
    for f in sorted(features, key=len, reverse=True):
        if core == f or core.startswith(f + "_"):
            return f
    return core


def _shap_contributions(bundle: registry.ModelBundle, features: dict, scale: float) -> Optional[dict[str, float]]:
    try:
        import shap  # type: ignore[import]
    except ImportError:
        return None
    try:
        pipe = bundle.pipeline
        pre, model = pipe[:-1], pipe[-1]
        X = pre.transform(registry.frame_for(bundle, features))
        X = X.toarray() if hasattr(X, "toarray") else np.asarray(X, dtype=float)
        names = list(pre.get_feature_names_out())
        values = np.asarray(shap.TreeExplainer(model).shap_values(X))
        if values.ndim == 3:  # (rows, features, classes) -> positive class
            values = values[0, :, -1]
        elif values.ndim == 2:
            values = values[0]
        out: dict[str, float] = {}
        for n, v in zip(names, values):
            key = _original_name(n, bundle.features)
            out[key] = out.get(key, 0.0) + float(v) * scale
        return out
    except Exception:
        logger.exception("SHAP explanation failed for %s; using occlusion", bundle.name)
        return None


def _occlusion(bundle: registry.ModelBundle, features: dict, score_fn: Callable[[dict], float]) -> dict[str, float]:
    base = score_fn(features)
    baseline = bundle.meta.get("baseline", {})
    out = {}
    for f in bundle.features:
        if f not in baseline or baseline[f] == features[f]:
            out[f] = 0.0
            continue
        out[f] = base - score_fn({**features, f: baseline[f]})
    return out


def explain(
    bundle: registry.ModelBundle,
    features: dict,
    score: float,
    score_fn: Callable[[dict], float],
    subject: str,
    top_n: int = 3,
) -> tuple[dict, str]:
    """Return (contributing_factors, explanation_text)."""
    # SHAP values for a classifier are in log-odds; for the forest, in path
    # length (higher = more normal). Convert to the score's direction/scale
    # with a local linear factor so magnitudes are comparable on 0-100.
    if bundle.name == "fraud":
        scale = -10.0
    else:
        p = min(max(score / 100.0, 0.02), 0.98)
        scale = 100.0 * p * (1 - p)
    contributions = _shap_contributions(bundle, features, scale)
    method = "shap"
    if contributions is None:
        contributions = _occlusion(bundle, features, score_fn)
        method = "occlusion"

    ranked = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)
    top = [(k, v) for k, v in ranked if abs(v) >= 0.5][:top_n]
    factors = {
        "method": method,
        "model_version": bundle.version,
        "contributions": {k: round(v, 2) for k, v in ranked},
        "top_factors": [
            {
                "feature": k,
                "label": FEATURE_LABELS.get(k, k),
                "value": features.get(k),
                "effect": round(v, 2),
                "direction": "raises" if v > 0 else "lowers",
            }
            for k, v in top
        ],
        "inputs": features,
    }
    if top:
        parts = [f"{FEATURE_LABELS.get(k, k)} ({'+' if v > 0 else '−'}{abs(v):.0f})" for k, v in top]
        text = f"{subject} {score:.0f}/100. Biggest factors: " + "; ".join(parts) + "."
    else:
        text = f"{subject} {score:.0f}/100. No single factor stood out."
    return factors, text
