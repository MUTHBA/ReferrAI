# -----------------------------------------------------------------------------
# backend/app/ai/scoring/fraud_rules.py
#
# FraudRuleEngine — deterministic, stateless fraud rules (AI-FRD-001).
# Runs three synchronous DB-backed checks against a single referral click and
# returns the names of every triggered rule. Designed to be called alongside
# (not instead of) the Isolation Forest model in score_fraud().
#
# Rules:
#   clicks_per_hour_exceeded      — >N clicks from the same IP in the last hour.
#   device_shared_across_partners — same device fingerprint seen for >M distinct
#                                   partners in the last 24 h (device reuse fraud).
#   self_referral                 — the same IP has already produced a conversion
#                                   for this partner in the last 24 h, suggesting
#                                   the partner is clicking their own link.
#
# Thresholds are loaded from the settings table via SettingService.get() with
# safe defaults (20 and 3 respectively) so missing rows never raise.
#
# Each rule runs in its own try/except so one failing rule never silences the
# others. check() itself is also wrapped — it always returns a list, never raises.
# -----------------------------------------------------------------------------

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralClick, ReferralConversion
from app.services.setting_service import SettingService

logger = logging.getLogger(__name__)


class FraudRuleEngine:
    """Deterministic rule-based fraud checks for a single referral click.

    Usage::

        rules = FraudRuleEngine(db)
        triggered = await rules.check(click_id)
        # e.g. ["clicks_per_hour_exceeded", "self_referral"]
    """

    RULE_CLICKS_PER_HOUR: str = "clicks_per_hour_exceeded"
    RULE_DEVICE_SPREAD: str = "device_shared_across_partners"
    RULE_SELF_REFERRAL: str = "self_referral"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check(self, click_id: uuid.UUID) -> list[str]:
        """Run all rules against the click. Returns list of triggered rule names.

        Returns an empty list if the click does not exist, if any individual rule
        errors (that rule is skipped), or on any unexpected exception.
        """
        try:
            now = datetime.now(timezone.utc)
            cutoff_1h = now - timedelta(hours=1)
            cutoff_24h = now - timedelta(hours=24)

            click = await self.db.scalar(
                select(ReferralClick).where(ReferralClick.id == click_id)
            )
            if click is None:
                logger.warning("FraudRuleEngine.check: click %s not found", click_id)
                return []

            ip: str = click.ip_address or "unknown"
            partner_id: uuid.UUID = click.partner_id
            device_info: dict = click.device_info or {}
            fingerprint: str = (
                device_info.get("fingerprint")
                or device_info.get("user_agent")
                or "unknown"
            )

            svc = SettingService(self.db)
            max_cph = int(await svc.get("fraud.max_clicks_per_hour"))
            max_spread = int(await svc.get("fraud.max_device_partner_spread"))

            triggered: list[str] = []

            if await self._check_clicks_per_hour(ip, cutoff_1h, max_cph):
                triggered.append(self.RULE_CLICKS_PER_HOUR)

            if await self._check_device_spread(fingerprint, cutoff_24h, max_spread):
                triggered.append(self.RULE_DEVICE_SPREAD)

            if await self._check_self_referral(ip, partner_id, click_id, cutoff_24h):
                triggered.append(self.RULE_SELF_REFERRAL)

            return triggered

        except Exception:
            logger.exception(
                "FraudRuleEngine.check failed for click %s — returning []", click_id
            )
            return []

    # ------------------------------------------------------------------
    # Private rule implementations
    # ------------------------------------------------------------------

    async def _check_clicks_per_hour(
        self, ip: str, cutoff_1h: datetime, max_cph: int
    ) -> bool:
        """True when click count from this IP in the past hour exceeds max_cph."""
        try:
            count = await self.db.scalar(
                select(func.count())
                .select_from(ReferralClick)
                .where(ReferralClick.ip_address == ip)
                .where(ReferralClick.clicked_at >= cutoff_1h)
                .where(ReferralClick.is_synthetic == False)  # noqa: E712
            )
            return int(count or 0) > max_cph
        except Exception:
            logger.exception("FraudRuleEngine._check_clicks_per_hour failed")
            return False

    async def _check_device_spread(
        self, fingerprint: str, cutoff_24h: datetime, max_spread: int
    ) -> bool:
        """True when the same device fingerprint appears for more than max_spread
        distinct partners in the past 24 h."""
        try:
            fp_expr = func.coalesce(
                ReferralClick.device_info["fingerprint"].astext,
                ReferralClick.device_info["user_agent"].astext,
            )
            count = await self.db.scalar(
                select(func.count(func.distinct(ReferralClick.partner_id)))
                .select_from(ReferralClick)
                .where(fp_expr == fingerprint)
                .where(ReferralClick.clicked_at >= cutoff_24h)
                .where(ReferralClick.is_synthetic == False)  # noqa: E712
            )
            return int(count or 0) > max_spread
        except Exception:
            logger.exception("FraudRuleEngine._check_device_spread failed")
            return False

    async def _check_self_referral(
        self,
        ip: str,
        partner_id: uuid.UUID,
        click_id: uuid.UUID,
        cutoff_24h: datetime,
    ) -> bool:
        """True when the same IP has already produced a conversion for this partner
        in the past 24 h (proxy: the entity clicking IS the partner).

        Excludes the current click so a freshly-tracked click does not trigger
        the rule against itself even if a conversion is created in the same
        request cycle.
        """
        try:
            count = await self.db.scalar(
                select(func.count())
                .select_from(ReferralConversion)
                .join(ReferralClick, ReferralConversion.click_id == ReferralClick.id)
                .where(ReferralConversion.partner_id == partner_id)
                .where(ReferralClick.ip_address == ip)
                .where(ReferralClick.id != click_id)
                .where(ReferralConversion.converted_at >= cutoff_24h)
            )
            return int(count or 0) > 0
        except Exception:
            logger.exception("FraudRuleEngine._check_self_referral failed")
            return False
