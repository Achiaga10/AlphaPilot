"""Allow append-only News classification attempt history.

Revision ID: e8a1c5d4f920
Revises: d7f4a2c9e810
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e8a1c5d4f920"
down_revision: str | Sequence[str] | None = "d7f4a2c9e810"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_news_classification_attempt_identity",
        "news_classifications",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_news_classification_attempt_identity",
        "news_classifications",
        [
            "article_id",
            "classification_provider",
            "classification_model",
            "classification_version",
        ],
    )
