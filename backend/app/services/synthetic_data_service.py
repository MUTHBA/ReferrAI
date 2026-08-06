# -----------------------------------------------------------------------------
# backend/app/services/synthetic_data_service.py
#
# Orchestrates SyntheticDataGenerator to produce a coherent ML training dataset
# in a single admin call (AI-DATA-002).
#
# Transaction note: each generator method commits its own sub-transaction
# (documented in AI-DATA-001). A true single-transaction wrapper would require
# SAVEPOINTs and restructuring the generator — out of scope here. The practical
# guarantee is "all-or-nothing per step": a failure mid-run leaves committed
# partners/clicks in the DB, but all rows carry is_synthetic=True so they are
# excluded from production dashboards and analytics by default.
#
# Commission logic is intentionally skipped for synthetic conversions.
# ReferralConversionService.record_conversion() calls CommissionService, which
# modifies partner wallets; we bypass it entirely by calling the generator
# directly so no wallet balance changes occur for synthetic data.
#
# Churn/fraud wiring (FR-AI-DATA-003/004): generate_churn_labelled() only
# partitions partner_ids — per its own docstring, the caller must restrict
# generate_clicks() to active_partner_ids so churned partners are left with
# no click/conversion activity, which is how train_churn_predictor.py derives
# its churn label. generate_fraud_labelled() rewrites a fraud_ratio fraction
# of the just-created clicks in place, so it must run after generate_clicks()
# and before generate_conversions() (conversions reference click_id, and
# fraud labelling doesn't change which clicks exist — only their content —
# so ordering relative to generate_conversions() doesn't otherwise matter).
# -----------------------------------------------------------------------------

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.generators.synthetic_data_generator import SyntheticDataGenerator
from app.schemas.synthetic_data import SyntheticDataRequest, SyntheticDataResponse


async def generate_and_insert(
    db: AsyncSession, request: SyntheticDataRequest
) -> SyntheticDataResponse:
    """Generate and persist a batch of synthetic referral data for ML training.

    Steps:
    1. generate_partners(n)      — creates User + Partner + Wallet triplets,
                                   all with is_synthetic=True.
    2. generate_churn_labelled(ids, churn_ratio) — partitions partners into
                                   churned/active (no DB writes).
    3. generate_clicks(active_ids, n) — creates one synthetic ReferralLink per
                                   active partner (to satisfy the DB CHECK
                                   constraint) then n ReferralClick rows spread
                                   across active partners only, all with
                                   is_synthetic=True. Churned partners receive
                                   no clicks, matching how
                                   train_churn_predictor.py derives its label.
    4. generate_fraud_labelled(ids, fraud_ratio) — rewrites a fraud_ratio
                                   fraction of the just-created clicks in place
                                   to exhibit a fraud velocity pattern, and
                                   labels every click's ground truth in
                                   device_info (both required by
                                   train_fraud_detector.py).
    5. generate_conversions(ids, n) — creates n ReferralConversion rows referencing
                                   the click pool, all with is_synthetic=True.
                                   No CommissionService call; no wallet mutations.

    Args:
        db:      Async SQLAlchemy session injected by FastAPI's get_db dependency.
        request: Validated request body with generation parameters.

    Returns:
        SyntheticDataResponse with the count of rows created/labeled in each step.
    """
    generator = SyntheticDataGenerator(db)

    # Step 1 — partners (User + Partner + Wallet per entry, is_synthetic=True)
    partners = await generator.generate_partners(request.num_partners)
    partner_ids: list[uuid.UUID] = [p.id for p in partners]

    # Step 2 — partition churned vs. active partners (no DB writes here)
    churn_partition = await generator.generate_churn_labelled(
        partner_ids, request.churn_ratio
    )
    active_partner_ids: list[uuid.UUID] = churn_partition["active_partner_ids"]
    churned_partner_ids: list[uuid.UUID] = churn_partition["churned_partner_ids"]

    # Step 3 — clicks spread across active partners only; churned partners are
    # left with zero click activity
    n_clicks = request.num_partners * request.num_clicks_per_partner
    clicks = []
    if active_partner_ids and n_clicks > 0:
        clicks = await generator.generate_clicks(active_partner_ids, n_clicks)
    click_ids: list[uuid.UUID] = [c.id for c in clicks]

    # Step 4 — rewrite a fraud_ratio fraction of the clicks with a fraud
    # velocity pattern and label every click's ground truth
    fraud_click_ids: list[uuid.UUID] = []
    if click_ids:
        fraud_labels = await generator.generate_fraud_labelled(
            click_ids, request.fraud_ratio
        )
        fraud_click_ids = fraud_labels["fraud_click_ids"]

    # Step 5 — conversions referencing the click pool; no commission calculation
    conversions = []
    if click_ids and request.num_conversions > 0:
        conversions = await generator.generate_conversions(click_ids, request.num_conversions)

    return SyntheticDataResponse(
        partners_created=len(partners),
        clicks_created=len(clicks),
        conversions_created=len(conversions),
        fraud_labeled_clicks_created=len(fraud_click_ids),
        churned_partners_created=len(churned_partner_ids),
    )
