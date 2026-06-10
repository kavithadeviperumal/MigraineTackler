import streamlit as st
import httpx
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from components.time_picker import time_picker as _time_picker_widget

API_BASE = st.secrets.get("API_BASE", "http://localhost:8000")

_MIGRAINE_MEDICATIONS = [
    "acetaminophen", "acetaminophen + aspirin + caffeine", "almotriptan",
    "amitriptyline", "aspirin", "atenolol", "candesartan",
    "dihydroergotamine", "divalproex", "eletriptan", "eptinezumab",
    "erenumab", "ergotamine", "fremanezumab", "frovatriptan",
    "gabapentin", "galcanezumab", "ibuprofen", "lasmiditan",
    "lisinopril", "metoclopramide", "metoprolol", "naproxen",
    "naratriptan", "nortriptyline", "onabotulinumtoxinA", "ondansetron",
    "prochlorperazine", "promethazine", "propranolol", "rimegepant",
    "rizatriptan", "sumatriptan", "timolol", "topiramate",
    "ubrogepant", "valproate", "venlafaxine", "verapamil",
    "zavegepant", "zolmitriptan",
]

_ALL_FOODS = [
    "aged_cheese", "alcohol", "artificial_sweeteners", "avocado",
    "bananas", "beans_legumes", "beer", "caffeine", "chocolate",
    "citrus", "fermented_foods", "garlic", "gluten", "MSG",
    "nuts", "onions", "pickled_foods", "pizza", "processed_meat",
    "red_wine", "smoked_fish", "tyramine_rich_foods", "yeast_extract",
]

_SOS_QUICK_MEDS = [
    "None yet", "acetaminophen", "ibuprofen", "rimegepant",
    "rizatriptan", "sumatriptan", "ubrogepant", "zolmitriptan", "other",
]

_HORMONAL_STATUSES = {
    "premenopausal_regular": "Pre-menopausal — regular cycle",
    "premenopausal_irregular": "Pre-menopausal — irregular cycle",
    "perimenopause": "Perimenopause",
    "postmenopausal": "Post-menopausal",
    "hormonal_contraception": "On hormonal contraception (pill / patch / IUD / ring)",
    "pregnant_postpartum": "Pregnant or postpartum",
    "not_applicable": "Not applicable",
    "prefer_not_to_say": "Prefer not to say",
}

st.set_page_config(page_title="MigraineTackler", page_icon="🧠", layout="wide")

st.markdown("""
<style>
[data-testid="stStatusWidget"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────

for _k, _v in {
    "user_id": None,
    "username": None,
    "token": None,
    "intake_messages": [],
    "research_messages": [],
    "sos_pending": False,
    "sos_data": {},
    "reset_confirm": False,
    "geo_city": "",
    "onboarding_step": 1,
    "onboarding_data": {},
    "onboarding_complete": False,
    "lifestyle_audit_output": None,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Persistent auth via query params ─────────────────────────────────────────

if st.session_state.token is None and "token" in st.query_params:
    st.session_state.token    = st.query_params["token"]
    st.session_state.user_id  = st.query_params.get("uid")
    st.session_state.username = st.query_params.get("uname")

# ── API helpers ───────────────────────────────────────────────────────────────

def _auth_headers() -> dict:
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_post(path: str, body: dict, timeout: int = 60) -> dict | None:
    try:
        r = httpx.post(f"{API_BASE}{path}", json=body, headers=_auth_headers(), timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        st.error(f"Connection error: {e}")
    return None


def api_patch(path: str, body: dict) -> dict | None:
    try:
        r = httpx.patch(f"{API_BASE}{path}", json=body, headers=_auth_headers(), timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        st.error(f"Connection error: {e}")
    return None


def api_get(path: str, params: dict | None = None) -> dict | list | None:
    try:
        r = httpx.get(f"{API_BASE}{path}", params=params, headers=_auth_headers(), timeout=10, follow_redirects=True)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def call_analyze(intent: str, log_id: int | None = None, message: str | None = None) -> dict | None:
    body = {"intent": intent}
    if log_id is not None:
        body["current_log_id"] = log_id
    if message:
        body["message"] = message
    return api_post("/analyze", body, timeout=120)


# ── Shared utilities ──────────────────────────────────────────────────────────

def migraine_free_streak(logs: list) -> int:
    streak = 0
    for log in sorted(logs, key=lambda l: l["entry_date"], reverse=True):
        if log.get("migraine_occurred"):
            break
        streak += 1
    return streak


def _render_progress(slot, label: str, value: float) -> None:
    with slot.container():
        st.markdown("<br>", unsafe_allow_html=True)
        _, col, _ = st.columns([1, 3, 1])
        with col:
            st.markdown(
                f"<div style='text-align:center;padding:6px 0;color:#555'>{label}</div>",
                unsafe_allow_html=True,
            )
            st.progress(value)
        st.markdown("<br>", unsafe_allow_html=True)


@contextmanager
def _progress(label: str, value: float = 0.6):
    slot = st.empty()
    _render_progress(slot, label, value)
    try:
        yield slot
    finally:
        slot.empty()


def _calc_sleep_hours(bedtime, wake_time) -> float | None:
    try:
        b = datetime.combine(date.today(), bedtime)
        w = datetime.combine(date.today(), wake_time)
        delta = w - b
        if delta.total_seconds() < 0:
            delta += timedelta(hours=24)
        return round(delta.total_seconds() / 3600, 1)
    except (TypeError, AttributeError):
        return None


def _render_location_picker() -> str | None:
    with st.expander("📍 Location (for accurate weather)", expanded=False):
        city = st.text_input(
            "City",
            value=st.session_state.geo_city,
            placeholder="e.g. Austin, TX  or  London, UK",
            key="city_input",
        )
        st.session_state.geo_city = city
        if city:
            st.caption(f"Weather will be fetched for **{city}**.")
        else:
            st.caption("Leave blank to use the default city from app config.")
    return st.session_state.geo_city or None


def _parse_bedtime(profile: dict, key: str, default: time) -> time:
    raw = profile.get(key)
    if raw:
        try:
            return time.fromisoformat(raw)
        except ValueError:
            pass
    return default


def _hormonal_shows_cycle(hormonal_status: str | None) -> bool:
    return hormonal_status in (
        "premenopausal_regular", "premenopausal_irregular", "perimenopause"
    )


def _hormonal_shows_section(hormonal_status: str | None) -> bool:
    return hormonal_status not in (
        "postmenopausal", "not_applicable", "prefer_not_to_say", None
    )


# ── Auth page ─────────────────────────────────────────────────────────────────

def _render_auth_page():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.title("🧠 MigraineTackler")
        st.caption("Your personal migraine tracking and analysis companion.")
        st.divider()
        tab_login, tab_register = st.tabs(["Log in", "Create account"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
            if submitted:
                with st.spinner("Logging in..."):
                    result = api_post("/auth/login", {"username": username, "password": password})
                if result:
                    st.session_state.user_id = result["id"]
                    st.session_state.username = result["username"]
                    st.session_state.token = result["token"]
                    st.query_params["token"] = result["token"]
                    st.query_params["uid"]   = str(result["id"])
                    st.query_params["uname"] = result["username"]
                    st.rerun()

        with tab_register:
            with st.form("register_form"):
                new_username = st.text_input("Choose a username")
                new_password = st.text_input("Choose a password", type="password")
                confirm = st.text_input("Confirm password", type="password")
                submitted_reg = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if submitted_reg:
                if new_password != confirm:
                    st.error("Passwords don't match.")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    with st.spinner("Creating your account..."):
                        result = api_post("/auth/register", {"username": new_username, "password": new_password})
                    if result:
                        st.session_state.user_id = result["id"]
                        st.session_state.username = result["username"]
                        st.session_state.token = result["token"]
                        st.query_params["token"] = result["token"]
                        st.query_params["uid"]   = str(result["id"])
                        st.query_params["uname"] = result["username"]
                        st.success("Account created! Setting up your profile...")
                        st.rerun()


# ── Onboarding wizard ─────────────────────────────────────────────────────────

_ONBOARDING_STEPS = [
    "Migraine History",
    "Known Triggers",
    "Your Baseline",
    "Hormonal Profile",
    "Medications",
]


def _onboarding_progress():
    step = st.session_state.onboarding_step
    total = len(_ONBOARDING_STEPS)
    if step <= total:
        st.progress(step / total)
        st.caption(f"Step {step} of {total} — {_ONBOARDING_STEPS[step - 1]}")
    st.divider()


def _render_onboarding(existing_profile: dict):
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.title("🧠 Welcome to MigraineTackler")
        st.caption(f"Hi **{st.session_state.username}** — let's set up your profile so the app can personalise everything for you.")
        st.divider()

        step = st.session_state.onboarding_step
        data = st.session_state.onboarding_data

        # ── Step 1: Migraine History ──────────────────────────────────────────
        if step == 1:
            _onboarding_progress()
            st.subheader("How long have you had migraines?")
            duration = st.radio(
                "Duration",
                ["Less than 1 year", "1–5 years", "More than 5 years"],
                label_visibility="collapsed",
                index=["Less than 1 year", "1–5 years", "More than 5 years"].index(
                    data.get("_duration_label", "1–5 years")
                ),
            )
            st.subheader("How often do they occur?")
            frequency = st.radio(
                "Frequency",
                ["Less than once a month", "1–3 times a month", "About once a week", "Multiple times a week or daily"],
                label_visibility="collapsed",
                index=["Less than once a month", "1–3 times a month", "About once a week", "Multiple times a week or daily"].index(
                    data.get("_freq_label", "1–3 times a month")
                ),
            )
            st.subheader("Diagnosed subtype *(optional)*")
            subtype = st.text_input(
                "Subtype",
                value=data.get("migraine_subtype", ""),
                placeholder="e.g. chronic migraine, vestibular, menstrual...",
                label_visibility="collapsed",
            )
            if st.button("Next →", type="primary", use_container_width=True):
                _dur_map = {
                    "Less than 1 year": "<1yr",
                    "1–5 years": "1-5yr",
                    "More than 5 years": "5+yr",
                }
                _freq_map = {
                    "Less than once a month": "<1/month",
                    "1–3 times a month": "1-3/month",
                    "About once a week": "weekly",
                    "Multiple times a week or daily": "daily",
                }
                data["migraine_duration"] = _dur_map[duration]
                data["migraine_frequency"] = _freq_map[frequency]
                data["migraine_subtype"] = subtype or None
                data["_duration_label"] = duration
                data["_freq_label"] = frequency
                st.session_state.onboarding_step = 2
                st.rerun()

        # ── Step 2: Known Triggers ────────────────────────────────────────────
        elif step == 2:
            _onboarding_progress()
            st.subheader("Which foods do you suspect trigger your migraines?")
            st.caption("Select all that apply — or choose 'None identified yet' if you're not sure.")
            trigger_options = ["None identified yet"] + _ref_foods
            default_triggers = data.get("_food_trigger_labels", [])
            selected = st.multiselect(
                "Food triggers",
                trigger_options,
                default=default_triggers,
                label_visibility="collapsed",
            )
            st.subheader("Any other triggers you've noticed? *(optional)*")
            other = st.text_input(
                "Other triggers",
                value=data.get("other_triggers", ""),
                placeholder="e.g. bright lights, strong smells, weather changes...",
                label_visibility="collapsed",
            )
            c1, c2 = st.columns(2)
            if c1.button("← Back", use_container_width=True):
                st.session_state.onboarding_step = 1
                st.rerun()
            if c2.button("Next →", type="primary", use_container_width=True):
                food_triggers = [f for f in selected if f != "None identified yet"]
                data["known_food_triggers"] = food_triggers or None
                data["other_triggers"] = other or None
                data["_food_trigger_labels"] = selected
                st.session_state.onboarding_step = 3
                st.rerun()

        # ── Step 3: Baseline ──────────────────────────────────────────────────
        elif step == 3:
            _onboarding_progress()
            st.subheader("Where do you live?")
            st.caption("Used to pull automatic weather data — barometric pressure changes are a major migraine trigger.")
            home_city_ob = st.text_input(
                "Home city",
                value=data.get("home_city", ""),
                placeholder="e.g. Austin, TX  or  London, UK",
                label_visibility="collapsed",
                key="ob_home_city",
            )
            st.divider()
            st.subheader("What are your typical sleep times?")
            c1, c2 = st.columns(2)
            with c1:
                bedtime = _time_picker_widget(
                    "Typical bedtime",
                    value=_parse_bedtime(data, "typical_bedtime", time(22, 30)),
                    key="ob_bedtime",
                )
            with c2:
                wake_time = _time_picker_widget(
                    "Typical wake time",
                    value=_parse_bedtime(data, "typical_wake_time", time(6, 30)),
                    key="ob_wake",
                )
            st.subheader("Typical stress level")
            stress = st.slider(
                "Stress",
                1, 10,
                value=data.get("typical_stress_level", 5),
                label_visibility="collapsed",
            )
            st.subheader("What kind of job do you have?")
            job = st.radio(
                "Job type",
                ["Desk / sedentary", "Mostly active / on feet", "Mixed"],
                index=["Desk / sedentary", "Mostly active / on feet", "Mixed"].index(
                    data.get("_job_label", "Desk / sedentary")
                ),
                label_visibility="collapsed",
            )
            st.subheader("Typical daily hydration")
            hydration_oz_ob = st.slider(
                "Daily water intake (oz)", 16, 120,
                value=int(data.get("typical_hydration_oz") or 64), step=8,
                help="8 oz = 1 cup  ·  64 oz = 8 cups  ·  Most adults need 64–80 oz",
            )

            st.subheader("Typical caffeine intake")
            _caff_ob_opts = [
                "None",
                "Light  (1–2 cups / <200 mg)",
                "Moderate  (2–3 cups / 200–400 mg)",
                "Heavy  (3+ cups / >400 mg)",
            ]
            _caff_ob_map = {
                "None": "none",
                "Light  (1–2 cups / <200 mg)": "light",
                "Moderate  (2–3 cups / 200–400 mg)": "moderate",
                "Heavy  (3+ cups / >400 mg)": "heavy",
            }
            _caff_ob_rev = {v: k for k, v in _caff_ob_map.items()}
            caff_ob_label = st.radio(
                "Caffeine",
                _caff_ob_opts,
                index=_caff_ob_opts.index(
                    _caff_ob_rev.get(data.get("typical_caffeine_level", "none"), "None")
                ),
                label_visibility="collapsed",
            )

            c1, c2 = st.columns(2)
            if c1.button("← Back", use_container_width=True):
                st.session_state.onboarding_step = 2
                st.rerun()
            if c2.button("Next →", type="primary", use_container_width=True):
                _job_map = {
                    "Desk / sedentary": "desk",
                    "Mostly active / on feet": "active",
                    "Mixed": "mixed",
                }
                data["home_city"] = home_city_ob or None
                data["typical_bedtime"] = bedtime.strftime("%H:%M") if bedtime else None
                data["typical_wake_time"] = wake_time.strftime("%H:%M") if wake_time else None
                data["typical_stress_level"] = stress
                data["job_type"] = _job_map[job]
                data["_job_label"] = job
                data["typical_hydration_oz"] = float(hydration_oz_ob)
                data["typical_caffeine_level"] = _caff_ob_map[caff_ob_label]
                st.session_state.onboarding_step = 4
                st.rerun()

        # ── Step 4: Hormonal Profile ──────────────────────────────────────────
        elif step == 4:
            _onboarding_progress()
            st.subheader("Which best describes your hormonal status?")
            status_labels = list(_HORMONAL_STATUSES.values())
            status_keys = list(_HORMONAL_STATUSES.keys())
            current_key = data.get("hormonal_status", "prefer_not_to_say")
            current_label = _HORMONAL_STATUSES.get(current_key, status_labels[-1])
            selected_status_label = st.radio(
                "Hormonal status",
                status_labels,
                index=status_labels.index(current_label),
                label_visibility="collapsed",
            )
            selected_status_key = status_keys[status_labels.index(selected_status_label)]

            cycle_length = None
            cluster = None
            worst_phase = None

            if _hormonal_shows_cycle(selected_status_key):
                st.subheader("Cycle details *(optional)*")
                c1, c2 = st.columns(2)
                cycle_length = c1.number_input(
                    "Typical cycle length (days)",
                    min_value=0, max_value=60,
                    value=data.get("cycle_length_days") or 28,
                    step=1,
                )
                cluster_options = ["Yes", "No", "Not sure"]
                cluster_val = data.get("migraines_cluster_period", "not_sure")
                cluster_map_rev = {"yes": "Yes", "no": "No", "not_sure": "Not sure"}
                cluster = c2.radio(
                    "Do migraines cluster around your period?",
                    cluster_options,
                    index=cluster_options.index(cluster_map_rev.get(cluster_val, "Not sure")),
                )
                if cluster == "Yes":
                    phase_options = ["Before (days 25–28)", "During (days 1–3)", "After (days 4–6)", "No clear pattern"]
                    phase_val = data.get("worst_hormonal_phase", "no_pattern")
                    phase_map_rev = {
                        "before": "Before (days 25–28)",
                        "during": "During (days 1–3)",
                        "after": "After (days 4–6)",
                        "no_pattern": "No clear pattern",
                    }
                    worst_phase_label = st.radio(
                        "Which phase is worst for you?",
                        phase_options,
                        index=phase_options.index(phase_map_rev.get(phase_val, "No clear pattern")),
                    )
                    phase_map = {
                        "Before (days 25–28)": "before",
                        "During (days 1–3)": "during",
                        "After (days 4–6)": "after",
                        "No clear pattern": "no_pattern",
                    }
                    worst_phase = phase_map[worst_phase_label]

            elif selected_status_key == "hormonal_contraception":
                st.info("We'll ask about hormonal symptoms on your daily log instead of cycle day.")

            c1, c2 = st.columns(2)
            if c1.button("← Back", use_container_width=True):
                st.session_state.onboarding_step = 3
                st.rerun()
            if c2.button("Next →", type="primary", use_container_width=True):
                cluster_map = {"Yes": "yes", "No": "no", "Not sure": "not_sure"}
                data["hormonal_status"] = selected_status_key
                data["cycle_length_days"] = int(cycle_length) if cycle_length else None
                data["migraines_cluster_period"] = cluster_map.get(cluster) if cluster else None
                data["worst_hormonal_phase"] = worst_phase
                st.session_state.onboarding_step = 5
                st.rerun()

        # ── Step 5: Medications ───────────────────────────────────────────────
        elif step == 5:
            _onboarding_progress()
            st.subheader("Preventive medications *(if any)*")
            prev_meds = st.multiselect(
                "Preventive",
                _MIGRAINE_MEDICATIONS,
                default=data.get("preventive_medications") or [],
                label_visibility="collapsed",
            )
            st.subheader("Supplements *(if any)*")
            supps = st.multiselect(
                "Supplements",
                ["butterbur", "CoQ10", "feverfew", "magnesium", "melatonin", "riboflavin_B2"],
                default=data.get("supplements") or [],
                label_visibility="collapsed",
            )
            st.subheader("Acute medications you keep on hand")
            acute = st.multiselect(
                "Acute",
                _MIGRAINE_MEDICATIONS,
                default=data.get("acute_medications") or [],
                label_visibility="collapsed",
            )
            st.caption("Don't see something? You can add it later in Settings.")
            c1, c2 = st.columns(2)
            if c1.button("← Back", use_container_width=True):
                st.session_state.onboarding_step = 4
                st.rerun()
            if c2.button("Complete setup →", type="primary", use_container_width=True):
                data["preventive_medications"] = prev_meds or None
                data["supplements"] = supps or None
                data["acute_medications"] = acute or None
                data["onboarding_complete"] = True
                # Remove internal UI labels before sending
                payload = {k: v for k, v in data.items() if not k.startswith("_")}
                existing = api_get("/profile/me")
                if existing:
                    result = api_patch("/profile/me", payload)
                else:
                    result = api_post("/profile/me", payload)
                if result:
                    st.session_state.onboarding_complete = True
                    st.session_state.cached_profile = result
                    st.session_state.onboarding_step = 6
                    st.rerun()

        # ── Step 6: Complete ──────────────────────────────────────────────────
        elif step == 6:
            st.success("### You're all set! 🎉")
            st.write(
                "Your profile has been saved. From now on, your daily log will be "
                "pre-filled with your baseline and personalised to your hormonal profile."
            )
            if st.button("Start logging →", type="primary", use_container_width=True):
                st.session_state.onboarding_step = 1
                st.session_state.onboarding_data = {}
                st.rerun()


# ── Log submission ────────────────────────────────────────────────────────────

def _submit_log(payload: dict):
    slot = st.empty()
    _render_progress(slot, "💾 Saving log...", 0.35)
    result = api_post("/logs/", payload)

    if result:
        st.session_state.pop("ref_foods", None)  # new food may have been logged; refresh on next rerun
        log_id = result["log"]["id"]
        st.session_state.intake_messages = []

        if result.get("red_flag"):
            st.error(f"⚠️ Red flag symptoms: {', '.join(result.get('red_flag_symptoms', []))}. Please see a doctor.")
        if result.get("moh_alert"):
            st.warning(
                f"⚠️ Medication overuse alert — {result['triptan_days']} triptan days "
                f"and {result['nsaid_days']} NSAID days in the last 30 days."
            )

        _render_progress(slot, "🧠 Intake agent reviewing your log...", 0.75)
        analysis = call_analyze("log_entry", log_id=log_id)
        slot.empty()

        if analysis and analysis.get("messages"):
            for msg in analysis["messages"]:
                st.session_state.intake_messages.append({"role": "assistant", "content": msg})
            st.rerun()
    else:
        slot.empty()


# ── Auth gate ─────────────────────────────────────────────────────────────────

if not st.session_state.user_id:
    _render_auth_page()
    st.stop()

# ── Onboarding gate ───────────────────────────────────────────────────────────

if "cached_profile" not in st.session_state:
    st.session_state.cached_profile = api_get("/profile/me")
_profile = st.session_state.cached_profile or {}

if "ref_foods" not in st.session_state:
    _rfd = api_get("/profile/me/reference-foods")
    st.session_state.ref_foods = _rfd.get("foods", []) if _rfd else []
_ref_foods: list[str] = st.session_state.ref_foods or _ALL_FOODS

if _profile.get("onboarding_complete"):
    st.session_state.onboarding_complete = True

if not st.session_state.onboarding_complete:
    if _profile:
        st.session_state.onboarding_data = {
            k: _profile.get(k) for k in [
                "migraine_duration", "migraine_frequency", "migraine_subtype",
                "known_food_triggers", "other_triggers",
                "home_city",
                "typical_bedtime", "typical_wake_time", "typical_stress_level", "job_type",
                "typical_hydration_oz", "typical_caffeine_level",
                "hormonal_status", "cycle_length_days", "migraines_cluster_period", "worst_hormonal_phase",
                "preventive_medications", "supplements", "acute_medications",
            ]
        }
    _render_onboarding(_profile)
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🧠 MigraineTackler")
    st.caption(f"Logged in as **{st.session_state.username}**")
    if st.button("Log out", use_container_width=True):
        st.query_params.clear()
        for k in ["user_id", "username", "token", "intake_messages", "research_messages",
                  "sos_pending", "sos_data", "reset_confirm", "geo_city", "onboarding_step", "onboarding_data"]:
            st.session_state[k] = [] if k.endswith("messages") else ({} if k in ("sos_data", "onboarding_data") else (1 if k == "onboarding_step" else (False if k in ("sos_pending", "reset_confirm") else (None if k in ("user_id", "username", "token") else ""))))
        st.session_state.onboarding_complete = False
        st.session_state.pop("ref_foods", None)
        st.session_state.pop("cached_profile", None)
        st.rerun()

    if st.session_state.sos_pending:
        st.warning("🆘 SOS pending — add recovery details")
    st.divider()
    page = st.radio(
        "Navigate",
        ["📋 Log Entry", "📊 Dashboard", "🔬 Research", "📅 History", "⚙️ Settings"],
        label_visibility="collapsed",
    )
    st.divider()
    if not st.session_state.reset_confirm:
        if st.button("🗑️ Reset All Data", use_container_width=True):
            st.session_state.reset_confirm = True
            st.rerun()
    else:
        st.warning("This will permanently delete all your logs and agent memory.")
        c1, c2 = st.columns(2)
        if c1.button("Confirm", type="primary", use_container_width=True):
            result = api_post("/reset", {})
            if result:
                for key in ["intake_messages", "research_messages", "sos_pending", "sos_data"]:
                    st.session_state[key] = [] if key.endswith("messages") or key == "sos_data" else False
                st.session_state.reset_confirm = False
                st.success("All data reset.")
                st.rerun()
        if c2.button("Cancel", use_container_width=True):
            st.session_state.reset_confirm = False
            st.rerun()

# ── Profile helpers ───────────────────────────────────────────────────────────

_hs = _profile.get("hormonal_status")
_show_cycle_day = _hormonal_shows_cycle(_hs)
_show_hormonal_section = _hormonal_shows_section(_hs)
_known_food_triggers = _profile.get("known_food_triggers") or []
_profile_home_city = _profile.get("home_city") or ""
_profile_bedtime = _parse_bedtime(_profile, "typical_bedtime", time(22, 30))
_profile_wake = _parse_bedtime(_profile, "typical_wake_time", time(6, 30))
_profile_prev_meds = _profile.get("preventive_medications") or []
_profile_supps = _profile.get("supplements") or []
_profile_hydration_oz = _profile.get("typical_hydration_oz") or 64.0
_caff_level_to_mg = {"none": 0, "light": 100, "moderate": 300, "heavy": 500}
_profile_caffeine_mg = float(_caff_level_to_mg.get(_profile.get("typical_caffeine_level") or "moderate", 200))
_typical_sleep_hours = _calc_sleep_hours(_profile_bedtime, _profile_wake)

# ── Page: Log Entry ───────────────────────────────────────────────────────────

if page == "📋 Log Entry":
    st.title("📋 Log Entry")

    if st.session_state.intake_messages:
        st.subheader("Intake Agent")
        for msg in st.session_state.intake_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        reply = st.chat_input("Reply to the intake agent...")
        if reply:
            st.session_state.intake_messages.append({"role": "user", "content": reply})
            with _progress("🧠 Updating record..."):
                analysis = call_analyze("log_entry", message=reply)
            if analysis and analysis.get("messages"):
                for msg in analysis["messages"]:
                    st.session_state.intake_messages.append({"role": "assistant", "content": msg})
            st.rerun()
        if st.button("📋 Log another entry", use_container_width=True):
            st.session_state.intake_messages = []
            st.rerun()
        st.stop()

    migraine_occurred = st.toggle("Migraine today?", key="migraine_toggle")

    # ── Quick path: migraine-free day ─────────────────────────────────────────
    if not migraine_occurred:
        st.caption("✅ Great day — 30-second check-in")

        with st.form("log_form_free", clear_on_submit=False):
            entry_date = st.date_input("Date", value=date.today(), max_value=date.today())

            c1, c2 = st.columns(2)
            sleep_quality = c1.slider("Sleep quality last night", 1, 10, 6, key="slq_free")
            stress_level  = c2.slider("Stress level today", 1, 10, _profile.get("typical_stress_level") or 3, key="stress_free")

            if _known_food_triggers:
                trigger_foods_today = st.multiselect(
                    "Any of your trigger foods today? *(leave empty if none)*",
                    options=_known_food_triggers,
                    default=[],
                )
            else:
                trigger_foods_today = []

            hydration_choice = st.radio(
                "Hydration today",
                ["👍 Good", "😐 Average", "👎 Low"],
                index=1,
                horizontal=True,
            )

            notes = st.text_area("Anything notable? *(optional)*", placeholder="Stress source, unusual food, fragrance, anything...")
            submitted_free = st.form_submit_button("💾 Save", type="primary", use_container_width=True)

        if submitted_free:
            _hydration_map = {
                "👍 Good": round(_profile_hydration_oz * 1.2, 1),
                "😐 Average": _profile_hydration_oz,
                "👎 Low": round(_profile_hydration_oz * 0.55, 1),
            }
            _submit_log({
                "entry_date": str(entry_date),
                "migraine_occurred": False,
                "sleep_hours": _typical_sleep_hours,
                "sleep_quality": sleep_quality,
                "stress_level": stress_level,
                "foods": trigger_foods_today or None,
                "hydration_oz": _hydration_map[hydration_choice],
                "notes": notes or None,
            })

    # ── Migraine path ─────────────────────────────────────────────────────────
    else:
        if not st.session_state.sos_pending:
            st.caption("🔴 Quick capture now — add the details when you recover.")

            with st.form("sos_form", clear_on_submit=False):
                entry_date  = st.date_input("Date", value=date.today(), max_value=date.today())
                sos_time_val = datetime.now().strftime("%H:%M")
                st.markdown("#### Pain level right now")
                pain_level = st.select_slider(" ", options=list(range(1, 11)), value=7,
                    format_func=lambda x: f"{'🟢' if x <= 3 else '🟡' if x <= 6 else '🔴'} {x}")
                st.markdown("#### Medication taken?")
                med_quick = st.radio(" ", _SOS_QUICK_MEDS, horizontal=True)
                submitted_sos = st.form_submit_button("🆘 Log Now — I'll add details later", type="primary", use_container_width=True)

            if submitted_sos:
                st.session_state.sos_pending = True
                st.session_state.sos_data = {
                    "date": str(entry_date),
                    "time": sos_time_val,
                    "pain_level": pain_level,
                    "medication": med_quick if med_quick != "None yet" else None,
                }
                st.rerun()

        else:
            sos = st.session_state.sos_data
            st.info(f"🔴 Migraine logged at **{sos.get('time', '')}** — pain **{sos.get('pain_level', '?')}/10**. Add a few details when you feel up to it.")
            if st.button("❌ Clear (false alarm)"):
                st.session_state.sos_pending = False
                st.session_state.sos_data = {}
                st.rerun()
            st.divider()

            # ── Auto-derive context from yesterday's log ──────────────────────
            _recent_logs = api_get("/logs", {"limit": 5}) or []
            _yesterday_log = next((l for l in _recent_logs if not l.get("migraine_occurred")), None)

            _auto_sleep_hours = _yesterday_log.get("sleep_hours") if _yesterday_log else _typical_sleep_hours
            _auto_sleep_quality = _yesterday_log.get("sleep_quality") if _yesterday_log else None
            _auto_stress = _yesterday_log.get("stress_level") if _yesterday_log else None
            _auto_hydration = _yesterday_log.get("hydration_oz") if _yesterday_log else _profile_hydration_oz
            _auto_caffeine = _yesterday_log.get("caffeine_mg") if _yesterday_log else _profile_caffeine_mg
            _auto_foods = _yesterday_log.get("foods") or [] if _yesterday_log else []

            # ── Show auto-derived context panel ───────────────────────────────
            with st.expander("📋 Pre-filled from your previous log — no need to re-enter", expanded=True):
                _ctx_cols = st.columns(4)
                _ctx_cols[0].metric("Sleep", f"{_auto_sleep_hours}h" if _auto_sleep_hours else "—")
                _ctx_cols[1].metric("Sleep quality", f"{_auto_sleep_quality}/10" if _auto_sleep_quality else "—")
                _ctx_cols[2].metric("Stress", f"{_auto_stress}/10" if _auto_stress else "—")
                _ctx_cols[3].metric("Hydration", f"{round(_auto_hydration)} oz" if _auto_hydration else "—")
                if _auto_foods:
                    st.caption(f"Foods logged: {', '.join(_auto_foods)}")
                if not _yesterday_log:
                    st.caption("No recent log found — context will be estimated from your profile baseline.")

            st.markdown("#### Just answer these — we'll handle the rest")

            # ── Determine dynamic question from top trigger ───────────────────
            _sos_state = api_get("/analyze/state/me") or {}
            _confirmed = _sos_state.get("confirmed_triggers", [])
            _suspected = _sos_state.get("suspected_triggers", [])
            _all_triggers = _confirmed + _suspected
            _dynamic_label = "Anything unusual in your environment, diet, or routine in the past 24 hours?"
            if _all_triggers:
                _top = _all_triggers[0].lower()
                if any(k in _top for k in ["sleep", "insomnia"]):
                    _dynamic_label = f"Sleep is one of your top triggers — did the previous night feel worse than usual, beyond what's shown above?"
                elif any(k in _top for k in ["caffeine", "coffee"]):
                    _dynamic_label = "Caffeine is a suspected trigger — did you skip or significantly reduce it today?"
                elif any(k in _top for k in ["stress"]):
                    _dynamic_label = "Stress is linked to your migraines — what was weighing on you in the past 24 hours?"
                elif any(k in _top for k in ["weather", "pressure", "barometric"]):
                    _dynamic_label = "Weather changes are a trigger for you — did you notice the headache building with any weather shift?"
                elif any(k in _top for k in ["hormonal", "menstrual", "cycle"]):
                    _dynamic_label = "Hormonal patterns are a factor for you — where are you in your cycle right now (day number if known)?"
                else:
                    _dynamic_label = f"One of your triggers is **{_all_triggers[0]}** — any exposure to it in the past 24 hours?"

            with st.form("sos_smart_form", clear_on_submit=False):
                # Q1 — Prodrome
                st.markdown("**1. Any warning signs before it hit?**")
                _prior_prodromes = []
                for _ml in _recent_logs:
                    if _ml.get("prodrome_symptoms"):
                        _prior_prodromes += _ml["prodrome_symptoms"]
                _prodrome_opts = ["brain_fog", "fatigue", "food_cravings", "light_sensitivity",
                                  "mood_changes", "nausea", "neck_stiffness", "visual_aura", "yawning"]
                _prodrome_defaults = [p for p in list(dict.fromkeys(_prior_prodromes)) if p in _prodrome_opts][:3]
                prodrome = st.multiselect("Prodrome symptoms", _prodrome_opts,
                                          default=_prodrome_defaults, label_visibility="collapsed")

                # Q2 — Pain location + duration
                st.markdown("**2. Pain: where and how long?**")
                _q2_c1, _q2_c2, _q2_c3 = st.columns(3)
                pain_level = _q2_c1.slider("Pain level", 1, 10, sos.get("pain_level", 7))
                pain_location = _q2_c2.selectbox("Location",
                    ["", "behind_eye", "bilateral_temporal", "frontal", "full_head", "occipital", "temporal_left", "temporal_right"])
                duration_hours = _q2_c3.number_input("Duration (hrs)", 0.0, 72.0, step=0.5)

                # Q3 — Relief
                st.markdown("**3. What helped?**")
                _q3_c1, _q3_c2 = st.columns([2, 1])
                relief_methods = _q3_c1.multiselect("Relief methods",
                    ["acupressure", "breathing_exercises", "caffeine", "cold_shower", "dark_room",
                     "heat_pack", "hydration", "ice_pack", "lying_down", "meditation", "sleep", "vomiting_relief"],
                    label_visibility="collapsed")
                relief_effectiveness = _q3_c2.slider("Effectiveness", 1, 10, 5, label_visibility="collapsed")

                # Medication — pre-fill from SOS
                sos_med = sos.get("medication")
                _default_meds = [sos_med] if sos_med and sos_med in _MIGRAINE_MEDICATIONS else []
                medications = st.multiselect("Medications taken", _MIGRAINE_MEDICATIONS, default=_default_meds)

                # Q4 — Dynamic trigger question
                st.markdown(f"**4. {_dynamic_label}**")
                dynamic_answer = st.text_input("Your answer", label_visibility="collapsed",
                                               placeholder="Type your answer here...")

                # Hormonal — only if relevant
                if _show_cycle_day:
                    menstrual_cycle_day = st.number_input("Cycle day *(optional)*", 0, 35, 0)
                else:
                    menstrual_cycle_day = None

                submitted_smart = st.form_submit_button("💾 Submit", type="primary", use_container_width=True)

            if submitted_smart:
                st.session_state.sos_pending = False
                st.session_state.sos_data = {}
                _notes_parts = []
                if dynamic_answer.strip():
                    _notes_parts.append(f"[Trigger check] {_dynamic_label} — {dynamic_answer.strip()}")
                _submit_log({
                    "entry_date": sos.get("date", str(date.today())),
                    "migraine_occurred": True,
                    "city": _profile_home_city or None,
                    "pain_level": pain_level,
                    "pain_location": pain_location or None,
                    "duration_hours": duration_hours or None,
                    "prodrome_symptoms": prodrome or None,
                    # auto-derived from yesterday's log
                    "sleep_hours": _auto_sleep_hours,
                    "sleep_quality": _auto_sleep_quality,
                    "stress_level": _auto_stress,
                    "foods": _auto_foods or None,
                    "hydration_oz": _auto_hydration,
                    "caffeine_mg": _auto_caffeine,
                    "medications": medications or None,
                    "relief_methods": relief_methods or None,
                    "relief_effectiveness": relief_effectiveness if relief_methods else None,
                    "menstrual_cycle_day": menstrual_cycle_day or None,
                    "notes": "\n".join(_notes_parts) or None,
                })
                st.rerun()

# ── Page: Dashboard ───────────────────────────────────────────────────────────

elif page == "📊 Dashboard":
    st.title("📊 Dashboard")

    with _progress("📊 Loading dashboard...", 0.6):
        logs = api_get("/logs", {"limit": 60}) or []
        state = api_get("/analyze/state/me") or {}

    if not logs:
        st.info("No logs yet. Start on the Log Today page.")
    else:
        last_30 = logs[:30]
        migraine_days = [l for l in last_30 if l.get("migraine_occurred")]
        pain_scores = [l["pain_level"] for l in migraine_days if l.get("pain_level")]
        avg_pain = sum(pain_scores) / len(pain_scores) if pain_scores else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Migraines (30d)", len(migraine_days))
        c2.metric("Avg Pain (30d)", f"{avg_pain:.1f}/10" if avg_pain else "—")
        c3.metric("Total Logs", len(logs))
        c4.metric("Migraine-free streak", f"{migraine_free_streak(logs)}d")

        st.divider()
        load = api_get("/logs/toxic-load") or {}
        if load:
            risk = load.get("risk_level", "low")
            fill = load.get("fill_pct", 0.0)
            rolling = load.get("rolling_score", 0.0)
            threshold = load.get("threshold", 10.0)
            breakdown = load.get("breakdown", {})
            risk_color = {"low": "🟢", "moderate": "🟡", "high": "🟠", "critical": "🔴"}.get(risk, "⚪")
            st.subheader(f"{risk_color} Trigger Bucket  —  {risk.upper()}")
            carryover = load.get("carryover_score", 0.0)
            st.caption(f"Rolling load: **{rolling}** / {threshold} threshold  ·  Today: {load.get('today_score', 0)}  ·  Carry-over: {carryover}")
            st.progress(min(fill / 100, 1.0))
            if breakdown:
                st.caption("Today's contributors: " + "  ·  ".join(f"**{k.replace('_', ' ')}** +{v}" for k, v in sorted(breakdown.items(), key=lambda x: -x[1])))
            else:
                st.caption("No triggers logged today.")

        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Triggers")
            confirmed = state.get("confirmed_triggers", [])
            suspected = state.get("suspected_triggers", [])
            if confirmed:
                st.markdown("**Confirmed**")
                for t in confirmed:
                    st.markdown(f"- 🔴 {t}")
            if suspected:
                st.markdown("**Suspected**")
                for t in suspected:
                    st.markdown(f"- 🟡 {t}")
            if not confirmed and not suspected:
                st.caption("No triggers identified yet.")

        with col2:
            st.subheader("Root Cause Hypothesis")
            hypothesis = state.get("current_root_cause_hypothesis", "")
            subtype = state.get("migraine_subtype", "")
            evidence = state.get("root_cause_evidence", [])
            if hypothesis:
                if subtype:
                    st.caption(f"Subtype: `{subtype}`")
                st.write(hypothesis)
                if evidence:
                    st.markdown("**Evidence**")
                    for ev in evidence:
                        claim = ev.get("claim", "")
                        source = ev.get("source", "")
                        stype = ev.get("source_type", "")
                        _badge = {"log_history": "🗓", "onboarding": "📋", "weather": "🌦",
                                  "agent_memory": "🧠", "stats": "📊"}.get(stype, "•")
                        st.markdown(f"{_badge} {claim} `[{source}]`")
            else:
                st.caption("No hypothesis yet.")

        st.divider()
        st.subheader("Current Protocol")
        protocol = state.get("current_protocol", {})
        if protocol and protocol.get("active_items"):
            st.caption(f"Version {protocol.get('version', 1)} · {protocol.get('date', '')}")
            for item in protocol["active_items"]:
                with st.expander(f"Tier {item['tier']} — {item['intervention']}"):
                    st.write(f"**Detail:** {item['dose_or_detail']}")
                    st.write(f"**Rationale:** {item['rationale']}")
                    st.write(f"**What to log:** {item['what_to_log']}")
                    st.caption(f"Assess after {item['assessment_weeks']} weeks")
        else:
            st.caption("No protocol yet.")

        st.divider()
        st.subheader("📊 Lifestyle Audit")
        st.caption("On-demand: what's slipping, what worked, and non-medication protocols grounded in your data.")
        if st.button("Run Lifestyle Audit", use_container_width=True):
            with _progress("🌿 Generating your personalised plan...", 0.6):
                _pc_result = call_analyze("lifestyle_audit")
            if _pc_result and _pc_result.get("messages"):
                chained = _pc_result.get("protocol_refresh_recommended", False)
                audit_msg = _pc_result["messages"][-2] if chained else _pc_result["messages"][-1]
                st.session_state["lifestyle_audit_output"] = audit_msg
                st.rerun()

        if st.session_state.get("lifestyle_audit_output"):
            with st.expander("Your Lifestyle Audit", expanded=True):
                st.markdown(st.session_state["lifestyle_audit_output"])

        st.divider()
        c1, c2, c3 = st.columns(3)
        if c1.button("🔄 Run Pattern Analysis", use_container_width=True):
            with _progress("🔄 Analyzing patterns..."):
                call_analyze("pattern_review")
            st.success("Done. Refresh to see updated triggers.")
        if c2.button("🧠 Run Root Cause Analysis", use_container_width=True):
            with _progress("🧠 Analyzing root cause..."):
                call_analyze("root_cause_review")
            st.success("Done. Refresh to see updated hypothesis.")
        if c3.button("📋 Generate Protocol", use_container_width=True):
            with _progress("📋 Generating protocol..."):
                call_analyze("protocol_review")
            st.success("Done. Refresh to see your protocol.")

# ── Page: Research ────────────────────────────────────────────────────────────

elif page == "🔬 Research":
    st.title("🔬 Research")
    st.caption("Ask anything about migraines, triggers, treatments, or mechanisms.")

    for msg in st.session_state.research_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    question = st.chat_input("Ask a research question...")
    if question:
        st.session_state.research_messages.append({"role": "user", "content": question})
        with _progress("🔬 Researching..."):
            result = call_analyze("research_request", message=question)
        if result and result.get("messages"):
            for msg in result["messages"]:
                st.session_state.research_messages.append({"role": "assistant", "content": msg})
        elif result is None:
            st.session_state.research_messages.append({
                "role": "assistant",
                "content": "Something went wrong reaching the AI service. Check your Google API key and try again.",
            })
        st.rerun()

# ── Page: History ─────────────────────────────────────────────────────────────

elif page == "📅 History":
    st.title("📅 History")
    with _progress("📅 Loading history...", 0.6):
        logs = api_get("/logs", {"limit": 30}) or []

    if not logs:
        st.info("No logs yet.")
    else:
        for log in logs:
            icon = "🔴" if log.get("migraine_occurred") else "🟢"
            label = f"{icon} {log['entry_date']}"
            if log.get("pain_level"):
                label += f" — pain {log['pain_level']}/10"
            with st.expander(label):
                c1, c2 = st.columns(2)
                with c1:
                    if log.get("pain_location"):
                        st.write(f"**Location:** {log['pain_location']}")
                    st.write(f"**Sleep:** {log.get('sleep_hours', '—')} hrs · quality {log.get('sleep_quality', '—')}/10")
                    st.write(f"**Stress:** {log.get('stress_level', '—')}/10 — {log.get('stress_source') or '—'}")
                    if log.get("prodrome_symptoms"):
                        st.write(f"**Prodrome:** {', '.join(log['prodrome_symptoms'])}")
                with c2:
                    if log.get("medications"):
                        st.write(f"**Medications:** {', '.join(log['medications'])}")
                    if log.get("foods"):
                        st.write(f"**Foods:** {', '.join(log['foods'])}")
                    st.write(f"**Hydration:** {log.get('hydration_oz', '—')} oz · Caffeine: {log.get('caffeine_mg', '—')} mg")
                if log.get("notes"):
                    st.write(f"**Notes:** {log['notes']}")

# ── Page: Settings ────────────────────────────────────────────────────────────

elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    st.caption("Update your profile — changes take effect on your next log entry.")

    p = _profile

    with st.form("settings_form"):
        st.subheader("Migraine History")
        c1, c2 = st.columns(2)
        _dur_opts = ["<1yr", "1-5yr", "5+yr"]
        _freq_opts = ["<1/month", "1-3/month", "weekly", "daily"]
        migraine_duration = c1.selectbox("Duration", _dur_opts,
            index=_dur_opts.index(p.get("migraine_duration", "<1yr")) if p.get("migraine_duration") in _dur_opts else 0)
        migraine_frequency = c2.selectbox("Frequency", _freq_opts,
            index=_freq_opts.index(p.get("migraine_frequency", "1-3/month")) if p.get("migraine_frequency") in _freq_opts else 1)
        migraine_subtype = st.text_input("Subtype (optional)", value=p.get("migraine_subtype") or "")

        st.subheader("Location")
        home_city_s = st.text_input("Home city", value=p.get("home_city") or "",
                                    placeholder="e.g. Austin, TX  or  London, UK")

        st.subheader("Known Triggers")
        known_food_triggers = st.multiselect("Food triggers", _ref_foods, default=p.get("known_food_triggers") or [])
        other_triggers = st.text_input("Other triggers", value=p.get("other_triggers") or "")

        st.subheader("Baseline")
        c1, c2, c3 = st.columns(3)
        typical_bedtime = _time_picker_widget("Typical bedtime", value=_parse_bedtime(p, "typical_bedtime", time(22, 30)), key="s_bt")
        typical_wake = _time_picker_widget("Typical wake time", value=_parse_bedtime(p, "typical_wake_time", time(6, 30)), key="s_wt")
        typical_stress = c3.slider("Typical stress level", 1, 10, p.get("typical_stress_level") or 5)
        _job_opts = ["desk", "active", "mixed"]
        job_type = st.selectbox("Job type", _job_opts,
            index=_job_opts.index(p.get("job_type", "desk")) if p.get("job_type") in _job_opts else 0)

        st.subheader("Baseline Habits")
        c1, c2 = st.columns(2)
        typical_hydration_oz = c1.slider(
            "Typical daily water (oz)", 16, 120,
            value=int(p.get("typical_hydration_oz") or 64), step=8,
            help="8 oz = 1 cup  ·  64 oz = 8 cups",
        )
        _caff_s_opts = [
            "None",
            "Light  (1–2 cups / <200 mg)",
            "Moderate  (2–3 cups / 200–400 mg)",
            "Heavy  (3+ cups / >400 mg)",
        ]
        _caff_s_map = {
            "None": "none",
            "Light  (1–2 cups / <200 mg)": "light",
            "Moderate  (2–3 cups / 200–400 mg)": "moderate",
            "Heavy  (3+ cups / >400 mg)": "heavy",
        }
        _caff_s_rev = {v: k for k, v in _caff_s_map.items()}
        _caff_s_sel = c2.selectbox(
            "Typical caffeine intake",
            _caff_s_opts,
            index=_caff_s_opts.index(
                _caff_s_rev.get(p.get("typical_caffeine_level", "none"), "None")
            ),
        )
        typical_caffeine_level = _caff_s_map[_caff_s_sel]

        st.subheader("Hormonal Profile")
        status_labels = list(_HORMONAL_STATUSES.values())
        status_keys = list(_HORMONAL_STATUSES.keys())
        current_hs_key = p.get("hormonal_status", "prefer_not_to_say")
        current_hs_label = _HORMONAL_STATUSES.get(current_hs_key, status_labels[-1])
        sel_status_label = st.selectbox("Hormonal status", status_labels,
            index=status_labels.index(current_hs_label))
        sel_status_key = status_keys[status_labels.index(sel_status_label)]

        cycle_length_days = None
        migraines_cluster_period = None
        worst_hormonal_phase = None
        if _hormonal_shows_cycle(sel_status_key):
            c1, c2 = st.columns(2)
            cycle_length_days = c1.number_input("Cycle length (days)", 0, 60, p.get("cycle_length_days") or 28)
            _cp_opts = ["yes", "no", "not_sure"]
            migraines_cluster_period = c2.selectbox("Migraines cluster around period?",
                ["Yes", "No", "Not sure"],
                index=["yes", "no", "not_sure"].index(p.get("migraines_cluster_period", "not_sure")) if p.get("migraines_cluster_period") in _cp_opts else 2)
            migraines_cluster_period = {"Yes": "yes", "No": "no", "Not sure": "not_sure"}[migraines_cluster_period]
            _wp_opts = ["before", "during", "after", "no_pattern"]
            worst_hormonal_phase = st.selectbox("Worst hormonal phase",
                ["Before", "During", "After", "No pattern"],
                index=["before", "during", "after", "no_pattern"].index(p.get("worst_hormonal_phase", "no_pattern")) if p.get("worst_hormonal_phase") in _wp_opts else 3)
            worst_hormonal_phase = {"Before": "before", "During": "during", "After": "after", "No pattern": "no_pattern"}[worst_hormonal_phase]

        st.subheader("Medications")
        preventive_medications = st.multiselect("Preventive medications", _MIGRAINE_MEDICATIONS, default=p.get("preventive_medications") or [])
        supplements_settings = st.multiselect("Supplements", ["butterbur", "CoQ10", "feverfew", "magnesium", "melatonin", "riboflavin_B2"], default=p.get("supplements") or [])
        acute_medications = st.multiselect("Acute medications on hand", _MIGRAINE_MEDICATIONS, default=p.get("acute_medications") or [])

        saved = st.form_submit_button("💾 Save changes", type="primary", use_container_width=True)

    if saved:
        result = api_patch("/profile/me", {
            "migraine_duration": migraine_duration,
            "migraine_frequency": migraine_frequency,
            "migraine_subtype": migraine_subtype or None,
            "home_city": home_city_s or None,
            "known_food_triggers": known_food_triggers or None,
            "other_triggers": other_triggers or None,
            "typical_bedtime": typical_bedtime.strftime("%H:%M") if typical_bedtime else None,
            "typical_wake_time": typical_wake.strftime("%H:%M") if typical_wake else None,
            "typical_stress_level": typical_stress,
            "job_type": job_type,
            "hormonal_status": sel_status_key,
            "cycle_length_days": int(cycle_length_days) if cycle_length_days else None,
            "migraines_cluster_period": migraines_cluster_period,
            "worst_hormonal_phase": worst_hormonal_phase,
            "preventive_medications": preventive_medications or None,
            "supplements": supplements_settings or None,
            "acute_medications": acute_medications or None,
            "typical_hydration_oz": float(typical_hydration_oz),
            "typical_caffeine_level": typical_caffeine_level,
        })
        if result:
            st.success("Profile updated.")
            st.rerun()
