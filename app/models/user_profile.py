from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Step 1 — Migraine History
    migraine_duration: Optional[str] = None    # <1yr / 1-5yr / 5+yr
    migraine_frequency: Optional[str] = None   # <1/month / 1-3/month / weekly / daily
    migraine_subtype: Optional[str] = None     # optional free text

    # Step 2 — Known Triggers
    known_food_triggers: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    other_triggers: Optional[str] = None

    # Step 3 — Baseline
    home_city: Optional[str] = None            # e.g. "Austin, TX" — used for weather lookup
    typical_bedtime: Optional[str] = None      # HH:MM
    typical_wake_time: Optional[str] = None    # HH:MM
    typical_stress_level: Optional[int] = None
    job_type: Optional[str] = None             # desk / active / mixed
    typical_hydration_oz: Optional[float] = None   # daily oz baseline
    typical_caffeine_level: Optional[str] = None   # none / light / moderate / heavy

    # Step 4 — Hormonal Profile
    hormonal_status: Optional[str] = None
    # premenopausal_regular | premenopausal_irregular | perimenopause |
    # postmenopausal | hormonal_contraception | pregnant_postpartum |
    # not_applicable | prefer_not_to_say
    cycle_length_days: Optional[int] = None
    migraines_cluster_period: Optional[str] = None  # yes / no / not_sure
    worst_hormonal_phase: Optional[str] = None       # before / during / after / no_pattern

    # Step 5 — Medications
    preventive_medications: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    supplements: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    acute_medications: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    onboarding_complete: bool = Field(default=False)
