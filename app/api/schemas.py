from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str
    password: str


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
    migraine_duration: Optional[str] = None
    migraine_frequency: Optional[str] = None
    migraine_subtype: Optional[str] = None
    known_food_triggers: Optional[List[str]] = None
    other_triggers: Optional[str] = None
    typical_bedtime: Optional[str] = None
    typical_wake_time: Optional[str] = None
    typical_stress_level: Optional[int] = None
    job_type: Optional[str] = None
    typical_hydration_oz: Optional[float] = None
    typical_caffeine_level: Optional[str] = None
    hormonal_status: Optional[str] = None
    cycle_length_days: Optional[int] = None
    migraines_cluster_period: Optional[str] = None
    worst_hormonal_phase: Optional[str] = None
    preventive_medications: Optional[List[str]] = None
    supplements: Optional[List[str]] = None
    acute_medications: Optional[List[str]] = None
    onboarding_complete: bool = False


class UserProfileUpdate(BaseModel):
    migraine_duration: Optional[str] = None
    migraine_frequency: Optional[str] = None
    migraine_subtype: Optional[str] = None
    known_food_triggers: Optional[List[str]] = None
    other_triggers: Optional[str] = None
    typical_bedtime: Optional[str] = None
    typical_wake_time: Optional[str] = None
    typical_stress_level: Optional[int] = None
    job_type: Optional[str] = None
    typical_hydration_oz: Optional[float] = None
    typical_caffeine_level: Optional[str] = None
    hormonal_status: Optional[str] = None
    cycle_length_days: Optional[int] = None
    migraines_cluster_period: Optional[str] = None
    worst_hormonal_phase: Optional[str] = None
    preventive_medications: Optional[List[str]] = None
    supplements: Optional[List[str]] = None
    acute_medications: Optional[List[str]] = None
    onboarding_complete: Optional[bool] = None


class UserProfileRead(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    migraine_duration: Optional[str] = None
    migraine_frequency: Optional[str] = None
    migraine_subtype: Optional[str] = None
    known_food_triggers: Optional[List[str]] = None
    other_triggers: Optional[str] = None
    typical_bedtime: Optional[str] = None
    typical_wake_time: Optional[str] = None
    typical_stress_level: Optional[int] = None
    job_type: Optional[str] = None
    typical_hydration_oz: Optional[float] = None
    typical_caffeine_level: Optional[str] = None
    hormonal_status: Optional[str] = None
    cycle_length_days: Optional[int] = None
    migraines_cluster_period: Optional[str] = None
    worst_hormonal_phase: Optional[str] = None
    preventive_medications: Optional[List[str]] = None
    supplements: Optional[List[str]] = None
    acute_medications: Optional[List[str]] = None
    onboarding_complete: bool = False

    model_config = {"from_attributes": True}


# ── Log Entry ─────────────────────────────────────────────────────────────────

class LogEntryCreate(BaseModel):
    entry_date: date
    migraine_occurred: bool = False
    pain_level: Optional[int] = Field(default=None, ge=1, le=10)
    pain_location: Optional[str] = None
    pain_quality: Optional[str] = None
    duration_hours: Optional[float] = None

    prodrome_symptoms: Optional[List[str]] = None
    postdrome_symptoms: Optional[List[str]] = None

    foods: Optional[List[str]] = None
    hydration_oz: Optional[float] = None
    caffeine_mg: Optional[float] = None
    alcohol_drinks: Optional[float] = None
    meals_skipped: Optional[List[str]] = None
    fasting_hours: Optional[float] = None

    supplements: Optional[List[str]] = None
    medications: Optional[List[str]] = None
    traditional_medicine: Optional[List[str]] = None

    sleep_hours: Optional[float] = None
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=10)
    bedtime: Optional[str] = None
    wake_time: Optional[str] = None

    stress_level: Optional[int] = Field(default=None, ge=1, le=10)
    stress_source: Optional[str] = None

    chemical_exposure: Optional[List[str]] = None
    fragrance_exposure: Optional[bool] = None

    exercise_type: Optional[str] = None
    exercise_minutes: Optional[int] = None
    screen_hours: Optional[float] = None
    neck_tension: Optional[int] = Field(default=None, ge=1, le=10)

    menstrual_cycle_day: Optional[int] = None
    hormonal_notes: Optional[str] = None

    bowel_quality: Optional[int] = Field(default=None, ge=1, le=7)
    bloating: Optional[bool] = None

    relief_methods: Optional[List[str]] = None
    relief_effectiveness: Optional[int] = Field(default=None, ge=1, le=10)

    notes: Optional[str] = None

    # City sent from the browser; not stored on LogEntry directly —
    # used only to fetch location-accurate weather and resolve location_city.
    city: Optional[str] = None

    # User scoping
    user_id: Optional[int] = None


class LogEntryRead(BaseModel):
    id: int
    created_at: datetime
    entry_date: date
    migraine_occurred: bool
    pain_level: Optional[int] = None
    pain_location: Optional[str] = None
    pain_quality: Optional[str] = None
    duration_hours: Optional[float] = None
    prodrome_symptoms: Optional[List[str]] = None
    postdrome_symptoms: Optional[List[str]] = None
    foods: Optional[List[str]] = None
    hydration_oz: Optional[float] = None
    caffeine_mg: Optional[float] = None
    alcohol_drinks: Optional[float] = None
    meals_skipped: Optional[List[str]] = None
    fasting_hours: Optional[float] = None
    supplements: Optional[List[str]] = None
    medications: Optional[List[str]] = None
    traditional_medicine: Optional[List[str]] = None
    sleep_hours: Optional[float] = None
    sleep_quality: Optional[int] = None
    bedtime: Optional[str] = None
    wake_time: Optional[str] = None
    stress_level: Optional[int] = None
    stress_source: Optional[str] = None
    chemical_exposure: Optional[List[str]] = None
    fragrance_exposure: Optional[bool] = None
    exercise_type: Optional[str] = None
    exercise_minutes: Optional[int] = None
    screen_hours: Optional[float] = None
    neck_tension: Optional[int] = None
    menstrual_cycle_day: Optional[int] = None
    hormonal_notes: Optional[str] = None
    bowel_quality: Optional[int] = None
    bloating: Optional[bool] = None
    relief_methods: Optional[List[str]] = None
    relief_effectiveness: Optional[int] = None
    location_city: Optional[str] = None
    barometric_pressure_hpa: Optional[float] = None
    pressure_delta_24h: Optional[float] = None
    temperature_f: Optional[float] = None
    humidity_pct: Optional[float] = None
    aqi: Optional[int] = None
    dominant_pollutant: Optional[str] = None
    notes: Optional[str] = None
    intake_followup_qa: Optional[List[dict]] = None

    model_config = {"from_attributes": True}


class LogCreateResponse(BaseModel):
    log: LogEntryRead
    red_flag: bool
    red_flag_symptoms: List[str]
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
    current_log_id: Optional[int] = None
    message: Optional[str] = None
    user_id: Optional[int] = None


class AnalyzeResponse(BaseModel):
    messages: List[str]
    moh_alert: bool
    red_flag: bool
