# -----------------------------------------------------------------------------
# backend/app/services/synthetic_data_service.py
#
# Orchestrates the five SyntheticDataGenerator methods in order to produce a
# coherent training dataset in a single admin call (AI-DATA-002).
#
# Transaction note: each generator method commits its own transaction (see
# AI-DATA-001 docstring). This service does not wrap them in an outer
# transaction because SQLAlchemy async sessions don't support nested real
# transactions without SAVEPOINTs, and the atomicity guarantee here is
# "all-or-nothing per step" rather than "all steps or none." A failure in
# generate_conversions leaves committed partners and clicks, which is
# acceptable for synthetic training data — re-running the endpoint on the
# same DB is safe and idempotent in outcome (all rows carry is_synthetic=True).
#
# Commission logic is intentionally skipped for synthetic conversions:
# - Synthetic rows must never trigger wallet balance changes.
# - ReferralConversionService.record_conversion() calls CommissionService,
#   which modifies partner wallets; we bypass it entirely by calling the
#   generator directly.
# -----------------------------------------------------------------------------

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.generators.synthetic_data_generator import SyntheticDataGenerator
from app.schemas.synthetic_data import SyntheticDataRequest, SyntheticDataResponse


async def generate_and_insert(
    db: AsyncSession, request: SyntheticDataRequest
) -> SyntheticDataResponse:
    generator = SyntheticDataGenerator(db)

    # Step 1 — create partners (User + Partner + Wallet per row, all is_synthetic=True)
    partners = await generator.generate_partners(request.num_partners)
    partner_ids: list[uuid.UUID] = [p.id for p in partners]

    # Step 2 — partition partners into churned (no activity) and active (get clicks)
    # generate_churn_labelled is a pure in-memory partition — no DB writes, no await
    # for I/O, but declared async for API consistency with the other generator methods.
    churn_result = await generator.generate_churn_labelled(partner_ids, request.churn_ratio)
    active_partner_ids: list[uuid.UUID] = churn_result["active_partner_ids"]

    # Step 3 — generate clicks for active partners only; churned partners have none,
    # which is the behavioural signal the churn model will learn from.
    clicks = []
    if active_partner_ids:
        n_clicks = len(active_partner_ids) * request.num_clicks_per_partner
        clicks = await generator.generate_clicks(active_partner_ids, n_clicks)

    click_ids: list[uuid.UUID] = [c.id for c in clicks]

    # Step 4 — rewrite a fraction of clicks to exhibit fraud velocity patterns
    # (shared IP + identical UA within a 5-min burst window) and persist labels
    # in device_info JSONB as _synthetic_fraud_label.
    if click_ids and request.fraud_ratio > 0.0:
        await generator.generate_fraud_labelled(click_ids, request.fraud_ratio)

    # Step 5 — generate conversions referencing the click pool; no CommissionService
    # call, no wallet mutations.
    conversions = []
    if click_ids and request.num_conversions > 0:
        conversions = await generator.generate_conversions(click_ids, request.num_conversions)

    return SyntheticDataResponse(
        partners_created=len(partners),
        clicks_created=len(clicks),
        conversions_created=len(conversions),
    )
