# -----------------------------------------------------------------------------
# backend/app/core/setting_definitions.py
#
# Single source of truth for every runtime business setting stored in the
# `settings` table: its default value, description and validator. Used by
# SettingService (to reject bad admin edits with 422 and to fall back to a
# sane default when a row is missing), by the admin Settings UI (via the
# /settings/schema endpoint) and by the test fixtures that seed the table.
# Alembic migrations deliberately do NOT import this module — they carry
# their own literal seed values so they stay reproducible forever.
# -----------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


class SettingValidationError(ValueError):
    """Raised when a value is not acceptable for a given setting key."""


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    default: Any
    description: str
    kind: str  # "number" | "integer" | "enum" | "object"
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    exclusive_minimum: bool = False
    choices: tuple[str, ...] = ()
    object_keys: tuple[str, ...] = ()
    unit: Optional[str] = None
    extra_check: Optional[Callable[[Any], None]] = field(default=None, compare=False)

    # ------------------------------------------------------------------ #
    def validate(self, value: Any) -> Any:
        """Return the normalised value or raise SettingValidationError."""
        if self.kind == "enum":
            if not isinstance(value, str) or value not in self.choices:
                raise SettingValidationError(
                    f"{self.key} must be one of {', '.join(self.choices)}"
                )
            return value

        if self.kind in ("number", "integer"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                # Accept numeric strings coming from form inputs.
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    raise SettingValidationError(f"{self.key} must be a number") from None
            if self.kind == "integer":
                if float(value) != int(float(value)):
                    raise SettingValidationError(f"{self.key} must be a whole number")
                value = int(float(value))
            else:
                value = float(value)
            if self.minimum is not None:
                if self.exclusive_minimum and value <= self.minimum:
                    raise SettingValidationError(f"{self.key} must be greater than {self.minimum}")
                if not self.exclusive_minimum and value < self.minimum:
                    raise SettingValidationError(f"{self.key} must be at least {self.minimum}")
            if self.maximum is not None and value > self.maximum:
                raise SettingValidationError(f"{self.key} must be at most {self.maximum}")
            return value

        if self.kind == "object":
            if not isinstance(value, dict):
                raise SettingValidationError(f"{self.key} must be an object")
            missing = [k for k in self.object_keys if k not in value]
            unknown = [k for k in value if k not in self.object_keys]
            if missing or unknown:
                raise SettingValidationError(
                    f"{self.key} must have exactly the keys {', '.join(self.object_keys)}"
                )
            if self.extra_check:
                self.extra_check(value)
            return value

        raise SettingValidationError(f"Unsupported setting kind for {self.key}")

    def to_schema(self) -> dict:
        return {
            "key": self.key,
            "kind": self.kind,
            "default": self.default,
            "description": self.description,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "exclusive_minimum": self.exclusive_minimum,
            "choices": list(self.choices),
            "object_keys": list(self.object_keys),
            "unit": self.unit,
        }


def _check_weights(value: dict) -> None:
    for k, v in value.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            raise SettingValidationError(f"ranking.weights.{k} must be a non-negative number")
    if sum(value.values()) <= 0:
        raise SettingValidationError("ranking.weights must not all be zero")


_DEFINITIONS: tuple[SettingDefinition, ...] = (
    SettingDefinition(
        "commission.default_type", "percentage",
        "Default commission type applied when the partner's tier gives no rate.",
        kind="enum", choices=("percentage", "fixed"),
    ),
    SettingDefinition(
        "commission.default_percentage", 0.10,
        "Default commission rate as a decimal fraction (0.10 = 10%).",
        kind="number", minimum=0, maximum=1, exclusive_minimum=True, unit="fraction",
    ),
    SettingDefinition(
        "commission.default_fixed_amount", 10.00,
        "Fixed commission amount in base currency when the type is fixed.",
        kind="number", minimum=0, unit="currency",
    ),
    SettingDefinition(
        "wallet.min_withdrawal_amount", 10.00,
        "Smallest amount a partner may request in one withdrawal.",
        kind="number", minimum=0, exclusive_minimum=True, unit="currency",
    ),
    SettingDefinition(
        "wallet.auto_approval_threshold", 100.00,
        "Withdrawals below this amount (and within this amount per rolling 24h) are "
        "auto-approved unless the partner has a fraud flag pending review.",
        kind="number", minimum=0, unit="currency",
    ),
    SettingDefinition(
        "referral.attribution_model", "last_click",
        "Which click in the attribution window is credited: first_click or last_click.",
        kind="enum", choices=("first_click", "last_click"),
    ),
    SettingDefinition(
        "referral.attribution_window_days", 30,
        "Number of days a referral click remains valid for conversion attribution.",
        kind="integer", minimum=1, maximum=365, unit="days",
    ),
    SettingDefinition(
        "fraud.alert_threshold", 70,
        "Fraud risk score (0-100) above which a fraud flag is raised for admin review.",
        kind="number", minimum=0, maximum=100, unit="score",
    ),
    SettingDefinition(
        "fraud.max_clicks_per_hour", 20,
        "Clicks from one IP within an hour before the click-burst fraud rule triggers.",
        kind="integer", minimum=1, unit="clicks",
    ),
    SettingDefinition(
        "fraud.max_device_partner_spread", 3,
        "Distinct partners one device may click within 24h before the device-reuse rule triggers.",
        kind="integer", minimum=1, unit="partners",
    ),
    SettingDefinition(
        "fraud.rule_weight", 25,
        "Points each triggered fraud rule adds to the model's fraud score (0-100 scale).",
        kind="number", minimum=0, maximum=100, unit="score",
    ),
    SettingDefinition(
        "churn.alert_threshold", 65,
        "Churn risk score (0-100) above which a partner is shown as at risk.",
        kind="number", minimum=0, maximum=100, unit="score",
    ),
    SettingDefinition(
        "ranking.weights", {"quality": 0.4, "churn": 0.2, "volume": 0.2, "revenue": 0.2},
        "Weights for the composite partner ranking score.",
        kind="object", object_keys=("quality", "churn", "volume", "revenue"),
        extra_check=_check_weights,
    ),
    SettingDefinition(
        "ai.batch_scoring_interval_hours", 24,
        "How often churn and ranking scores are recomputed automatically (0 disables).",
        kind="integer", minimum=0, maximum=168, unit="hours",
    ),
)

SETTING_DEFINITIONS: dict[str, SettingDefinition] = {d.key: d for d in _DEFINITIONS}


def default_for(key: str) -> Any:
    definition = SETTING_DEFINITIONS.get(key)
    return definition.default if definition else None
