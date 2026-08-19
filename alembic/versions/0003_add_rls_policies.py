"""enable row-level security on all user-scoped tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-18

Policies use current_setting('app.current_user_id') which FastAPI sets via
SET LOCAL at the start of every authenticated request (see app/api/deps.py).

IMPORTANT — superuser bypass:
PostgreSQL superusers (e.g. the 'postgres' role used in DATABASE_URL) bypass
RLS by default.  For RLS to enforce in production, the FastAPI app should
connect as a non-superuser role.  Create one in Supabase:

    Dashboard → SQL Editor:
        CREATE ROLE app_user LOGIN PASSWORD '<strong-password>';
        GRANT USAGE ON SCHEMA public TO app_user;
        GRANT SELECT, INSERT, UPDATE, DELETE
            ON ALL TABLES IN SCHEMA public TO app_user;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

Then update DATABASE_URL in Render to use app_user credentials.
Alembic migrations should continue to run as the superuser (postgres).
"""

from collections.abc import Sequence

from alembic import op  # type: ignore[attr-defined]

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables with strict user isolation (user_id is always the logged-in user)
_STRICT_TABLES = ["log_entries", "user_profiles", "refresh_tokens"]

# knowledge_chunks: user_id IS NULL means a global/shared research chunk —
# readable by all authenticated users, but users can only write their own chunks.
_KNOWLEDGE_TABLE = "knowledge_chunks"


def upgrade() -> None:
    # Enable RLS on all user-scoped tables
    for table in [*_STRICT_TABLES, _KNOWLEDGE_TABLE]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    # Strict isolation: you only see and write your own rows
    for table in _STRICT_TABLES:
        op.execute(f"""
            CREATE POLICY user_isolation ON {table}
                FOR ALL
                USING (
                    user_id = current_setting('app.current_user_id', true)::int
                )
                WITH CHECK (
                    user_id = current_setting('app.current_user_id', true)::int
                )
        """)

    # knowledge_chunks: global chunks (user_id IS NULL) are readable by everyone;
    # user chunks are private; inserts/updates must always belong to current user.
    op.execute(f"""
        CREATE POLICY user_isolation ON {_KNOWLEDGE_TABLE}
            FOR ALL
            USING (
                user_id IS NULL
                OR user_id = current_setting('app.current_user_id', true)::int
            )
            WITH CHECK (
                user_id = current_setting('app.current_user_id', true)::int
            )
    """)


def downgrade() -> None:
    for table in [*_STRICT_TABLES, _KNOWLEDGE_TABLE]:
        op.execute(f"DROP POLICY IF EXISTS user_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
