# Alembic migration — adds FraudRuleEngine threshold keys to the settings table.
"""add fraud rule engine threshold settings

Revision ID: f1c2d3e4a567
Revises: a608528f6443
Create Date: 2026-07-07 09:00:00.000000

Adds two canonical settings keys consumed by FraudRuleEngine (AI-FRD-001).
These are read via SettingService.get() with safe defaults, so existing
deployments continue to function before this migration runs. The migration
seeds the preferred production defaults.

  fraud.max_clicks_per_hour       — click-burst threshold per source IP (default 20).
  fraud.max_device_partner_spread — max distinct partners a device may click across
                                    in 24 h before triggering the device-reuse rule
                                    (default 3).
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1c2d3e4a567"
down_revision: Union[str, None] = "a608528f6443"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

settings_table = sa.table(
    "settings",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("key", sa.String),
    sa.column("value", postgresql.JSONB),
    sa.column("description", sa.Text),
)


def upgrade() -> None:
    op.bulk_insert(
        settings_table,
        [
            {
                "id": uuid.uuid4(),
                "key": "fraud.max_clicks_per_hour",
                "value": 20,
                "description": (
                    "Maximum clicks allowed from a single IP address within one hour "
                    "before the clicks_per_hour_exceeded fraud rule triggers."
                ),
            },
            {
                "id": uuid.uuid4(),
                "key": "fraud.max_device_partner_spread",
                "value": 3,
                "description": (
                    "Maximum number of distinct partners a single device fingerprint "
                    "may click within 24 hours before the device_shared_across_partners "
                    "fraud rule triggers."
                ),
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        settings_table.delete().where(
            settings_table.c.key.in_(
                ["fraud.max_clicks_per_hour", "fraud.max_device_partner_spread"]
            )
        )
    )
