## Market Research: Migraine Diary and Tracking Apps

### 1. Market Size

- **Digital Therapeutics for Migraine (TAM):** $1.7B in 2025 → $4.82B by 2030 at **23.2% CAGR** *(The Business Research Company / GII Research, 2026)*
- **Migraine Forecasting Apps (subset TAM):** ~$425M in 2024; North America ~41% (~$175M); CAGR **21.3% through 2033** *(DataIntelo, 2024)*
- **SAM (smartphone-owning chronic migraine sufferers, English-speaking markets):** ~39M people globally have chronic migraine; only **0.2% currently use a dedicated migraine app** — massive white space *(research2guidance)*
- **SOM (realistic 3-yr capture for a new AI entrant):** Targeting 0.05–0.1% of the global ~1B migraine sufferers = 500K–1M users; at $5–8/mo avg revenue = **$30M–$96M ARR potential**
- **Key driver:** FDA clearance of CT-132 (Click Therapeutics, April 2025) — first prescription digital therapeutic for episodic migraine — legitimizes the category and signals regulatory pathway

---

### 2. Key Trends

1. **AI + Wearables converging on prediction** — Migraine Buddy + Oura Ring partnership (Jan 2026) pairs HRV, sleep, temperature with symptom logs for pre-attack forecasting. Ultrahuman's Migraine PowerPlug (early 2026) uses biosensors for real-time prediction. Shift: reactive logging → proactive prevention.

2. **Prescription Digital Therapeutics (PDTs) emerging** — FDA's revised General Wellness Policy (Jan 2026) is lowering the barrier for software-as-medical-device classification. CT-132 is the first approved migraine PDT. Competitors will seek clearance; raises the bar for clinical validation.

3. **Hormonal / menstrual migraine is underserved** — Oura-Migraine Buddy integration explicitly targets cycle-driven migraines. ~60% of female migraine sufferers report menstrual triggers — no app owns this segment yet.

4. **Log fatigue is the #1 retention killer** — User research (PMC qualitative review, 2021) consistently flags that apps require too many fields. Users abandon during attacks, when logging is most critical. No app has solved the "30-second migraine-free day check-in" problem.

5. **Clinical credibility is a moat** — Apps recommended by the National Headache Foundation (Migraine Monitor) or validated in peer-reviewed trials command provider trust. B2B2C (employer/payer/clinic channel) is emerging as a monetization path alongside DTC subscriptions.

---

### 3. Competitive Dynamics

| App | Data Collected | Logging UX | AI / Pattern Detection | Pricing | Key Differentiator | Top Complaint |
|---|---|---|---|---|---|---|
| **Migraine Buddy** | Pain, symptoms, triggers, medications, sleep, weather, aura, barometric pressure | Moderate friction — many fields; ~3–5 min per attack | Trigger correlation reports; Oura Ring biometric integration (Jan 2026) | Free + ~$20/mo premium | Largest user base (2M+); #1 doctor-recommended | Premium too expensive; form is overwhelming during attack |
| **N1-Headache / Curelator** | Daily habits, mood, sleep, activity, diet — logged every day | ~5 min/day minimum; requires consistent daily input | Statistical N-of-1 analysis: Trigger Maps, Protector Maps, Suspected Trigger Maps | Free; premium ~$50 one-time | Rigorous statistical methodology; clinician code for free premium | High daily commitment; onboarding complexity; slow to surface insights |
| **Bearable** | Symptoms, mood, medication, sleep, custom factors; Apple Health sync | Flexible but customizable = complex for new users | Correlation surface after 30 days of data; not migraine-specific AI | Free + $34.99/yr ($6.99/mo) | Broadest chronic illness coverage; high ratings (4.8 App Store) | Not migraine-specific; pattern insights require 30+ days |
| **Manage My Pain** | Pain location, intensity, duration, mood, medication, treatments | Standard form; not optimized for speed | Basic visual insights; 30-day history on free tier | Free; insights unlock at $1.79–$7.49/credit | Clinical-grade reports for provider sharing; strong customer support | Long EULA friction; can't edit incomplete logs easily |
| **Migraine Monitor** | Pain intensity, medication dosing, mood, stress, triggers, weather (auto) | Moderate; weather auto-populated reduces friction | AI-assisted headache insights; NHF-endorsed | Free (premium tier exists) | NHF / MRF endorsement; automated weather correlation | Limited AI depth; UI feels dated |
| **Headache Log** | Timer, pain factors, triggers; minimal fields | Fastest UX in category — minimal fields, Android-only | None | Free | Simplest and fastest logging | Android-only; no doctor reports; no data export for printing; no AI |

**Market structure:** Fragmented. No dominant winner. Migraine Buddy leads on volume but not on AI depth. White space exists at the intersection of fast UX + real AI reasoning.

---

### 4. Implications for Us

**Opportunities:**
- **30-sec migraine-free check-in is unbuilt** — every competitor requires similar effort daily vs. during attacks. MigraineTackler's asymmetric logging (30–45 sec clean days / full form on migraine days) directly addresses the #1 dropout cause.
- **LangGraph agent as differentiated backend** — no competitor does root cause analysis or generates personalized protocols. Correlation reports (Migraine Buddy, N1) tell users *what*; we can tell them *why* and *what to do next*.
- **Hormonal migraine segment is open** — integrating cycle data with LangGraph reasoning (e.g., "your last 3 attacks occurred on cycle day 25–27; consider preventive protocol starting day 23") is a concrete, ownable use case.
- **B2B2C channel via clinicians** — NHF endorsement and clinician code programs (N1-Headache model) show provider channel works. Position MigraineTackler reports as AI-generated clinical summaries.

**Threats:**
- Migraine Buddy's Oura partnership accelerates their AI roadmap with real biometric data — they have the user base to win on data volume.
- CT-132 FDA precedent may pressure DTC apps to seek clearance or face credibility gap vs. prescribed solutions.
- Bearable's breadth makes it sticky for users with comorbidities (anxiety, chronic fatigue); MigraineTackler must win on migraine-specific depth.

**Strategic angles:**
- Launch with a razor-sharp "migraine-free day = 30 seconds" promise as the core acquisition hook.
- Publish a small N-of-1 protocol study or partner with a headache clinic for clinical validation.
- Price at $8–10/mo annual — below Migraine Buddy premium, above free tier clutter.

---

### 5. What We Still Don't Know

- **Actual DAU/MAU retention curves** for existing apps — app store ratings don't reveal 30/60/90-day retention; this is the critical unknown for validating our logging UX hypothesis.
- **Willingness to pay for AI-driven protocols** vs. passive tracking — no public data on conversion rates from free to premium tiers for AI features specifically.
- **Clinical channel economics** — what a headache clinic or neurologist actually pays or refers for, and whether they'll endorse an uncleared app.
- **Wearable ownership overlap** — what % of chronic migraine sufferers already own an Oura/Garmin/Apple Watch; determines feasibility of passive biometric data as a differentiator at launch.

---

**Open Questions**
- What is the 90-day retention rate for Migraine Buddy and N1-Headache — do users actually stick through the data-collection phase before insights surface?
- Is there a real market for "personalized migraine protocols" or do patients default to their neurologist's advice regardless of app output?
- What regulatory exposure does MigraineTackler face if LangGraph agents generate treatment recommendations — does that cross into SaMD (Software as a Medical Device) territory?
- Can the 30-second logging UX coexist with enough data richness to produce statistically valid trigger identification, or is there an inherent tension?
- Who is the actual buyer in a B2B2C model — the headache clinic, the health system, or the employer — and what does their procurement process look like?
