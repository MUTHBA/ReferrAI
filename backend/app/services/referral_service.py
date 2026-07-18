# -----------------------------------------------------------------------------
# backend/app/services/referral_service.py
#
# Scaffold placeholder — referral business logic was split into four focused
# services rather than a single monolithic ReferralService:
#   referral_link_service.py      — ReferralLink CRUD and slug generation
#   referral_code_service.py      — ReferralCode CRUD
#   referral_click_service.py     — click recording and deduplication
#   referral_conversion_service.py — conversion recording and attribution
# Attribution logic specifically lives in attribution_service.py
# (AttributionService.attribute_conversion). Route handlers in
# api/v1/routes/referrals.py import from these granular services directly.
# This file is retained as a namespace marker; it remains empty.
# -----------------------------------------------------------------------------
