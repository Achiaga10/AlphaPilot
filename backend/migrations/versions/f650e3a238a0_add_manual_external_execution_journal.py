"""Add isolated user-recorded manual execution evidence.

Revision ID: f650e3a238a0
Revises: e9b2bc954dea
Create Date: 2026-09-14 19:02:03.457768

"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f650e3a238a0"
down_revision: str | Sequence[str] | None = "e9b2bc954dea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_execution_cases",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "portfolio_id",
            sa.UUID(),
            sa.ForeignKey("forward_portfolios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "forward_order_id",
            sa.UUID(),
            sa.ForeignKey("forward_orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("broker", sa.String(30), nullable=False),
        sa.Column("provenance", sa.String(40), nullable=False),
        sa.Column(
            "recording_complete", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("skipped_at", sa.DateTime(timezone=True)),
        sa.Column("skip_reason", sa.String(80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("forward_order_id", name="uq_external_case_forward_order"),
    )
    op.create_index("ix_external_cases_portfolio", "external_execution_cases", ["portfolio_id"])
    op.create_table(
        "external_execution_fills",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "case_id",
            sa.UUID(),
            sa.ForeignKey("external_execution_cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_key", sa.String(120), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(20, 4), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fee", sa.Numeric(20, 4)),
        sa.Column("mark_complete", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("void_reason", sa.String(200)),
        sa.Column("void_source", sa.String(40)),
        sa.CheckConstraint("quantity > 0", name="ck_external_fill_quantity_positive"),
        sa.CheckConstraint("price > 0", name="ck_external_fill_price_positive"),
        sa.CheckConstraint("fee IS NULL OR fee >= 0", name="ck_external_fill_fee_nonnegative"),
        sa.UniqueConstraint("case_id", "request_key", name="uq_external_fill_request"),
    )
    op.create_index(
        "ix_external_fills_case_created", "external_execution_fills", ["case_id", "created_at"]
    )
    op.create_table(
        "external_execution_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "portfolio_id",
            sa.UUID(),
            sa.ForeignKey("forward_portfolios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.UUID(),
            sa.ForeignKey("external_execution_cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_external_event_key"),
    )
    op.create_index(
        "ix_external_events_portfolio_created",
        "external_execution_events",
        ["portfolio_id", "created_at"],
    )

    # Older Forward orders remain visible in the new journal without changing them.
    bind = op.get_bind()
    orders = bind.execute(sa.text("SELECT id, portfolio_id, created_at FROM forward_orders")).all()
    if orders:
        cases = [
            {
                "id": uuid4(),
                "portfolio_id": order.portfolio_id,
                "forward_order_id": order.id,
                "created_at": order.created_at,
            }
            for order in orders
        ]
        bind.execute(
            sa.text(
                "INSERT INTO external_execution_cases "
                "(id, portfolio_id, forward_order_id, broker, provenance, "
                "recording_complete, created_at, updated_at) "
                "VALUES (:id, :portfolio_id, :forward_order_id, 'ALPACA', "
                "'MANUAL_USER_RECORDED', false, :created_at, :created_at)"
            ),
            cases,
        )
        bind.execute(
            sa.text(
                "INSERT INTO external_execution_events "
                "(id, portfolio_id, case_id, event_type, idempotency_key, "
                "reason_code, source, facts, created_at) "
                "VALUES (:id, :portfolio_id, :case_id, 'EXTERNAL_ACTION_READY', 'action:ready', "
                "'FORWARD_ORDER_CREATED', 'SYSTEM_DERIVED', '{}', :created_at)"
            ),
            [
                {
                    "id": uuid4(),
                    "portfolio_id": case["portfolio_id"],
                    "case_id": case["id"],
                    "created_at": case["created_at"],
                }
                for case in cases
            ],
        )


def downgrade() -> None:
    op.drop_index("ix_external_events_portfolio_created", table_name="external_execution_events")
    op.drop_table("external_execution_events")
    op.drop_index("ix_external_fills_case_created", table_name="external_execution_fills")
    op.drop_table("external_execution_fills")
    op.drop_index("ix_external_cases_portfolio", table_name="external_execution_cases")
    op.drop_table("external_execution_cases")
