# -----------------------------------------------------------------------------
# backend/app/repositories/transaction_repository.py
#
# Append-only data access for the transactions table. Transactions are the
# immutable ledger entries written by WalletService.credit() and .debit() —
# they are never updated or deleted. Callers flush; the enclosing service
# method commits (or the route handler does so via the session context).
# -----------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import Transaction


class TransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, transaction: Transaction) -> Transaction:
        self.session.add(transaction)
        await self.session.flush()
        return transaction
