from datetime import date, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class LogEntry(SQLModel, table=True):
    __tablename__ = "log_entries"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)

    # ── Core event ──────────────────────────────────────────────────────────
    entry_date: date = Field(index=True)
    migraine_occurred: bool = Field(default=False)
    pain_level: int | None = Field(default=None, ge=1, le=10)
    pain_location: str | None = None  # temporal_left, frontal, occipital, etc.
    pain_quality: str | None = None  # throbbing, pressure, stabbing, burning
    duration_hours: float | None = None

    # ── Prodrome / postdrome ─────────────────────────────────────────────────
    prodrome_symptoms: list[str] | None = Field(default=None, sa_column=Column(JSON))
    postdrome_symptoms: list[str] | None = Field(default=None, sa_column=Column(JSON))

    # ── Diet ────────────────────────────────────────────────────────────────
    foods: list[str] | None = Field(default=None, sa_column=Column(JSON))
    hydration_oz: float | None = None
    caffeine_mg: float | None = None
    alcohol_drinks: float | None = None
    meals_skipped: list[str] | None = Field(default=None, sa_column=Column(JSON))
    fasting_hours: float | None = None  # longest gap without food that day

    # ── Supplements + medications ────────────────────────────────────────────
    supplements: list[str] | None = Field(default=None, sa_column=Column(JSON))
    medications: list[str] | None = Field(default=None, sa_column=Column(JSON))
    traditional_medicine: list[str] | None = Field(default=None, sa_column=Column(JSON))

    # ── Sleep ────────────────────────────────────────────────────────────────
    sleep_hours: float | None = None
    sleep_quality: int | None = Field(default=None, ge=1, le=10)
    bedtime: str | None = None  # HH:MM string
    wake_time: str | None = None

    # ── Stress + emotional ───────────────────────────────────────────────────
    stress_level: int | None = Field(default=None, ge=1, le=10)
    stress_source: str | None = None

    # ── Environmental ────────────────────────────────────────────────────────
    chemical_exposure: list[str] | None = Field(default=None, sa_column=Column(JSON))
    fragrance_exposure: bool | None = None

    # ── Physical ─────────────────────────────────────────────────────────────
    exercise_type: str | None = None
    exercise_minutes: int | None = None
    screen_hours: float | None = None
    neck_tension: int | None = Field(default=None, ge=1, le=10)

    # ── Hormonal ─────────────────────────────────────────────────────────────
    menstrual_cycle_day: int | None = None
    hormonal_notes: str | None = None

    # ── Gut ──────────────────────────────────────────────────────────────────
    bowel_quality: int | None = Field(default=None, ge=1, le=7)  # Bristol scale
    bloating: bool | None = None

    # ── Relief ───────────────────────────────────────────────────────────────
    relief_methods: list[str] | None = Field(default=None, sa_column=Column(JSON))
    relief_effectiveness: int | None = Field(default=None, ge=1, le=10)

    # ── Location (auto-resolved from coordinates or config city) ────────────
    location_city: str | None = None

    # ── Weather (auto-appended by weather service) ───────────────────────────
    barometric_pressure_hpa: float | None = None
    pressure_delta_24h: float | None = None
    temperature_f: float | None = None
    humidity_pct: float | None = None
    aqi: int | None = None
    dominant_pollutant: str | None = None

    # ── Free text + intake notes ─────────────────────────────────────────────
    notes: str | None = None
    intake_followup_qa: list[dict] | None = Field(default=None, sa_column=Column(JSON))

    # ── Novel / unusual exposures ─────────────────────────────────────────────
    # Anything consumed, applied, or encountered that is outside the user's normal
    # routine — not covered by the standard trigger list. Captured via Intake Agent
    # probing or user self-report. Used for unknown trigger correlation.
    novel_exposures: list[str] | None = Field(default=None, sa_column=Column(JSON))
