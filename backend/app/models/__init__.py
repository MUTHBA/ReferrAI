# -----------------------------------------------------------------------------
# backend/app/models/__init__.py
#
# Re-exports all 16 ORM models from the app.models package. Alembic's env.py
# does `from app.models import Base` — this import triggers all model files to
# load, registering their tables on Base.metadata before autogenerate runs.
# If a new model file is created, add it here or migrations will miss its table.
# The explicit __all__ list makes IDE auto-import and static analysis reliable.
# -----------------------------------------------------------------------------

from app.models.base import Base
from app.models.user import User
from app.models.partner import Partner, PartnerTier
from app.models.referral import (
    ReferralClick,
    ReferralCode,
    ReferralConversion,
    ReferralLink,
)
from app.models.commission import Commission
from app.models.wallet import Transaction, Wallet, Withdrawal
from app.models.setting import Setting
from app.models.ai_score import AIScore
from app.models.fraud_flag import FraudFlag
from app.models.discovered_partner import DiscoveredPartner
from app.models.audit_log import AuditLog

__all__ = [
    "Base",
    "User",
    "PartnerTier",
    "Partner",
    "ReferralLink",
    "ReferralCode",
    "ReferralClick",
    "ReferralConversion",
    "Commission",
    "Wallet",
    "Withdrawal",
    "Transaction",
    "Setting",
    "AIScore",
    "FraudFlag",
    "DiscoveredPartner",
    "AuditLog",
]
