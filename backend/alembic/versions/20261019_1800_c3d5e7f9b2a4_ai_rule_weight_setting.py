"""seed fraud.rule_weight setting; ai_scores.status 'insufficient_data'

Revision ID: c3d5e7f9b2a4
Revises: b7e4c2d9a1f0
Create Date: 2026-10-19 18:00:00.000000

Adds fraud.rule_weight: points each triggered deterministic fraud rule adds
to the model's fraud score (idempotent), and allows ai_scores.status
'insufficient_data' (e.g. churn for partners younger than 30 days).
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d5e7f9b2a4"
down_revision: Union[str, None] = "b7e4c2d9a1f0"
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
    op.drop_constraint("ck_ai_scores_status", "ai_scores", type_="check")
    op.create_check_constraint(
        "ck_ai_scores_status", "ai_scores", "status IN ('ok', 'model_unavailable', 'insufficient_data', 'error')"
    )
    exists = op.get_bind().execute(sa.text("SELECT 1 FROM settings WHERE key = 'fraud.rule_weight'")).first()
    if not exists:
        op.bulk_insert(
            settings_table,
            [
                {
                    "id": uuid.uuid4(),
                    "key": "fraud.rule_weight",
                    "value": 25,
                    "description": "Points each triggered fraud rule adds to the model's fraud score (0-100 scale).",
                }
            ],
        )


def downgrade() -> None:
    op.execute("DELETE FROM settings WHERE key = 'fraud.rule_weight'")
    op.execute("UPDATE ai_scores SET status = 'model_unavailable' WHERE status = 'insufficient_data'")
    op.drop_constraint("ck_ai_scores_status", "ai_scores", type_="check")
    op.create_check_constraint("ck_ai_scores_status", "ai_scores", "status IN ('ok', 'model_unavailable', 'error')")
