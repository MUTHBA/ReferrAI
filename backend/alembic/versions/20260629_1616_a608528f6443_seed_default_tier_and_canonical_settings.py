"""seed default tier and canonical settings

Revision ID: a608528f6443
Revises: c1019227a087
Create Date: 2026-06-29 16:16:33.346385

Inserts the Bronze PartnerTier and all 10 canonical Setting rows required for
the platform to operate. Uses lightweight sa.table() helpers so this migration
remains independent of the ORM models in app/models/.
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a608528f6443'
down_revision: Union[str, None] = 'c1019227a087'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Lightweight table helpers — no ORM model imports
# ---------------------------------------------------------------------------

partner_tiers_table = sa.table(
    'partner_tiers',
    sa.column('id', postgresql.UUID(as_uuid=True)),
    sa.column('name', sa.String),
    sa.column('rank_order', sa.Integer),
    sa.column('min_referral_count', sa.Integer),
    sa.column('min_revenue_contribution', sa.Numeric),
    sa.column('commission_type', sa.String),
    sa.column('commission_value', sa.Numeric),
)

settings_table = sa.table(
    'settings',
    sa.column('id', postgresql.UUID(as_uuid=True)),
    sa.column('key', sa.String),
    sa.column('value', postgresql.JSONB),
    sa.column('description', sa.Text),
)


def upgrade() -> None:
    op.bulk_insert(
        partner_tiers_table,
        [
            {
                'id': uuid.uuid4(),
                'name': 'Bronze',
                'rank_order': 1,
                'min_referral_count': 0,
                'min_revenue_contribution': 0,
                'commission_type': 'percentage',
                'commission_value': 0.10,
            }
        ],
    )

    op.bulk_insert(
        settings_table,
        [
            {
                'id': uuid.uuid4(),
                'key': 'commission.default_type',
                'value': 'percentage',
                'description': 'Default commission type applied when no tier override exists.',
            },
            {
                'id': uuid.uuid4(),
                'key': 'commission.default_percentage',
                'value': 0.10,
                'description': 'Default commission rate as a decimal (e.g. 0.10 = 10%).',
            },
            {
                'id': uuid.uuid4(),
                'key': 'commission.default_fixed_amount',
                'value': 10.00,
                'description': 'Fixed commission amount in base currency when type is fixed.',
            },
            {
                'id': uuid.uuid4(),
                'key': 'wallet.min_withdrawal_amount',
                'value': 10.00,
                'description': 'Minimum balance a partner must request to initiate a withdrawal.',
            },
            {
                'id': uuid.uuid4(),
                'key': 'wallet.auto_approval_threshold',
                'value': 100.00,
                'description': 'Withdrawal requests below this amount are auto-approved unless a fraud flag is active.',
            },
            {
                'id': uuid.uuid4(),
                'key': 'referral.attribution_model',
                'value': 'last_click',
                'description': 'Click attribution model: first_click or last_click.',
            },
            {
                'id': uuid.uuid4(),
                'key': 'referral.attribution_window_days',
                'value': 30,
                'description': 'Number of days a referral click remains valid for conversion attribution.',
            },
            {
                'id': uuid.uuid4(),
                'key': 'fraud.alert_threshold',
                'value': 70,
                'description': 'AI fraud score (0–100) above which a partner is flagged for admin review.',
            },
            {
                'id': uuid.uuid4(),
                'key': 'churn.alert_threshold',
                'value': 65,
                'description': 'AI churn score (0–100) above which an alert is raised for a partner.',
            },
            {
                'id': uuid.uuid4(),
                'key': 'ranking.weights',
                'value': {'quality': 0.4, 'churn': 0.2, 'volume': 0.2, 'revenue': 0.2},
                'description': 'Weight coefficients for the composite partner ranking score.',
            },
        ],
    )


def downgrade() -> None:
    settings_keys = [
        'commission.default_type',
        'commission.default_percentage',
        'commission.default_fixed_amount',
        'wallet.min_withdrawal_amount',
        'wallet.auto_approval_threshold',
        'referral.attribution_model',
        'referral.attribution_window_days',
        'fraud.alert_threshold',
        'churn.alert_threshold',
        'ranking.weights',
    ]

    op.execute(
        settings_table.delete().where(
            settings_table.c.key.in_(settings_keys)
        )
    )

    op.execute(
        partner_tiers_table.delete().where(
            partner_tiers_table.c.name == 'Bronze'
        )
    )
