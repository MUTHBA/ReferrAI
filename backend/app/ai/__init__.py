# -----------------------------------------------------------------------------
# backend/app/ai/__init__.py
#
# Top-level AI package. Sub-packages (generators, scoring, explainability,
# discovery) are imported on demand by their callers — nothing is eagerly
# imported here so the heavy ML dependencies (scikit-learn, sentence-
# transformers, shap) only load when the relevant sub-package is first used.
# -----------------------------------------------------------------------------
