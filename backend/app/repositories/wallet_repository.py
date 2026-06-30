# -----------------------------------------------------------------------------
# backend/app/repositories/wallet_repository.py
#
# Data access for the wallets table. create() was added in AUTH-001 for
# partner registration. get_by_partner_id() is added here (COM-002 / WAL-001)
# so WalletService can load the wallet before crediting or debiting — the
# session tracks the mutated object automatically, so no explicit update()
# method is needed.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import Wallet


class WalletRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, wallet: Wallet) -> Wallet:
        self.session.add(wallet)
        await self.session.flush()
        return wallet

    async def get_by_partner_id(self, partner_id: uuid.UUID) -> Optional[Wallet]:
        result = await self.session.execute(
            select(Wallet).where(Wallet.partner_id == partner_id)
        )
        return result.scalar_one_or_none()
