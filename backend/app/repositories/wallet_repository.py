# -----------------------------------------------------------------------------
# backend/app/repositories/wallet_repository.py
#
# Data access for the wallets table. create() was added in AUTH-001 for
# partner registration. get_by_partner_id() is added here (COM-002 / WAL-001)
# so WalletService can load the wallet before crediting or debiting — the
# session tracks the mutated object automatically, so no explicit update()
# method is needed.
#
# debit_if_sufficient() (financial-integrity hardening) is the exception:
# it deliberately bypasses the ORM's read-modify-write pattern with a single
# atomic UPDATE ... WHERE balance >= :amount, so a withdrawal debit can never
# race against a concurrent debit on the same wallet and push balance
# negative — see WalletService.debit() for the full rationale.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update
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

    async def debit_if_sufficient(
        self, wallet_id: uuid.UUID, amount: Decimal
    ) -> Optional[tuple[Decimal, Decimal]]:
        """Atomically debit `amount` from balance and add it to
        total_withdrawn — but only if balance >= amount at the moment the
        UPDATE executes.

        This is a single UPDATE ... WHERE balance >= :amount statement
        rather than a read-check-write, so it is safe against two
        concurrent debits racing on the same wallet regardless of
        deployment topology: the database's own row-level write atomicity
        enforces this, not any application-level coordination (no
        SELECT ... FOR UPDATE, no in-process lock), so it holds equally
        under single-worker asyncio concurrency and true multi-process /
        multi-worker concurrency (e.g. `--workers 4` in production).

        Returns (new_balance, new_total_withdrawn) on success, or None if
        the balance was insufficient at the moment of the update — the
        caller should treat None the same as the old "balance < amount"
        check.
        """
        result = await self.session.execute(
            update(Wallet)
            .where(Wallet.id == wallet_id, Wallet.balance >= amount)
            .values(
                balance=Wallet.balance - amount,
                total_withdrawn=Wallet.total_withdrawn + amount,
            )
            .returning(Wallet.balance, Wallet.total_withdrawn)
        )
        row = result.first()
        return (row[0], row[1]) if row is not None else None
