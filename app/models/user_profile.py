from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Step 1 — Migraine History
    migraine_duration: str | None = None  # <1yr / 1-5yr / 5+yr
    migraine_frequency: str | None = None  # <1/month / 1-3/month / weekly / daily
    migraine_subtype: str | None = None  # optional free text

    # Step 2 — Known Triggers
    known_food_triggers: list[str] | None = Field(default=None, sa_column=Column(JSON))
    other_triggers: str | None = None

    # Step 3 — Baseline
    home_city: str | None = None  # e.g. "Austin, TX" — used for weather lookup
    typical_bedtime: str | None = None  # HH:MM
    typical_wake_time: str | None = None  # HH:MM
    typical_stress_level: int | None = None
    job_type: str | None = None  # desk / active / mixed
    typical_hydration_oz: float | None = None  # daily oz baseline
    typical_caffeine_level: str | None = None  # none / light / moderate / heavy

    # Step 4 — Hormonal Profile
    hormonal_status: str | None = None
    # premenopausal_regular | premenopausal_irregular | perimenopause |
    # postmenopausal | hormonal_contraception | pregnant_postpartum |
    # not_applicable | prefer_not_to_say
    cycle_length_days: int | None = None
    migraines_cluster_period: str | None = None  # yes / no / not_sure
    worst_hormonal_phase: str | None = None  # before / during / after / no_pattern

    # Step 5 — Medications
    preventive_medications: list[str] | None = Field(default=None, sa_column=Column(JSON))
    supplements: list[str] | None = Field(default=None, sa_column=Column(JSON))
    acute_medications: list[str] | None = Field(default=None, sa_column=Column(JSON))

    onboarding_complete: bool = Field(default=False)
