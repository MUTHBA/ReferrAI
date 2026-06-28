# -----------------------------------------------------------------------------
# backend/app/repositories/wallet_repository.py
#
# Data access for the wallets table. Currently just create(), used by
# AuthService.register() to give a new partner a zero-balance Wallet row at
# signup time. Credit/debit methods belong to the wallet/payout vertical,
# not here.
# -----------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import Wallet


class WalletRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, wallet: Wallet) -> Wallet:
        self.session.add(wallet)
        await self.session.flush()
        return wallet
