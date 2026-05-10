from datetime import datetime, date
from typing import Optional, List
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class LogEntry(SQLModel, table=True):
    __tablename__ = "log_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)

    # ── Core event ──────────────────────────────────────────────────────────
    entry_date: date = Field(index=True)
    migraine_occurred: bool = Field(default=False)
    pain_level: Optional[int] = Field(default=None, ge=1, le=10)
    pain_location: Optional[str] = None          # temporal_left, frontal, occipital, etc.
    pain_quality: Optional[str] = None           # throbbing, pressure, stabbing, burning
    duration_hours: Optional[float] = None

    # ── Prodrome / postdrome ─────────────────────────────────────────────────
    prodrome_symptoms: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    postdrome_symptoms: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    # ── Diet ────────────────────────────────────────────────────────────────
    foods: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    hydration_oz: Optional[float] = None
    caffeine_mg: Optional[float] = None
    alcohol_drinks: Optional[float] = None
    meals_skipped: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    fasting_hours: Optional[float] = None    # longest gap without food that day

    # ── Supplements + medications ────────────────────────────────────────────
    supplements: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    medications: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    traditional_medicine: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    # ── Sleep ────────────────────────────────────────────────────────────────
    sleep_hours: Optional[float] = None
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=10)
    bedtime: Optional[str] = None                # HH:MM string
    wake_time: Optional[str] = None

    # ── Stress + emotional ───────────────────────────────────────────────────
    stress_level: Optional[int] = Field(default=None, ge=1, le=10)
    stress_source: Optional[str] = None

    # ── Environmental ────────────────────────────────────────────────────────
    chemical_exposure: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    fragrance_exposure: Optional[bool] = None

    # ── Physical ─────────────────────────────────────────────────────────────
    exercise_type: Optional[str] = None
    exercise_minutes: Optional[int] = None
    screen_hours: Optional[float] = None
    neck_tension: Optional[int] = Field(default=None, ge=1, le=10)

    # ── Hormonal ─────────────────────────────────────────────────────────────
    menstrual_cycle_day: Optional[int] = None
    hormonal_notes: Optional[str] = None

    # ── Gut ──────────────────────────────────────────────────────────────────
    bowel_quality: Optional[int] = Field(default=None, ge=1, le=7)   # Bristol scale
    bloating: Optional[bool] = None

    # ── Relief ───────────────────────────────────────────────────────────────
    relief_methods: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    relief_effectiveness: Optional[int] = Field(default=None, ge=1, le=10)

    # ── Location (auto-resolved from coordinates or config city) ────────────
    location_city: Optional[str] = None

    # ── Weather (auto-appended by weather service) ───────────────────────────
    barometric_pressure_hpa: Optional[float] = None
    pressure_delta_24h: Optional[float] = None
    temperature_f: Optional[float] = None
    humidity_pct: Optional[float] = None
    aqi: Optional[int] = None
    dominant_pollutant: Optional[str] = None

    # ── Free text + intake notes ─────────────────────────────────────────────
    notes: Optional[str] = None
    intake_followup_qa: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON))
