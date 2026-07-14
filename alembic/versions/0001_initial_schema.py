"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-11

Creates all four tables from the current SQLModel definitions:
  users, user_profiles, log_entries, knowledge_chunks

knowledge_chunks.user_id is nullable from the start (NULL = system/shared chunk)
so the inline ALTER TABLE workaround in database.py is no longer needed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op  # type: ignore[attr-defined]

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    # pgvector must exist before the vector column type can be created
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("migraine_duration", sa.String(), nullable=True),
        sa.Column("migraine_frequency", sa.String(), nullable=True),
        sa.Column("migraine_subtype", sa.String(), nullable=True),
        sa.Column("known_food_triggers", sa.JSON(), nullable=True),
        sa.Column("other_triggers", sa.String(), nullable=True),
        sa.Column("home_city", sa.String(), nullable=True),
        sa.Column("typical_bedtime", sa.String(), nullable=True),
        sa.Column("typical_wake_time", sa.String(), nullable=True),
        sa.Column("typical_stress_level", sa.Integer(), nullable=True),
        sa.Column("job_type", sa.String(), nullable=True),
        sa.Column("typical_hydration_oz", sa.Float(), nullable=True),
        sa.Column("typical_caffeine_level", sa.String(), nullable=True),
        sa.Column("hormonal_status", sa.String(), nullable=True),
        sa.Column("cycle_length_days", sa.Integer(), nullable=True),
        sa.Column("migraines_cluster_period", sa.String(), nullable=True),
        sa.Column("worst_hormonal_phase", sa.String(), nullable=True),
        sa.Column("preventive_medications", sa.JSON(), nullable=True),
        sa.Column("supplements", sa.JSON(), nullable=True),
        sa.Column("acute_medications", sa.JSON(), nullable=True),
        sa.Column("onboarding_complete", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"])

    op.create_table(
        "log_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("migraine_occurred", sa.Boolean(), nullable=False),
        sa.Column("pain_level", sa.Integer(), nullable=True),
        sa.Column("pain_location", sa.String(), nullable=True),
        sa.Column("pain_quality", sa.String(), nullable=True),
        sa.Column("duration_hours", sa.Float(), nullable=True),
        sa.Column("prodrome_symptoms", sa.JSON(), nullable=True),
        sa.Column("postdrome_symptoms", sa.JSON(), nullable=True),
        sa.Column("foods", sa.JSON(), nullable=True),
        sa.Column("hydration_oz", sa.Float(), nullable=True),
        sa.Column("caffeine_mg", sa.Float(), nullable=True),
        sa.Column("alcohol_drinks", sa.Float(), nullable=True),
        sa.Column("meals_skipped", sa.JSON(), nullable=True),
        sa.Column("fasting_hours", sa.Float(), nullable=True),
        sa.Column("supplements", sa.JSON(), nullable=True),
        sa.Column("medications", sa.JSON(), nullable=True),
        sa.Column("traditional_medicine", sa.JSON(), nullable=True),
        sa.Column("sleep_hours", sa.Float(), nullable=True),
        sa.Column("sleep_quality", sa.Integer(), nullable=True),
        sa.Column("bedtime", sa.String(), nullable=True),
        sa.Column("wake_time", sa.String(), nullable=True),
        sa.Column("stress_level", sa.Integer(), nullable=True),
        sa.Column("stress_source", sa.String(), nullable=True),
        sa.Column("chemical_exposure", sa.JSON(), nullable=True),
        sa.Column("fragrance_exposure", sa.Boolean(), nullable=True),
        sa.Column("exercise_type", sa.String(), nullable=True),
        sa.Column("exercise_minutes", sa.Integer(), nullable=True),
        sa.Column("screen_hours", sa.Float(), nullable=True),
        sa.Column("neck_tension", sa.Integer(), nullable=True),
        sa.Column("menstrual_cycle_day", sa.Integer(), nullable=True),
        sa.Column("hormonal_notes", sa.String(), nullable=True),
        sa.Column("bowel_quality", sa.Integer(), nullable=True),
        sa.Column("bloating", sa.Boolean(), nullable=True),
        sa.Column("relief_methods", sa.JSON(), nullable=True),
        sa.Column("relief_effectiveness", sa.Integer(), nullable=True),
        sa.Column("location_city", sa.String(), nullable=True),
        sa.Column("barometric_pressure_hpa", sa.Float(), nullable=True),
        sa.Column("pressure_delta_24h", sa.Float(), nullable=True),
        sa.Column("temperature_f", sa.Float(), nullable=True),
        sa.Column("humidity_pct", sa.Float(), nullable=True),
        sa.Column("aqi", sa.Integer(), nullable=True),
        sa.Column("dominant_pollutant", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("intake_followup_qa", sa.JSON(), nullable=True),
        sa.Column("novel_exposures", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_log_entries_user_id", "log_entries", ["user_id"])
    op.create_index("ix_log_entries_entry_date", "log_entries", ["entry_date"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        # nullable: NULL = system/shared chunk (guideline seeder); non-null = user-uploaded doc
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("doc_title", sa.String(), nullable=False),
        sa.Column("doc_id", sa.String(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_chunks_user_id", "knowledge_chunks", ["user_id"])
    op.create_index("ix_knowledge_chunks_source_type", "knowledge_chunks", ["source_type"])
    op.create_index("ix_knowledge_chunks_doc_id", "knowledge_chunks", ["doc_id"])


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_log_entries_entry_date", table_name="log_entries")
    op.drop_index("ix_log_entries_user_id", table_name="log_entries")
    op.drop_table("log_entries")
    op.drop_index("ix_user_profiles_user_id", table_name="user_profiles")
    op.drop_table("user_profiles")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
