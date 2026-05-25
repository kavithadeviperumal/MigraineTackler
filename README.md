# MigraineTackler 🧠

> I have frequent migraines. After years of apps that logged my symptoms 
> without helping me understand *why* they kept happening, I built the 
> tool I actually needed.

MigraineTackler is a multi-agent AI system that doesn't just track 
migraines — it reasons about them. It distinguishes prodrome signals from 
triggers, identifies cumulative threshold patterns across time, synthesizes 
research across medical frameworks, and generates root cause hypotheses 
tailored to your history.

---

## The Problem with Existing Migraine Apps

Most migraine apps are glorified diaries. They record what happened. 
They don't explain why.

The clinical reality is more complex:

- **Migraines don't have single causes.** They occur when cumulative 
  triggers cross a personal threshold — poor sleep + barometric pressure 
  drop + high stress together, not any one factor alone.
- **What looks like a trigger is often a prodrome.** A chocolate craving 
  before a migraine is frequently an early symptom of a migraine already 
  in progress — not the cause. Misreading this leads to wrong avoidance 
  and no resolution.
- **Root causes span medical frameworks.** Neurological vulnerability, 
  hormonal patterns, nutritional deficiencies, and stress dysregulation 
  each explain different pieces of the same pattern.

MigraineTackler was built around these realities.

---

## What It Does

- **Logs intelligently** — captures lifestyle, diet, weather, medication, 
  hormonal, and environmental data with targeted clinical follow-up 
  questions, not generic forms
- **Detects patterns** — analyzes 10–50 entries to identify confirmed 
  triggers, lag effects, hormonal cycles, and protective factors
- **Synthesizes research** — pulls evidence across Western medicine, 
  functional medicine, TCM, and Ayurveda with tiered confidence scoring
- **Generates root cause hypotheses** — three-layer analysis: 
  proximal triggers → physiological vulnerabilities → upstream root causes
- **Builds personalized protocols** — 5-tier intervention recommendations 
  based on your specific pattern and root cause hypothesis
- **Alerts proactively** — hard-coded safety alerts for medication overuse 
  (MOH) and red flag symptoms; risk notifications when trigger conditions align

---

## Architecture

### Two-Layer Design

Safety-critical logic is **deterministic and never touches the LLM**. 
AI handles synthesis and judgment only.

User Input
↓
┌─────────────────────────────────┐
│  Layer 1: Rules Engine          │
│  - MOH detection                │
│    (≥10 medication days/month)  │
│  - Red flag symptom detection   │
│  - Trigger frequency tracking   │
│  - Weather/AQI enrichment       │
└────────────────┬────────────────┘
↓ (if no safety alert)
┌─────────────────────────────────┐
│  Layer 2: LanGraph Agents       │
│  - Orchestrator routes intent   │
│  - Loads shared memory context  │
│  - Delegates to specialist      │
└─────────────────────────────────┘



### The 5 Agents

| Agent | Triggers | Role |
|-------|----------|------|
| **Intake** | After every log entry | Targeted follow-up questions — distinguishes prodrome from trigger |
| **Pattern** | After 2+ log entries | Analyzes history + weather data — confirms triggers, detects lag effects and hormonal patterns |
| **Research** | On research requests | Evidence synthesis across 4 medical frameworks, tiered by confidence (RCT → traditional knowledge) |
| **Root Cause** | Weekly or on milestone | 3-layer causal hypothesis across Western, functional, TCM, and Ayurvedic frameworks |
| **Protocol** | After root cause updates | Personalized 5-tier intervention plan from safety-first to advanced interventions |

### Shared Memory

All agents read and write a persistent memory store via LanGraph 
PostgresSaver checkpointing:

- Confirmed / suspected / ruled-out triggers
- Current root cause hypothesis
- Active protocol
- Medical frameworks applied
- Research findings and session history

Every agent starts with complete context. No conversation resets between sessions.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit |
| Backend | FastAPI + Uvicorn |
| Agent Orchestration | LanGraph + LangChain |
| LLM | Google Gemini 2.0 Flash |
| Database | PostgreSQL + pgvector |
| ORM | SQLModel |
| Auth | JWT |
| Background Jobs | APScheduler |
| Observability | LangSmith |
| External APIs | OpenWeatherMap, EPA AirNow |

**Python 3.11+**

---

## Key Design Decisions

**Why deterministic safety logic?**  
LLMs are probabilistic. A 95% detection rate for MOH alerts or red flag 
symptoms is clinically unacceptable. Hard-coded rules guarantee the same 
output for the same input — every time. The LLM handles judgment; 
deterministic code handles facts.

**Why LanGraph?**  
Longitudinal health tracking requires persistent state. LanGraph's 
PostgresSaver checkpoints every agent's memory to the database — a user 
who returns after a week picks up with full context, confirmed triggers, 
and current hypothesis intact. Conditional routing also makes the agent 
graph explicit, debuggable, and auditable.

**Why multi-framework analysis?**  
Chronic migraine patients have often exhausted conventional approaches. 
Different medical frameworks identify different patterns in the same data. 
The system generates hypotheses across all four for the user to explore 
with their practitioners.

**Known limitation:** Multi-framework analysis quality depends on the 
model's training data. This system generates hypotheses for exploration — 
not clinical diagnoses. Next build: RAG over PubMed and specialized 
medical databases to ground synthesis in retrieved evidence.

---

## Roadmap

- [ ] RAG over PubMed + TCM/Ayurvedic databases  
- [ ] Switch to Claude API for stronger multi-framework reasoning  
- [ ] Apple Shortcuts voice logging for iPhone (reduce in-migraine friction)  
- [ ] Proactive risk alerts via email when trigger conditions align  
- [ ] React Native mobile frontend  

---

## Setup

**Prerequisites:** PostgreSQL running locally, Python 3.11+

```bash
# Clone
git clone https://github.com/kavithadeviperumal/MigraineTackler
cd MigraineTackler

# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env
Edit .env with your keys:


GOOGLE_API_KEY=          # aistudio.google.com
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=       # smith.langchain.com
LANGCHAIN_PROJECT=       # your project name
OPENWEATHER_API_KEY=     # openweathermap.org
OPENWEATHER_CITY=        # your city
OPENWEATHER_COUNTRY_CODE=# e.g. US
AIRNOW_API_KEY=          # airnowapi.org
AIRNOW_ZIP=              # your zip code
DB_PATH=                 # path to migraine.db
LANGGRAPH_DB_PATH=       # path to langgraph.db
JWT_SECRET_KEY=          # any strong secret
JWT_EXPIRE_DAYS=30
LOG_LEVEL=INFO

# Run backend
uvicorn app.api.main:app --reload

# Run frontend (separate terminal)
streamlit run streamlit_app.py
License
MIT


