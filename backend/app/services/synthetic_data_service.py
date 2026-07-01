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
    2. generate_clicks(ids, n)   — creates one synthetic ReferralLink per partner
                                   (to satisfy the DB CHECK constraint) then n
                                   ReferralClick rows spread across all partners,
                                   all with is_synthetic=True.
    3. generate_conversions(ids, n) — creates n ReferralConversion rows referencing
                                   the click pool, all with is_synthetic=True.
                                   No CommissionService call; no wallet mutations.

    Args:
        db:      Async SQLAlchemy session injected by FastAPI's get_db dependency.
        request: Validated request body with generation parameters.

    Returns:
        SyntheticDataResponse with the count of rows created in each table.
    """
    generator = SyntheticDataGenerator(db)

    # Step 1 — partners (User + Partner + Wallet per entry, is_synthetic=True)
    partners = await generator.generate_partners(request.num_partners)
    partner_ids: list[uuid.UUID] = [p.id for p in partners]

    # Step 2 — clicks spread across all generated partners
    n_clicks = request.num_partners * request.num_clicks_per_partner
    clicks = await generator.generate_clicks(partner_ids, n_clicks)
    click_ids: list[uuid.UUID] = [c.id for c in clicks]

    # Step 3 — conversions referencing the click pool; no commission calculation
    conversions = []
    if click_ids and request.num_conversions > 0:
        conversions = await generator.generate_conversions(click_ids, request.num_conversions)

    return SyntheticDataResponse(
        partners_created=len(partners),
        clicks_created=len(clicks),
        conversions_created=len(conversions),
    )
