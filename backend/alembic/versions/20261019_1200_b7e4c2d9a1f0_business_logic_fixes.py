"""business logic fixes: ledger types, nullable AI scores, partial indexes, data repair

Revision ID: b7e4c2d9a1f0
Revises: 2b4f6c8e1a93
Create Date: 2026-10-19 12:00:00.000000

Schema:
  * transactions.reference_type also allows 'withdrawal_reversal' (refund of a
    rejected withdrawal) and 'commission_reversal' (admin claw-back).
  * ai_scores.score becomes nullable and gains a status column
    (ok | model_unavailable | error) so a missing/failed model stores NULL
    instead of a fake score.
  * Partial indexes on the non-synthetic rows that dashboards query.
  * New setting ai.batch_scoring_interval_hours.

Data repair (idempotent):
  * Partners without a tier are moved to the lowest-rank tier.
  * Withdrawals that are still 'pending' now hold their funds: the amount is
    debited (with a ledger row) where the balance allows it; otherwise the
    request is rejected with an explanatory note, because the old code let
    partners request more than they had.
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e4c2d9a1f0"
down_revision: Union[str, None] = "2b4f6c8e1a93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

settings_table = sa.table(
    "settings",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("key", sa.String),
    sa.column("value", postgresql.JSONB),
    sa.column("description", sa.Text),
)

_PARTIAL_INDEXES = (
    ("ix_referral_clicks_real_partner_time", "referral_clicks", ["partner_id", "clicked_at"]),
    ("ix_referral_conversions_real_partner_time", "referral_conversions", ["partner_id", "converted_at"]),
    ("ix_partners_real_status", "partners", ["status"]),
)


def upgrade() -> None:
    # --- ledger reference types -------------------------------------------
    op.drop_constraint("ck_transactions_reference_type", "transactions", type_="check")
    op.create_check_constraint(
        "ck_transactions_reference_type",
        "transactions",
        "reference_type IN ('commission', 'withdrawal', 'withdrawal_reversal', 'commission_reversal')",
    )

    # --- nullable AI scores + status ---------------------------------------
    op.add_column(
        "ai_scores",
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'ok'")),
    )
    op.alter_column("ai_scores", "score", existing_type=sa.Numeric(5, 2), nullable=True)
    op.drop_constraint("ck_ai_scores_score_range", "ai_scores", type_="check")
    op.create_check_constraint(
        "ck_ai_scores_score_range", "ai_scores", "score IS NULL OR (score >= 0 AND score <= 100)"
    )
    op.create_check_constraint(
        "ck_ai_scores_status", "ai_scores", "status IN ('ok', 'model_unavailable', 'error')"
    )
    # Rows written by the old code when no model file existed carry the fixed
    # fallback values with model_version '1.0'. Mark them as unavailable.
    op.execute(
        "UPDATE ai_scores SET score = NULL, status = 'model_unavailable' "
        "WHERE model_version = '1.0' AND score_type IN ('quality', 'churn_risk') AND score = 50"
    )

    # --- partial indexes on real (non-synthetic) rows -----------------------
    for name, table, cols in _PARTIAL_INDEXES:
        op.create_index(name, table, cols, postgresql_where=sa.text("is_synthetic = false"))

    # --- new setting --------------------------------------------------------
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM settings WHERE key = 'ai.batch_scoring_interval_hours'")
    ).first()
    if not exists:
        op.bulk_insert(
            settings_table,
            [
                {
                    "id": uuid.uuid4(),
                    "key": "ai.batch_scoring_interval_hours",
                    "value": 24,
                    "description": "How often churn and ranking scores are recomputed automatically (0 disables).",
                }
            ],
        )

    # --- data repair: base tier ----------------------------------------------
    conn.execute(
        sa.text(
            "UPDATE partners SET tier_id = (SELECT id FROM partner_tiers ORDER BY rank_order ASC LIMIT 1) "
            "WHERE tier_id IS NULL AND EXISTS (SELECT 1 FROM partner_tiers)"
        )
    )

    # --- data repair: hold funds for pending withdrawals ----------------------
    pending = conn.execute(
        sa.text(
            "SELECT w.id, w.wallet_id, w.amount FROM withdrawals w "
            "WHERE w.status = 'pending' ORDER BY w.requested_at"
        )
    ).fetchall()
    for wid, wallet_id, amount in pending:
        held = conn.execute(
            sa.text(
                "UPDATE wallets SET balance = balance - :amt, updated_at = now() "
                "WHERE id = :wid AND balance >= :amt RETURNING balance"
            ),
            {"amt": amount, "wid": wallet_id},
        ).first()
        if held is not None:
            conn.execute(
                sa.text(
                    "INSERT INTO transactions (id, wallet_id, reference_id, reference_type, amount, balance_after, created_at) "
                    "VALUES (:id, :wallet, :ref, 'withdrawal', :amt, :bal, now())"
                ),
                {"id": uuid.uuid4(), "wallet": wallet_id, "ref": wid, "amt": -amount, "bal": held[0]},
            )
        else:
            conn.execute(
                sa.text(
                    "UPDATE withdrawals SET status = 'rejected', reviewed_at = now(), "
                    "notes = 'Automatically rejected during upgrade: balance was lower than the requested amount' "
                    "WHERE id = :wid"
                ),
                {"wid": wid},
            )


def downgrade() -> None:
    conn = op.get_bind()
    # Release held funds for still-pending withdrawals (inverse of the upgrade).
    conn.execute(
        sa.text(
            "UPDATE wallets w SET balance = w.balance + p.total FROM ("
            "  SELECT wallet_id, SUM(amount) AS total FROM withdrawals WHERE status = 'pending' GROUP BY wallet_id"
            ") p WHERE w.id = p.wallet_id"
        )
    )
    conn.execute(
        sa.text(
            "DELETE FROM transactions t USING withdrawals w "
            "WHERE t.reference_id = w.id AND t.reference_type = 'withdrawal' AND w.status = 'pending'"
        )
    )
    op.execute("DELETE FROM settings WHERE key = 'ai.batch_scoring_interval_hours'")
    for name, table, _ in _PARTIAL_INDEXES:
        op.drop_index(name, table_name=table)

    op.drop_constraint("ck_ai_scores_status", "ai_scores", type_="check")
    op.drop_constraint("ck_ai_scores_score_range", "ai_scores", type_="check")
    op.execute("DELETE FROM ai_scores WHERE score IS NULL")
    op.alter_column("ai_scores", "score", existing_type=sa.Numeric(5, 2), nullable=False)
    op.create_check_constraint("ck_ai_scores_score_range", "ai_scores", "score >= 0 AND score <= 100")
    op.drop_column("ai_scores", "status")

    op.execute(
        "DELETE FROM transactions WHERE reference_type IN ('withdrawal_reversal', 'commission_reversal')"
    )
    op.drop_constraint("ck_transactions_reference_type", "transactions", type_="check")
    op.create_check_constraint(
        "ck_transactions_reference_type", "transactions", "reference_type IN ('commission', 'withdrawal')"
    )
