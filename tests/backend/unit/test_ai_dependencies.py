# -----------------------------------------------------------------------------
# tests/backend/unit/test_ai_dependencies.py
#
# Regression guard for backend/requirements-ml.txt (+ requirements-embeddings.txt).
#
# On 2026-07-07, main's commit 3daf8f0 intentionally excluded shap and
# sentence-transformers from requirements-ml.txt to sidestep two Docker build
# problems (shap needs a C++ compiler; sentence-transformers pulls in a large
# PyTorch dependency). This branch solved both problems properly instead —
# backend/Dockerfile installs build-essential (so shap's native g++ extension
# compiles) and installs torch from the CPU-only wheel index before the rest
# of requirements-ml.txt (keeping sentence-transformers' PyTorch dependency
# small and CUDA-free) — so both packages ship in the Docker image and power
# real features: SHAP explanations (AI-XAI-001, BRD 8.7) and partner
# discovery embeddings (AI-DISC-001).
#
# NOTE (AI overhaul): sentence-transformers now lives in requirements-embeddings.txt, which
# the Dockerfile installs by default after CPU-only torch; the import checks below still
# apply to the Docker image.
#
# Both features are wrapped in broad except-clauses and degrade gracefully
# when the packages are unavailable (Explainer.explain_tree() returns {},
# PartnerDiscovery scoring returns 0.0) — the app never crashes, it just
# silently loses functionality. That means a future merge reintroducing the
# trimmed-down requirements-ml.txt would NOT be caught by any endpoint
# returning a wrong status code. These tests exist to make that regression
# loud instead of silent.
#
# These tests require the packages to actually be importable — they are NOT
# skipped when missing. Run them wherever requirements-ml.txt is installed
# (the backend Docker image, or a local venv with
# `pip install -r backend/requirements-ml.txt`). A bare
# `pip install -r requirements-test.txt` venv does not include them by
# design (keeps the rest of the suite fast/lightweight) and will correctly
# fail these tests there — that's expected, not itself a regression.
# Change: SHAP test now exercises app.ai.explain (Explainer class was replaced).
# -----------------------------------------------------------------------------

import numpy as np


def test_shap_is_importable() -> None:
    """shap must be installed — it powers SHAP explanations (AI-XAI-001, BRD 8.7).

    If this fails, requirements-ml.txt has dropped shap again (as main once
    did in commit 3daf8f0), or the Docker image is missing build-essential
    (needed to compile shap's native _cext extension).
    """
    try:
        import shap  # noqa: F401
    except ImportError as exc:
        raise AssertionError(
            "shap is required for AI-XAI explainability (BRD 8.7) — "
            "do not exclude it from requirements-ml.txt"
        ) from exc


def test_sentence_transformers_is_importable() -> None:
    """sentence_transformers must be installed — it powers partner discovery
    embeddings (AI-DISC-001).

    If this fails, requirements-ml.txt has dropped sentence-transformers
    again, or the Dockerfile stopped installing the CPU-only torch build
    ahead of it.
    """
    try:
        import sentence_transformers  # noqa: F401
    except ImportError as exc:
        raise AssertionError(
            "sentence_transformers is required for partner discovery "
            "embeddings (AI-DISC-001) — do not exclude it from "
            "requirements-ml.txt"
        ) from exc


def test_explain_produces_real_shap_values_not_the_degraded_fallback() -> None:
    """app.ai.explain must return real SHAP values for a fitted tree model.

    explain._shap_contributions() returns None on ANY failure (including shap
    being unimportable) and explain() then silently falls back to occlusion,
    so a broken shap would not fail any endpoint. Fitting a tiny pipeline
    in-memory here (no dependency on trained model files) proves shap works
    end-to-end, including the shap>=0.46 3-D (rows, features, classes) output.
    (Replaces the old Explainer.explain_tree() test: that class was replaced by
    app/ai/explain.py in the AI overhaul; the SHAP-shape guard itself is kept.)
    """
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    from app.ai import explain, registry

    feature_names = ["clicks_last_hour", "unique_devices", "account_age_days"]
    X = pd.DataFrame(
        [[1, 1, 400], [2, 1, 350], [50, 1, 2], [45, 1, 1]],
        columns=feature_names,
    )
    y = np.array([0, 0, 1, 1])
    pipeline = Pipeline(
        [("pre", StandardScaler()), ("model", RandomForestClassifier(n_estimators=10, random_state=0))]
    ).fit(X, y)
    bundle = registry.ModelBundle(
        name="quality", pipeline=pipeline, meta={"features": feature_names, "version": "test"}, mtime=0.0
    )

    result = explain._shap_contributions(
        bundle, {"clicks_last_hour": 48, "unique_devices": 1, "account_age_days": 3}, scale=1.0
    )

    assert result, (
        "explain._shap_contributions() returned None/empty for a model that was fit and "
        "passed in directly - shap is either not importable or not functioning correctly"
    )
    assert set(result) <= set(feature_names), "unexpected feature name in SHAP output"
    assert all(isinstance(v, float) for v in result.values())
