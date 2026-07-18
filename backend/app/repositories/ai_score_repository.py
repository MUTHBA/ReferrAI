# -----------------------------------------------------------------------------
# backend/app/repositories/ai_score_repository.py
#
# Scaffold placeholder — a dedicated AIScoreRepository was not implemented.
# All AIScore reads and writes are performed directly via SQLAlchemy select/
# insert statements inside the service layer (ai_service.py, dashboard_service.py,
# partner_service.py). This was a deliberate simplification: the ai_scores table
# is append-only (scores are never updated in place), and its query patterns are
# varied enough that a generic repository would not meaningfully reduce duplication.
# If a shared repository abstraction becomes useful (e.g. for bulk score retrieval
# or model-version filtering), implement it here and inject it into ai_service.py.
# -----------------------------------------------------------------------------
