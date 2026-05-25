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

```mermaid
flowchart TD
    A([User Input]) --> B

    subgraph L1["⚙️  Layer 1 — Rules Engine  (deterministic)"]
        B[MOH detection\n≥10 medication days / month]
        C[Red flag symptom check]
        D[Trigger frequency tracking]
        E[Weather & AQI enrichment]
    end

    B --> F{Safety alert?}
    C --> F
    D --> F
    E --> F

    F -->|Yes| G[🚨 Alert shown directly\nLLM bypassed]
    F -->|No| H

    subgraph L2["🤖  Layer 2 — LangGraph Agents  (AI)"]
        H[Orchestrator routes intent] --> I[Loads shared memory context]
        I --> J[Delegates to specialist agent]
    end
```



### The 6 Agents

| Agent | Triggers | Role |
|-------|----------|------|
| **Intake** | After every log entry | Targeted follow-up questions — distinguishes prodrome from trigger |
| **Pattern** | After 2+ log entries | Analyzes history + weather data — confirms triggers, detects lag effects and hormonal patterns |
| **Research** | On research requests | Retrieves real abstracts from PubMed + Semantic Scholar; LLM synthesizes from retrieved evidence only |
| **Root Cause** | Weekly or on milestone | 3-layer causal hypothesis grounded in the user's own data with structured evidence provenance |
| **Protocol** | After root cause updates | Personalized 5-tier intervention plan from safety-first to advanced interventions |
| **Preventive Care** | On demand | Reviews what's slipping, what worked, and surfaces non-medication preventive protocols |

### Shared Memory

All agents read and write a persistent memory store via LangGraph
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
| Agent Orchestration | LangGraph + LangChain |
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

**Why LangGraph?**  
Longitudinal health tracking requires persistent state. LangGraph's
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
model's training data. The research node retrieves real abstracts from
PubMed and Semantic Scholar at query time — but TCM and Ayurvedic
literature is not yet covered by a dedicated retrieval source. This
system generates hypotheses for exploration, not clinical diagnoses.

---

## Roadmap

- [x] RAG over PubMed + Semantic Scholar (live abstract retrieval, no training-weight citations)
- [ ] RAG over TCM and Ayurvedic literature databases
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
```

Edit `.env` with your keys:

```env
GOOGLE_API_KEY=           # aistudio.google.com
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=        # smith.langchain.com
LANGCHAIN_PROJECT=        # your project name
OPENWEATHER_API_KEY=      # openweathermap.org
OPENWEATHER_CITY=         # your city
OPENWEATHER_COUNTRY_CODE= # e.g. US
AIRNOW_API_KEY=           # airnowapi.org (US only)
AIRNOW_ZIP=               # your zip code
DATABASE_URL=             # postgresql://user:password@localhost:5432/migrainetackler
JWT_SECRET_KEY=           # generate: python -c "import secrets; print(secrets.token_hex(32))"
JWT_EXPIRE_DAYS=30
LOG_LEVEL=INFO
```

```bash
# Run backend
uvicorn app.api.main:app --reload

# Run frontend (separate terminal)
streamlit run streamlit_app.py
```

---

## License

MIT
