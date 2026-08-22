"""unique log entry per (user_id, entry_date)

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-21

Removes duplicate log_entries rows (keeping the highest id per user+date),
then enforces the invariant at the database level with a unique constraint.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicates — keep the row with the largest id for each (user_id, entry_date)
    op.execute(
        """
        DELETE FROM log_entries
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM log_entries
            GROUP BY user_id, entry_date
        )
        """
    )

    op.create_unique_constraint(
        "uq_log_entries_user_date", "log_entries", ["user_id", "entry_date"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_log_entries_user_date", "log_entries", type_="unique")
