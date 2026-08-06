# -----------------------------------------------------------------------------
# tests/backend/unit/test_ai_dependencies.py
#
# Regression guard for backend/requirements-ml.txt.
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


def test_explainer_produces_real_shap_values_not_the_degraded_fallback() -> None:
    """Explainer.explain_tree() must return real SHAP values for a fitted model.

    explain_tree() wraps every failure (including shap being unimportable)
    in a broad except and returns {} — the same empty dict used when a
    model file is simply missing. Fitting a tiny model in-memory here (no
    dependency on the repo's pretrained .joblib files, which aren't present
    in dev/test environments) proves shap is not just importable but
    functioning end-to-end — so a regression here fails on real, non-empty
    content, not just an import check.
    """
    from sklearn.ensemble import RandomForestClassifier

    from app.ai.explainability.explainer import Explainer

    feature_names = ["clicks_last_hour", "unique_devices", "account_age_days"]
    X = np.array(
        [
            [1, 1, 400],
            [2, 1, 350],
            [50, 1, 2],
            [45, 1, 1],
        ]
    )
    y = np.array([0, 0, 1, 1])

    model = RandomForestClassifier(n_estimators=10, random_state=0)
    model.fit(X, y)

    result = Explainer().explain_tree(
        model=model,
        features={"clicks_last_hour": 48, "unique_devices": 1, "account_age_days": 3},
        feature_names=feature_names,
    )

    assert result != {}, (
        "Explainer.explain_tree() returned the degraded-fallback empty dict "
        "for a model that was fit and passed in directly — shap is either "
        "not importable or not functioning correctly"
    )
    assert all(name in feature_names for name in result), "unexpected feature name in SHAP output"
    assert all(isinstance(v, float) for v in result.values())
