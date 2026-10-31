# -----------------------------------------------------------------------------
# backend/app/ai/__init__.py
#
# Top-level AI package. Nothing is imported eagerly, so scikit-learn / SHAP /
# sentence-transformers only load when a module that needs them is used.
#   features.py          feature definitions shared by training and scoring
#   synthetic.py         seeded synthetic world (training data + demo rows)
#   train.py             `python -m app.ai.train` — trains and saves models
#   registry.py          loads/saves model artifacts in settings.AI_MODEL_DIR
#   explain.py           SHAP (or occlusion) explanations per prediction
#   candidate_scoring.py partner-discovery similarity scoring
#   scoring/fraud_rules  deterministic fraud rules
# -----------------------------------------------------------------------------
