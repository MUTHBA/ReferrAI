# -----------------------------------------------------------------------------
# backend/app/services/wallet_service.py
#
# Business logic for wallet mutations (COM-002, WAL-002, WAL-003, WAL-004).
# credit() is called after a commission is calculated; debit() is called when
# a withdrawal is approved. Both flush but do not commit so they can be
# composed within a larger transaction by the route handler. Withdrawal
# request logic lives in request_withdrawal(): it reads auto-approval
# thresholds and fraud-flag state from the DB, auto-approves if eligible
# (calling debit() inline), or marks the withdrawal pending for admin review.
# Admin approval/rejection lives in review_withdrawal().
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import Transaction, Withdrawal
from app.repositories.fraud_flag_repository import FraudFlagRepository
from app.repositories.partner_repository import PartnerRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.wallet_repository import WalletRepository
from app.repositories.withdrawal_repository import WithdrawalRepository
from app.services.audit_log_service import AuditLogService
from app.services.setting_service import SettingService


class WalletNotFoundError(Exception):
    def __init__(self, partner_id: uuid.UUID) -> None:
        super().__init__(f"Wallet not found for partner {partner_id}")


class InsufficientBalanceError(Exception):
    def __init__(self, balance: Decimal, requested: Decimal) -> None:
        super().__init__(f"Insufficient balance: have {balance}, requested {requested}")
        self.balance = balance
        self.requested = requested


class BelowMinimumWithdrawalError(Exception):
    def __init__(self, minimum: Decimal) -> None:
        super().__init__(f"Amount is below the minimum withdrawal of {minimum}")
        self.minimum = minimum


class WithdrawalNotFoundError(Exception):
    def __init__(self, withdrawal_id: uuid.UUID) -> None:
        super().__init__(f"Withdrawal {withdrawal_id} not found")


class WithdrawalAlreadyProcessedError(Exception):
    def __init__(self, withdrawal_id: uuid.UUID) -> None:
        super().__init__(f"Withdrawal {withdrawal_id} has already been processed")


class WalletService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.wallet_repo = WalletRepository(session)
        self.transaction_repo = TransactionRepository(session)
        self.withdrawal_repo = WithdrawalRepository(session)
        self.partner_repo = PartnerRepository(session)
        self.fraud_repo = FraudFlagRepository(session)
        self.setting_service = SettingService(session)

    async def credit(
        self, partner_id: uuid.UUID, amount: Decimal, reference_id: uuid.UUID
    ) -> Transaction:
        wallet = await self.wallet_repo.get_by_partner_id(partner_id)
        if wallet is None:
            raise WalletNotFoundError(partner_id)

        wallet.balance += amount
        wallet.total_earned += amount
        await self.session.flush()

        transaction = Transaction(
            id=uuid.uuid4(),
            wallet_id=wallet.id,
            reference_id=reference_id,
            reference_type="commission",
            amount=amount,
            balance_after=wallet.balance,
        )
        return await self.transaction_repo.create(transaction)

    async def debit(
        self, partner_id: uuid.UUID, amount: Decimal, reference_id: uuid.UUID
    ) -> Transaction:
        wallet = await self.wallet_repo.get_by_partner_id(partner_id)
        if wallet is None:
            raise WalletNotFoundError(partner_id)

        # Atomic conditional UPDATE (financial-integrity hardening) — replaces
        # the old read-check-write ("if wallet.balance < amount: raise" then
        # "wallet.balance -= amount"), which had an unguarded window between
        # the balance check and the write where two concurrent withdrawal
        # requests could both read the same balance before either committed.
        # See WalletRepository.debit_if_sufficient() for the full rationale.
        debited = await self.wallet_repo.debit_if_sufficient(wallet.id, amount)
        if debited is None:
            raise InsufficientBalanceError(wallet.balance, amount)
        new_balance, new_total_withdrawn = debited

        # The UPDATE above already persisted these values; assign them to the
        # in-memory ORM object too so any code that reads wallet.balance /
        # wallet.total_withdrawn again later in this request sees the current
        # value. This does cause one redundant (but harmless — it writes the
        # same already-correct values) UPDATE at the next flush, since any
        # attribute assignment marks the object dirty regardless of whether
        # the value actually changed.
        wallet.balance = new_balance
        wallet.total_withdrawn = new_total_withdrawn

        transaction = Transaction(
            id=uuid.uuid4(),
            wallet_id=wallet.id,
            reference_id=reference_id,
            reference_type="withdrawal",
            amount=-amount,
            balance_after=new_balance,
        )
        return await self.transaction_repo.create(transaction)

    async def get_wallet(self, partner_id: uuid.UUID):
        wallet = await self.wallet_repo.get_by_partner_id(partner_id)
        if wallet is None:
            raise WalletNotFoundError(partner_id)
        return wallet

    async def get_transactions(self, partner_id: uuid.UUID) -> list[Transaction]:
        wallet = await self.wallet_repo.get_by_partner_id(partner_id)
        if wallet is None:
            raise WalletNotFoundError(partner_id)
        from sqlalchemy import select
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.wallet_id == wallet.id)
            .order_by(Transaction.created_at.desc())
        )
        return list(result.scalars().all())

    async def request_withdrawal(
        self, user_id: uuid.UUID, amount: Decimal
    ) -> Withdrawal:
        partner = await self.partner_repo.get_by_user_id(user_id)
        if partner is None:
            raise WalletNotFoundError(user_id)

        min_amount = Decimal(
            str(await self.setting_service.get("wallet.min_withdrawal_amount", 10.0))
        )
        if amount < min_amount:
            raise BelowMinimumWithdrawalError(min_amount)

        wallet = await self.wallet_repo.get_by_partner_id(partner.id)
        if wallet is None:
            raise WalletNotFoundError(partner.id)
        if wallet.balance < amount:
            raise InsufficientBalanceError(wallet.balance, amount)

        auto_threshold = Decimal(
            str(await self.setting_service.get("wallet.auto_approval_threshold", 100.0))
        )
        has_fraud_flag = await self.fraud_repo.has_active_flag(partner.id)
        auto_approve = amount <= auto_threshold and not has_fraud_flag

        withdrawal = Withdrawal(
            id=uuid.uuid4(),
            partner_id=partner.id,
            wallet_id=wallet.id,
            amount=amount,
            status="approved" if auto_approve else "pending",
            requires_manual_review=not auto_approve,
        )
        await self.withdrawal_repo.create(withdrawal)

        if auto_approve:
            await self.debit(partner.id, amount, withdrawal.id)

        await self.session.commit()
        return withdrawal

    async def review_withdrawal(
        self,
        withdrawal_id: uuid.UUID,
        action: str,
        reviewer_id: uuid.UUID,
        notes: Optional[str] = None,
    ) -> Withdrawal:
        withdrawal = await self.withdrawal_repo.get_by_id(withdrawal_id)
        if withdrawal is None:
            raise WithdrawalNotFoundError(withdrawal_id)
        if withdrawal.status != "pending":
            raise WithdrawalAlreadyProcessedError(withdrawal_id)

        withdrawal.status = action  # "approved" or "rejected"
        withdrawal.reviewed_by = reviewer_id
        withdrawal.reviewed_at = datetime.now(timezone.utc)
        withdrawal.notes = notes
        await self.session.flush()

        if action == "approved":
            await self.debit(withdrawal.partner_id, withdrawal.amount, withdrawal.id)

        await AuditLogService(self.session).log(
            user_id=reviewer_id,
            action=f"withdrawal.{action}",
            entity_type="withdrawal",
            entity_id=withdrawal.id,
            old_value="pending",
            new_value=action,
        )
        await self.session.commit()
        return withdrawal

    async def list_withdrawals(self, status: Optional[str] = None) -> list[Withdrawal]:
        return await self.withdrawal_repo.list_by_status(status)
