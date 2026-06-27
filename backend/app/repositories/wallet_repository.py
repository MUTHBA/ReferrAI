from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import Wallet


class WalletRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, wallet: Wallet) -> Wallet:
        self.session.add(wallet)
        await self.session.flush()
        return wallet
