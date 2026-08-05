# Alembic migration — adds external_reference column + unique constraint to referral_conversions for idempotent conversion recording.
"""add external_reference to referral_conversions

Revision ID: 1ad36e5a9ff1
Revises: f1c2d3e4a567
Create Date: 2026-07-16 15:17:44.269299

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ad36e5a9ff1'
down_revision: Union[str, None] = 'f1c2d3e4a567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add as nullable first so the ALTER succeeds on tables that already have rows.
    op.add_column(
        'referral_conversions',
        sa.Column('external_reference', sa.String(length=255), nullable=True),
    )
    # Backfill pre-existing rows with a unique sentinel derived from their PK
    # so the NOT NULL + unique constraint can be applied without conflicts.
    op.execute(
        "UPDATE referral_conversions "
        "SET external_reference = 'legacy-' || id::text "
        "WHERE external_reference IS NULL"
    )
    # Tighten to NOT NULL now that every row has a value.
    op.alter_column('referral_conversions', 'external_reference', nullable=False)
    op.create_index(
        op.f('ix_referral_conversions_external_reference'),
        'referral_conversions', ['external_reference'], unique=False,
    )
    op.create_unique_constraint(
        'uq_referral_conversions_partner_external_ref',
        'referral_conversions', ['partner_id', 'external_reference'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_referral_conversions_partner_external_ref', 'referral_conversions', type_='unique')
    op.drop_index(op.f('ix_referral_conversions_external_reference'), table_name='referral_conversions')
    op.drop_column('referral_conversions', 'external_reference')
