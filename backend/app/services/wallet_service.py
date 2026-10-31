# -----------------------------------------------------------------------------
# backend/app/services/wallet_service.py
#
# Wallet mutations (COM-002, WAL-002..004). All balance changes go through
# credit()/debit(), which take a row lock on the wallet first so concurrent
# requests serialise, and write a ledger row in `transactions`. They flush but
# never commit, so callers compose them into one atomic transaction.
#
# Withdrawal lifecycle:
#   request  -> funds are HELD immediately (debited, ledger 'withdrawal'), so a
#               partner can never have pending requests worth more than their
#               balance. Auto-approved when amount < wallet.auto_approval_threshold,
#               the rolling-24h auto-approved total stays within that threshold,
#               and the partner has no fraud flag pending review.
#   approve  -> no money moves (already held); total_withdrawn increases.
#   reject   -> held funds are returned (ledger 'withdrawal_reversal').
#   mark_paid-> approved -> paid once the payout has actually been sent.
# Every admin action and every auto-approval writes an audit_logs row.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import Partner
from app.models.wallet import Transaction, Wallet, Withdrawal
from app.repositories.fraud_flag_repository import FraudFlagRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.wallet_repository import WalletRepository
from app.repositories.withdrawal_repository import WithdrawalRepository
from app.services.audit_log_service import AuditLogService
from app.services.setting_service import SettingService

CENT = Decimal("0.01")


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


class PartnerNotActiveError(Exception):
    def __init__(self, status: str) -> None:
        super().__init__(f"Partner account is {status}")
        self.status = status


class WithdrawalNotFoundError(Exception):
    def __init__(self, withdrawal_id: uuid.UUID) -> None:
        super().__init__(f"Withdrawal {withdrawal_id} not found")


class WithdrawalAlreadyProcessedError(Exception):
    def __init__(self, withdrawal_id: uuid.UUID, status: str = "") -> None:
        super().__init__(f"Withdrawal {withdrawal_id} is already {status or 'processed'}")


class WalletService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.wallet_repo = WalletRepository(session)
        self.transaction_repo = TransactionRepository(session)
        self.withdrawal_repo = WithdrawalRepository(session)
        self.fraud_repo = FraudFlagRepository(session)
        self.setting_service = SettingService(session)

    # ------------------------------------------------------------------ #
    # Ledger primitives
    # ------------------------------------------------------------------ #
    async def _locked_wallet(self, partner_id: uuid.UUID) -> Wallet:
        wallet = await self.wallet_repo.get_by_partner_id(partner_id, for_update=True)
        if wallet is None:
            raise WalletNotFoundError(partner_id)
        return wallet

    async def _ledger(self, wallet: Wallet, amount: Decimal, reference_id: uuid.UUID, reference_type: str) -> Transaction:
        return await self.transaction_repo.create(
            Transaction(
                id=uuid.uuid4(),
                wallet_id=wallet.id,
                reference_id=reference_id,
                reference_type=reference_type,
                amount=amount,
                balance_after=wallet.balance,
            )
        )

    async def credit(
        self,
        partner_id: uuid.UUID,
        amount: Decimal,
        reference_id: uuid.UUID,
        reference_type: str = "commission",
    ) -> Transaction:
        """Add money to a wallet. Commission credits also count toward total_earned."""
        amount = Decimal(amount).quantize(CENT)
        wallet = await self._locked_wallet(partner_id)
        wallet.balance += amount
        if reference_type == "commission":
            wallet.total_earned += amount
        await self.session.flush()
        return await self._ledger(wallet, amount, reference_id, reference_type)

    async def debit(
        self,
        partner_id: uuid.UUID,
        amount: Decimal,
        reference_id: uuid.UUID,
        reference_type: str = "withdrawal",
    ) -> Transaction:
        amount = Decimal(amount).quantize(CENT)
        wallet = await self._locked_wallet(partner_id)
        if wallet.balance < amount:
            raise InsufficientBalanceError(wallet.balance, amount)
        wallet.balance -= amount
        if reference_type == "commission_reversal":
            wallet.total_earned -= amount
        await self.session.flush()
        return await self._ledger(wallet, -amount, reference_id, reference_type)

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    async def get_wallet(self, partner_id: uuid.UUID) -> tuple[Wallet, Decimal]:
        """Return (wallet, amount currently held by pending withdrawals)."""
        wallet = await self.wallet_repo.get_by_partner_id(partner_id)
        if wallet is None:
            raise WalletNotFoundError(partner_id)
        return wallet, await self.withdrawal_repo.sum_pending(partner_id)

    async def get_transactions(self, partner_id: uuid.UUID) -> list[Transaction]:
        wallet = await self.wallet_repo.get_by_partner_id(partner_id)
        if wallet is None:
            raise WalletNotFoundError(partner_id)
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.wallet_id == wallet.id)
            .order_by(Transaction.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_withdrawals(
        self, status: Optional[str] = None, partner_id: Optional[uuid.UUID] = None
    ) -> Sequence[Row]:
        return await self.withdrawal_repo.list_with_partner(status, partner_id)

    async def partners_with_open_fraud_flags(self) -> set[uuid.UUID]:
        from app.models.fraud_flag import FraudFlag

        rows = await self.session.execute(
            select(FraudFlag.partner_id).where(FraudFlag.status == "pending_review").distinct()
        )
        return set(rows.scalars().all())

    async def describe_transactions(self, transactions: list[Transaction]) -> dict[uuid.UUID, str]:
        """Plain-language label per transaction id, e.g. "Commission for demo-order-2041"."""
        from app.models.commission import Commission
        from app.models.referral import ReferralConversion

        commission_ids = {
            t.reference_id for t in transactions if t.reference_type in ("commission", "commission_reversal")
        }
        orders: dict[uuid.UUID, str] = {}
        if commission_ids:
            rows = await self.session.execute(
                select(Commission.id, ReferralConversion.external_reference)
                .join(ReferralConversion, ReferralConversion.id == Commission.conversion_id)
                .where(Commission.id.in_(commission_ids))
            )
            orders = {cid: ref for cid, ref in rows.all()}
        labels = {
            "commission": "Commission for {order}",
            "commission_reversal": "Commission reversed for {order}",
            "withdrawal": "Withdrawal",
            "withdrawal_reversal": "Withdrawal refunded",
        }
        out = {}
        for t in transactions:
            order = orders.get(t.reference_id, "an order")
            out[t.id] = labels.get(t.reference_type, t.reference_type).format(order=order)
        return out

    async def list_partner_withdrawals(self, partner_id: uuid.UUID) -> list[Withdrawal]:
        return await self.withdrawal_repo.list_by_partner(partner_id)

    # ------------------------------------------------------------------ #
    # Withdrawal lifecycle
    # ------------------------------------------------------------------ #
    async def request_withdrawal(self, partner: Partner, amount: Decimal) -> Withdrawal:
        if partner.status != "active":
            raise PartnerNotActiveError(partner.status)

        amount = Decimal(amount).quantize(CENT)
        min_amount = Decimal(str(await self.setting_service.get("wallet.min_withdrawal_amount")))
        if amount < min_amount:
            raise BelowMinimumWithdrawalError(min_amount)

        # Lock first so the balance check and the hold are atomic.
        wallet = await self._locked_wallet(partner.id)
        if wallet.balance < amount:
            raise InsufficientBalanceError(wallet.balance, amount)

        threshold = Decimal(str(await self.setting_service.get("wallet.auto_approval_threshold")))
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_auto = await self.withdrawal_repo.sum_auto_approved_since(partner.id, since)
        has_flag = await self.fraud_repo.has_active_flag(partner.id)
        auto_approve = amount < threshold and recent_auto + amount <= threshold and not has_flag

        withdrawal = Withdrawal(
            id=uuid.uuid4(),
            partner_id=partner.id,
            wallet_id=wallet.id,
            amount=amount,
            status="approved" if auto_approve else "pending",
            requires_manual_review=not auto_approve,
            reviewed_at=datetime.now(timezone.utc) if auto_approve else None,
            notes="Auto-approved" if auto_approve else None,
        )
        await self.withdrawal_repo.create(withdrawal)
        await self.debit(partner.id, amount, withdrawal.id, "withdrawal")  # hold funds

        if auto_approve:
            wallet.total_withdrawn += amount
            await AuditLogService(self.session).log(
                user_id=None,
                action="withdrawal.auto_approved",
                entity_type="withdrawal",
                entity_id=withdrawal.id,
                old_value=None,
                new_value={"amount": amount, "threshold": threshold, "recent_auto_total": recent_auto},
            )

        await self.session.commit()
        return withdrawal

    async def review_withdrawal(
        self,
        withdrawal_id: uuid.UUID,
        action: str,
        reviewer_id: uuid.UUID,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Withdrawal:
        withdrawal = await self.withdrawal_repo.get_by_id(withdrawal_id, for_update=True)
        if withdrawal is None:
            raise WithdrawalNotFoundError(withdrawal_id)
        if withdrawal.status != "pending":
            raise WithdrawalAlreadyProcessedError(withdrawal_id, withdrawal.status)

        if action == "approved":
            wallet = await self._locked_wallet(withdrawal.partner_id)
            wallet.total_withdrawn += withdrawal.amount
        elif action == "rejected":
            await self.credit(withdrawal.partner_id, withdrawal.amount, withdrawal.id, "withdrawal_reversal")
        else:
            raise ValueError(f"Unsupported review action {action!r}")

        withdrawal.status = action
        withdrawal.reviewed_by = reviewer_id
        withdrawal.reviewed_at = datetime.now(timezone.utc)
        withdrawal.notes = notes
        await self.session.flush()

        await AuditLogService(self.session).log(
            user_id=reviewer_id,
            action=f"withdrawal.{action}",
            entity_type="withdrawal",
            entity_id=withdrawal.id,
            old_value={"status": "pending"},
            new_value={"status": action, "amount": withdrawal.amount, "notes": notes},
            ip_address=ip_address,
        )
        await self.session.commit()
        return withdrawal

    async def mark_paid(
        self,
        withdrawal_id: uuid.UUID,
        admin_id: uuid.UUID,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Withdrawal:
        withdrawal = await self.withdrawal_repo.get_by_id(withdrawal_id, for_update=True)
        if withdrawal is None:
            raise WithdrawalNotFoundError(withdrawal_id)
        if withdrawal.status != "approved":
            raise WithdrawalAlreadyProcessedError(withdrawal_id, withdrawal.status)
        withdrawal.status = "paid"
        if notes:
            withdrawal.notes = notes
        await self.session.flush()
        await AuditLogService(self.session).log(
            user_id=admin_id,
            action="withdrawal.paid",
            entity_type="withdrawal",
            entity_id=withdrawal.id,
            old_value={"status": "approved"},
            new_value={"status": "paid", "amount": withdrawal.amount},
            ip_address=ip_address,
        )
        await self.session.commit()
        return withdrawal
