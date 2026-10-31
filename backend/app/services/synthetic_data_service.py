# -----------------------------------------------------------------------------
# backend/app/services/synthetic_data_service.py
#
# Admin "generate synthetic data" (AI-SYN): builds a synthetic world with the
# same generator the models are trained on and stores it as is_synthetic=True
# rows (partners, wallets, links, clicks, conversions) in one transaction.
# These rows are excluded from every dashboard, list and export; they exist so
# the data the models learn from can be inspected and exported for analysis.
# A fresh random seed is used per call so repeated calls never collide.
# -----------------------------------------------------------------------------

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.synthetic import generate_world, insert_world
from app.schemas.synthetic_data import SyntheticDataRequest, SyntheticDataResponse


async def generate_and_insert(db: AsyncSession, request: SyntheticDataRequest) -> SyntheticDataResponse:
    world = await anyio.to_thread.run_sync(
        lambda: generate_world(
            n_partners=request.num_partners,
            days=90,
            fraud_ratio=request.fraud_ratio,
            churn_ratio=request.churn_ratio,
            clicks_per_day=request.num_clicks_per_partner / 90.0,
            seed=None,
        )
    )
    counts = await insert_world(db, world, max_conversions=request.num_conversions)
    return SyntheticDataResponse(**counts)
