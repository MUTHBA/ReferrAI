# Alembic migration — adds a CHECK(conversion_value > 0) constraint to referral_conversions (financial-integrity defense-in-depth, matches ConversionCreate.conversion_value's Field(gt=0)).
"""add conversion_value positive check to referral_conversions

Revision ID: 2b4f6c8e1a93
Revises: 1ad36e5a9ff1
Create Date: 2026-08-06 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2b4f6c8e1a93'
down_revision: Union[str, None] = '1ad36e5a9ff1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOT VALID: applies to every new/future INSERT and UPDATE immediately,
    # but does not scan and fail on any pre-existing rows that already
    # violate it. Money-critical constraints should never be blocked from
    # deploying by stale bad data — clean up existing violators separately
    # (a data-fix script, not this migration) and run
    # `VALIDATE CONSTRAINT ck_referral_conversions_conversion_value_positive`
    # once they're gone if full historical validation is ever required.
    op.execute(
        "ALTER TABLE referral_conversions "
        "ADD CONSTRAINT ck_referral_conversions_conversion_value_positive "
        "CHECK (conversion_value > 0) NOT VALID"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE referral_conversions "
        "DROP CONSTRAINT ck_referral_conversions_conversion_value_positive"
    )
