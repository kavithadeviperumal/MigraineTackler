# MigraineTackler — System Architecture

## Goal
A personal, long-running health intelligence system that tracks migraine triggers,
finds root causes across Western and Eastern medical frameworks, synthesizes
authentic research, and builds a personalized alleviation protocol — improving
over time as more data is collected.

---

## Design Principles

1. **Deterministic for facts, AI for judgment** — never use an agent where a
   rule or query is sufficient. Agents are expensive and can hallucinate;
   deterministic code cannot.
2. **Structured data in, structured data out** — the AI layer reasons over
   clean, pre-processed records. It does not do data collection.
3. **Agents are specialized, not general** — each agent has one job and a
   scoped prompt. The Orchestrator decides who speaks.
4. **Safety-critical logic is always deterministic** — medication overuse alerts
   and red-flag symptom checks are hard-coded rules, never LLM judgment.
5. **Memory persists across sessions** — the system maintains a shared state
   store so agents build on prior findings rather than starting cold.

---

## System Map

```
User
 │
 ▼
┌─────────────────────────────────────────────┐
│             DETERMINISTIC LAYER             │
│                                             │
│  ┌──────────────┐  ┌─────────────────────┐  │
│  │  Log Form +  │  │  Weather & AQI API  │  │
│  │   Database   │  │  (scheduled fetch)  │  │
│  └──────┬───────┘  └──────────┬──────────┘  │
│         │                     │             │
│  ┌──────▼─────────────────────▼──────────┐  │
│  │           Rules Engine                │  │
│  │  • MOH Alert (≥10 triptan days/30d)   │  │
│  │  • Red-Flag Symptom Checker           │  │
│  │  • Migraine-free streak counter       │  │
│  │  • Trigger frequency aggregation      │  │
│  │  • Stats & charts (pain/time graphs)  │  │
│  └──────────────────┬────────────────────┘  │
└─────────────────────│───────────────────────┘
                      │  structured context packet
                      ▼
┌─────────────────────────────────────────────┐
│                AI AGENT LAYER               │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │           ORCHESTRATOR               │   │
│  │  Routes intent → correct agent       │   │
│  │  Manages shared memory store         │   │
│  │  Assembles context packets           │   │
│  └──┬──────────┬──────────┬────────┬────┘   │
│     │          │          │        │        │
│  ┌──▼──┐  ┌───▼───┐ ┌────▼──┐ ┌───▼────┐   │
│  │     │  │       │ │       │ │        │   │
│  │Intake│  │Pattern│ │Research│ │Root    │   │
│  │Agent │  │ Agent │ │ Agent  │ │Cause   │   │
│  │     │  │       │ │       │ │Agent   │   │
│  └──┬──┘  └───┬───┘ └────┬──┘ └───┬────┘   │
│     │          │          │        │        │
│     └──────────┴──────────┴────────┘        │
│                      │                      │
│              ┌───────▼────────┐             │
│              │ Protocol Agent │             │
│              │ (synthesizes   │             │
│              │  all outputs)  │             │
│              └────────────────┘             │
└─────────────────────────────────────────────┘
                      │
                      ▼
              Shared Memory Store
         (JSON / SQLite / vector DB)
```

---

## Layer 1 — Deterministic Layer

### 1a. Log Form + Database
**What it does:** Captures structured daily entries via form UI or CLI.
**Schema (per event record):**
- `timestamp`, `migraine_occurred` (bool), `pain_level` (1–10)
- `pain_location`, `pain_quality`, `duration_hours`
- `prodrome_symptoms[]`, `postdrome_symptoms[]`
- `foods[]`, `hydration_oz`, `caffeine_mg`, `alcohol_units`
- `supplements[]`, `medications[]`
- `sleep_hours`, `sleep_quality` (1–10), `bedtime`, `wake_time`
- `stress_level` (1–10), `stress_source`
- `chemical_exposure[]`, `fragrance_exposure` (bool)
- `exercise_type`, `exercise_minutes`
- `screen_hours`, `neck_tension` (1–10)
- `menstrual_cycle_day`, `hormonal_notes`
- `bowel_quality` (Bristol 1–7), `bloating` (bool)
- `relief_methods[]`, `relief_effectiveness` (1–10)
- `notes` (free text — passed to Intake Agent for follow-up)

**Tech:** SQLite (local, private) or Postgres. No cloud required initially.

### 1b. Weather & AQI Fetcher
**What it does:** On each log entry, auto-fetches and appends:
- Barometric pressure (current + 24h delta)
- Temperature, humidity
- AQI index and dominant pollutant
- Pollen count (if available)

**Source APIs:** OpenWeatherMap, AirNow (EPA), Tomorrow.io
**Trigger:** Runs automatically when a log entry is saved.

### 1c. Rules Engine
Hard-coded rules — no LLM involved.

| Rule | Condition | Action |
|------|-----------|--------|
| MOH Alert | Triptan or NSAID use ≥ 10 days in rolling 30-day window | Immediate warning displayed |
| Red-Flag Checker | Any of: "worst headache ever", fever + stiff neck, neurological deficit, new pattern after age 50 | Urgent: see a doctor now |
| Streak Counter | Days since last migraine_occurred = true | Display streak on dashboard |
| Trigger Frequency | Count occurrences of each trigger field across all events | Weekly summary report |
| Pain Trend | 7-day and 30-day rolling average pain level | Trend chart on dashboard |

---

## Layer 2 — AI Agent Layer

### Shared Memory Store
All agents read from and write to a shared JSON memory file (or SQLite table).

**Memory keys:**
```json
{
  "confirmed_triggers": [],
  "suspected_triggers": [],
  "ruled_out_triggers": [],
  "current_root_cause_hypothesis": "",
  "medical_frameworks_applied": [],
  "research_findings": [],
  "current_protocol": {},
  "protocol_version": 1,
  "migraine_subtype": "",
  "last_pattern_run": "",
  "last_research_run": "",
  "session_history_summary": ""
}
```

### Agent Descriptions

| Agent | Input | Output | Invoked When |
|-------|-------|--------|--------------|
| **Orchestrator** | Raw user message | Routing decision + context packet | Every session |
| **Intake Agent** | Saved log record + free-text notes | Probing follow-up questions | After every log entry |
| **Pattern Agent** | Last N log records + memory store | Updated trigger list + pattern summary | Every 3–5 new events |
| **Research Agent** | Specific trigger or mechanism query | Cited research findings | On-demand or post-pattern |
| **Root Cause Agent** | Pattern summary + research findings + memory | Updated root cause hypothesis | Weekly or on milestone |
| **Protocol Agent** | Root cause hypothesis + all memory | Ranked, personalized alleviation plan | After root cause update |

---

## Data Flow (Single Session Example)

```
1. User opens app → Orchestrator reads memory store, determines session intent

2. User fills log form → Deterministic layer saves record, fetches weather/AQI,
   runs rules engine (MOH check, red-flag check, streak update)

3. Rules engine fires MOH alert? → Display immediately, skip to step 6

4. Orchestrator passes log record to Intake Agent → Agent asks 1–2 probing
   follow-up questions → User answers → Appended to record

5. If N events threshold met → Pattern Agent runs on full log history →
   Updates memory store (confirmed_triggers, pattern summary)

6. If new pattern found → Research Agent queried for relevant mechanism →
   Findings added to memory store

7. Weekly or on user request → Root Cause Agent synthesizes all memory →
   Produces updated hypothesis

8. Root cause updated → Protocol Agent generates new ranked protocol →
   Stored in memory, displayed to user

9. Session summary written back to memory store for next session continuity
```

---

## File Structure

```
MigraineTackler/
├── ARCHITECTURE.md              ← this file
├── agents/
│   ├── 00_orchestrator.md       ← Orchestrator prompt
│   ├── 01_intake_agent.md       ← Intake Agent prompt
│   ├── 02_pattern_agent.md      ← Pattern Agent prompt
│   ├── 03_research_agent.md     ← Research Agent prompt
│   ├── 04_root_cause_agent.md   ← Root Cause Agent prompt
│   └── 05_protocol_agent.md     ← Protocol Agent prompt
├── rules/
│   └── rules_engine.md          ← Deterministic rules spec
└── schema/
    └── log_schema.md            ← Full log record schema
```

---

## Technology Recommendations (When Building)

| Component | Recommended Stack |
|-----------|------------------|
| Backend | Python + FastAPI |
| Database | SQLite (local) → Postgres (if cloud) |
| AI Agents | Claude API (claude-sonnet-4-6) via Anthropic SDK |
| Agent Memory | JSON file → SQLite → pgvector (as complexity grows) |
| Weather API | OpenWeatherMap free tier |
| AQI API | AirNow EPA (free, US-based) |
| Frontend | Simple: Streamlit. Full: React + TypeScript |
| Scheduling | APScheduler (weather fetch) or cron |
