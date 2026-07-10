from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

# ── Auth ──────────────────────────────────────────────────────────────────────


class UserRegister(BaseModel):
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserRead(BaseModel):
    id: int
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    token: str
    id: int
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── User Profile ──────────────────────────────────────────────────────────────


class UserProfileCreate(BaseModel):
    migraine_duration: str | None = None
    migraine_frequency: str | None = None
    migraine_subtype: str | None = None
    known_food_triggers: list[str] | None = None
    other_triggers: str | None = None
    home_city: str | None = None
    typical_bedtime: str | None = None
    typical_wake_time: str | None = None
    typical_stress_level: int | None = None
    job_type: str | None = None
    typical_hydration_oz: float | None = None
    typical_caffeine_level: str | None = None
    hormonal_status: str | None = None
    cycle_length_days: int | None = None
    migraines_cluster_period: str | None = None
    worst_hormonal_phase: str | None = None
    preventive_medications: list[str] | None = None
    supplements: list[str] | None = None
    acute_medications: list[str] | None = None
    onboarding_complete: bool = False


class UserProfileUpdate(BaseModel):
    migraine_duration: str | None = None
    migraine_frequency: str | None = None
    migraine_subtype: str | None = None
    known_food_triggers: list[str] | None = None
    other_triggers: str | None = None
    home_city: str | None = None
    typical_bedtime: str | None = None
    typical_wake_time: str | None = None
    typical_stress_level: int | None = None
    job_type: str | None = None
    typical_hydration_oz: float | None = None
    typical_caffeine_level: str | None = None
    hormonal_status: str | None = None
    cycle_length_days: int | None = None
    migraines_cluster_period: str | None = None
    worst_hormonal_phase: str | None = None
    preventive_medications: list[str] | None = None
    supplements: list[str] | None = None
    acute_medications: list[str] | None = None
    onboarding_complete: bool | None = None


class UserProfileRead(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    migraine_duration: str | None = None
    migraine_frequency: str | None = None
    migraine_subtype: str | None = None
    known_food_triggers: list[str] | None = None
    other_triggers: str | None = None
    home_city: str | None = None
    typical_bedtime: str | None = None
    typical_wake_time: str | None = None
    typical_stress_level: int | None = None
    job_type: str | None = None
    typical_hydration_oz: float | None = None
    typical_caffeine_level: str | None = None
    hormonal_status: str | None = None
    cycle_length_days: int | None = None
    migraines_cluster_period: str | None = None
    worst_hormonal_phase: str | None = None
    preventive_medications: list[str] | None = None
    supplements: list[str] | None = None
    acute_medications: list[str] | None = None
    onboarding_complete: bool = False

    model_config = {"from_attributes": True}


# ── Log Entry ─────────────────────────────────────────────────────────────────


class LogEntryCreate(BaseModel):
    entry_date: date
    migraine_occurred: bool = False
    pain_level: int | None = Field(default=None, ge=1, le=10)
    pain_location: str | None = None
    pain_quality: str | None = None
    duration_hours: float | None = None

    prodrome_symptoms: list[str] | None = None
    postdrome_symptoms: list[str] | None = None

    foods: list[str] | None = None
    hydration_oz: float | None = None
    caffeine_mg: float | None = None
    alcohol_drinks: float | None = None
    meals_skipped: list[str] | None = None
    fasting_hours: float | None = None

    supplements: list[str] | None = None
    medications: list[str] | None = None
    traditional_medicine: list[str] | None = None

    sleep_hours: float | None = None
    sleep_quality: int | None = Field(default=None, ge=1, le=10)
    bedtime: str | None = None
    wake_time: str | None = None

    stress_level: int | None = Field(default=None, ge=1, le=10)
    stress_source: str | None = None

    chemical_exposure: list[str] | None = None
    fragrance_exposure: bool | None = None

    exercise_type: str | None = None
    exercise_minutes: int | None = None
    screen_hours: float | None = None
    neck_tension: int | None = Field(default=None, ge=1, le=10)

    menstrual_cycle_day: int | None = None
    hormonal_notes: str | None = None

    bowel_quality: int | None = Field(default=None, ge=1, le=7)
    bloating: bool | None = None

    relief_methods: list[str] | None = None
    relief_effectiveness: int | None = Field(default=None, ge=1, le=10)

    notes: str | None = None

    # City sent from the browser; not stored on LogEntry directly —
    # used only to fetch location-accurate weather and resolve location_city.
    city: str | None = None

    # User scoping
    user_id: int | None = None


class LogEntryRead(BaseModel):
    id: int
    created_at: datetime
    entry_date: date
    migraine_occurred: bool
    pain_level: int | None = None
    pain_location: str | None = None
    pain_quality: str | None = None
    duration_hours: float | None = None
    prodrome_symptoms: list[str] | None = None
    postdrome_symptoms: list[str] | None = None
    foods: list[str] | None = None
    hydration_oz: float | None = None
    caffeine_mg: float | None = None
    alcohol_drinks: float | None = None
    meals_skipped: list[str] | None = None
    fasting_hours: float | None = None
    supplements: list[str] | None = None
    medications: list[str] | None = None
    traditional_medicine: list[str] | None = None
    sleep_hours: float | None = None
    sleep_quality: int | None = None
    bedtime: str | None = None
    wake_time: str | None = None
    stress_level: int | None = None
    stress_source: str | None = None
    chemical_exposure: list[str] | None = None
    fragrance_exposure: bool | None = None
    exercise_type: str | None = None
    exercise_minutes: int | None = None
    screen_hours: float | None = None
    neck_tension: int | None = None
    menstrual_cycle_day: int | None = None
    hormonal_notes: str | None = None
    bowel_quality: int | None = None
    bloating: bool | None = None
    relief_methods: list[str] | None = None
    relief_effectiveness: int | None = None
    location_city: str | None = None
    barometric_pressure_hpa: float | None = None
    pressure_delta_24h: float | None = None
    temperature_f: float | None = None
    humidity_pct: float | None = None
    aqi: int | None = None
    dominant_pollutant: str | None = None
    notes: str | None = None
    intake_followup_qa: list[dict] | None = None

    model_config = {"from_attributes": True}


class LogCreateResponse(BaseModel):
    log: LogEntryRead
    red_flag: bool
    red_flag_symptoms: list[str]
    moh_alert: bool
    triptan_days: int
    nsaid_days: int


class ToxicLoadResponse(BaseModel):
    today_score: float
    carryover_score: float
    rolling_score: float
    threshold: float
    fill_pct: float
    risk_level: str
    breakdown: dict


# ── Analyze ───────────────────────────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    thread_id: str = "default"
    intent: str = "log_entry"
    current_log_id: int | None = None
    message: str | None = None
    user_id: int | None = None


class AnalyzeResponse(BaseModel):
    messages: list[str]
    moh_alert: bool
    red_flag: bool
