# Context Builder Specification

## Purpose
The Context Builder is a deterministic function — no AI involved — that runs
before every agent call. It assembles the minimum context packet each agent
needs to do its job, pulling from the database and memory store.

The rule: **send summaries by default, fetch raw only when the agent's task
requires verification against specific historical values.**

---

## Shared Base Context (Sent to Every Agent)

Every agent call includes this base payload. It is always compacted — never
raw logs.

```json
{
  "base": {
    "memory_store": {
      "confirmed_triggers": [],
      "suspected_triggers": [],
      "ruled_out_triggers": [],
      "current_root_cause_hypothesis": "",
      "migraine_subtype": "",
      "medical_frameworks_applied": [],
      "research_findings": [],
      "current_protocol": {},
      "protocol_version": 0,
      "session_history_summary": ""
    },
    "deterministic_stats": {
      "migraine_free_streak_days": 0,
      "migraine_days_last_30d": 0,
      "avg_pain_level_last_30d": 0.0,
      "pain_trend_direction": "improving | worsening | stable",
      "moh_status": {
        "triptan_days_last_30d": 0,
        "nsaid_days_last_30d": 0,
        "alert_active": false
      },
      "top_5_triggers_last_30d": [],
      "total_events_logged": 0
    },
    "current_weather_snapshot": {
      "timestamp": "",
      "barometric_pressure_hpa": 0,
      "pressure_delta_24h": 0,
      "temperature_f": 0,
      "humidity_pct": 0,
      "aqi": 0,
      "dominant_pollutant": ""
    }
  }
}
```

**Estimated token cost:** ~400–600 tokens per call. Fixed overhead.

---

## Per-Agent Context Packets

Each agent receives the base context above plus the agent-specific additions
defined below.

---

### Orchestrator

**Intent:** Classify user intent, route to correct agent, assemble context.

**Additional context:**
```json
{
  "agent_specific": {
    "raw_user_message": "",
    "last_5_session_intents": []
  }
}
```

**Raw data fetched:** None. The Orchestrator works from memory and stats only.

**When Orchestrator fetches raw for downstream agent:** See each agent spec below.
The Orchestrator reads those fetch conditions and queries the DB before passing
the packet.

**Estimated total tokens:** ~500–700

---

### Intake Agent

**Intent:** Read a freshly saved log, ask 1–2 targeted follow-up questions.

**Additional context:**
```json
{
  "agent_specific": {
    "current_log_record": {
      "-- full structured log record for this session --": true
    },
    "prior_intake_notes_last_3_sessions": [
      {
        "date": "",
        "follow_up_question": "",
        "user_answer": ""
      }
    ]
  }
}
```

**Raw data fetched:** The current session's log record — always full fidelity.
This is the one case where the full raw record is sent because it was just
captured and hasn't been summarized yet.

**Prior sessions:** Only last 3 sessions' intake notes, not all history.
The Intake Agent needs recent context to avoid asking the same follow-up twice,
but does not need full history.

**Raw fetch trigger:** Always (current session record).

**Estimated total tokens:** ~800–1,200 depending on log fullness.

---

### Pattern Agent

**Intent:** Find non-obvious correlations across N log events.

**Additional context:**
```json
{
  "agent_specific": {
    "log_summary_batch": [
      {
        "date": "",
        "migraine_occurred": false,
        "pain_level": 0,
        "pain_location": "",
        "top_triggers_present": [],
        "sleep_hours": 0,
        "sleep_quality": 0,
        "stress_level": 0,
        "menstrual_cycle_day": null,
        "medications_taken": [],
        "supplements_taken": [],
        "relief_effectiveness": 0,
        "weather_pressure_delta_24h": 0,
        "aqi": 0,
        "intake_notes": ""
      }
    ],
    "batch_size": 0,
    "batch_date_range": {
      "from": "",
      "to": ""
    },
    "prior_pattern_summary": ""
  }
}
```

**What is compacted:** Each log record is reduced to ~15 key fields. Free-text
fields (raw notes, full food lists) are replaced by the Intake Agent's
structured follow-up answer. Full weather API payloads are reduced to
pressure_delta_24h and AQI only.

**What is NOT sent:** Full ingredient lists, full supplement details, raw
weather API responses, verbose free-text notes.

**Batch size rules:**
- Default: last 20 events
- Minimum to run: 5 events (Pattern Agent is blocked below this)
- Maximum per call: 50 events (split into two calls if exceeded)

**Raw fetch trigger:** Only when Orchestrator detects a "re-analysis under
new hypothesis" intent — e.g., user says "can we look at this differently"
or Root Cause Agent has updated the hypothesis since the last pattern run.
In that case, fetch full records for the relevant date range.

**Estimated total tokens (20 events):** ~2,000–3,500

---

### Research Agent

**Intent:** Synthesize external sources on a specific trigger or mechanism.

**Additional context:**
```json
{
  "agent_specific": {
    "research_query": "",
    "query_type": "trigger | mechanism | supplement | treatment | tcm | ayurveda",
    "user_data_relevant_to_query": {
      "related_confirmed_triggers": [],
      "related_pattern_findings": "",
      "events_where_this_trigger_present": 0,
      "migraine_correlation_pct": 0
    },
    "prior_research_on_this_topic": ""
  }
}
```

**What is compacted:** The Research Agent does not receive log records. It
receives only the memory store and a distilled summary of how this trigger
appears in the user's data (count, correlation percentage, pattern note).

**Why:** The Research Agent's job is external synthesis, not personal data
analysis. Sending it 30 log records adds noise and cost.

**Raw fetch trigger:** Never for log records. The Orchestrator extracts the
relevant stats from the DB deterministically and passes them as the
`user_data_relevant_to_query` fields above.

**Exception — threshold verification:** If the research query involves a
specific quantitative threshold (e.g., "is my barometric pressure sensitivity
matching the 5 hPa clinical threshold?"), the Orchestrator fetches the raw
weather deltas for all migraine events and passes them as a simple array:
```json
{ "pressure_deltas_on_migraine_days": [4.2, 6.1, 3.8, 7.0, 5.5] }
```
This is the minimal raw slice needed to answer the question.

**Estimated total tokens:** ~700–1,000

---

### Root Cause Agent

**Intent:** Deep synthesis across all frameworks to update the root cause
hypothesis.

**Additional context:**
```json
{
  "agent_specific": {
    "pattern_summary": "",
    "accumulated_research_findings": [],
    "anomaly_log": {
      "migraine_free_periods": [
        {
          "date_range": "",
          "duration_days": 0,
          "notable_differences_from_baseline": ""
        }
      ],
      "migraine_despite_no_triggers": [
        {
          "date": "",
          "intake_notes": ""
        }
      ]
    },
    "current_hypothesis_version": 0,
    "hypothesis_changelog": []
  }
}
```

**What is compacted:** The Root Cause Agent never receives raw log records
by default. It works from the Pattern Agent's structured summary and the
Research Agent's findings — both of which are already synthesized.

**Raw fetch trigger — two conditions:**

1. **Anomaly investigation:** If there are migraine-free periods of 5+ days
   or migraines with zero logged triggers, the Orchestrator fetches full raw
   records for those specific events only. These are the exceptions that
   challenge the hypothesis and are most valuable for root cause reasoning.

2. **Free-text and intake notes review:** When the Root Cause Agent explicitly
   signals it needs the user's verbatim notes (e.g., for a somatic or
   emotional pattern that doesn't appear in structured fields), the
   Orchestrator fetches all intake follow-up answers chronologically as a
   plain text block.

**Estimated total tokens (no raw fetch):** ~1,500–2,500
**Estimated total tokens (with anomaly raw fetch):** ~2,500–4,000

---

### Protocol Agent

**Intent:** Build and update the personalized alleviation protocol.

**Additional context:**
```json
{
  "agent_specific": {
    "root_cause_hypothesis": "",
    "hypothesis_layer_1_triggers": [],
    "hypothesis_layer_2_vulnerabilities": [],
    "hypothesis_layer_3_root_causes": [],
    "protocol_history": [
      {
        "version": 0,
        "date": "",
        "active_items": [],
        "outcome_notes": ""
      }
    ],
    "what_has_been_tried": [
      {
        "intervention": "",
        "duration_weeks": 0,
        "user_reported_outcome": "",
        "migraine_frequency_change": ""
      }
    ],
    "current_supplement_list": [],
    "current_medication_list": []
  }
}
```

**What is compacted:** Protocol Agent works almost entirely from the memory
store and root cause hypothesis. It does not need log records.

**Raw fetch trigger — one condition:**

**Streak analysis for protocol validation:** When the Protocol Agent needs to
assess whether an active recommendation is working, the Orchestrator fetches
a before/after summary: migraine frequency and average pain level for the
4-week period before the intervention started vs. the 4-week period after.
This is a deterministic aggregation query, not raw record retrieval.

```json
{
  "intervention_effectiveness": {
    "intervention": "magnesium glycinate 400mg",
    "started": "2025-06-01",
    "pre_period": {
      "migraine_days": 8,
      "avg_pain": 6.4
    },
    "post_period": {
      "migraine_days": 5,
      "avg_pain": 5.1
    }
  }
}
```

**Estimated total tokens:** ~1,200–2,000

---

## Raw Fetch Decision Table

Summary of when the Orchestrator fetches raw records vs. uses summaries.

| Agent | Default | Raw Fetch Condition | What Is Fetched |
|-------|---------|---------------------|-----------------|
| Orchestrator | Summary | Never | — |
| Intake Agent | Full current record | Always (current session only) | Single record, all fields |
| Pattern Agent | Compacted batch | Re-analysis under new hypothesis | Full records, specific date range |
| Research Agent | Stats only | Threshold verification query | Single field array (e.g., pressure deltas) |
| Root Cause Agent | Pattern + research summaries | Anomaly events OR verbatim notes needed | Specific anomalous records OR intake notes block |
| Protocol Agent | Memory + hypothesis | Never (uses deterministic aggregation instead) | Aggregated before/after stats |

---

## Token Budget Guidelines

Target total context per agent call (input tokens):

| Agent | Budget | Notes |
|-------|--------|-------|
| Orchestrator | < 1,000 | Lightweight router |
| Intake Agent | < 2,000 | One record + short history |
| Pattern Agent | < 5,000 | 20-event batch; split if more |
| Research Agent | < 2,000 | No log records |
| Root Cause Agent | < 5,000 | Rises with anomaly fetch |
| Protocol Agent | < 3,000 | History-heavy but no logs |

If a call would exceed budget:
1. Trim `session_history_summary` to 3 sentences
2. Reduce log batch size (Pattern Agent)
3. Truncate `hypothesis_changelog` to last 3 versions
4. As a last resort: split into two sequential calls

---

## Context Builder Implementation Notes

The Context Builder is a Python function `build_context(agent_name, session_data)`
that:

1. Always loads base context from memory store + deterministic stats
2. Checks the raw fetch decision table for the given agent
3. Queries the DB for any required raw or aggregated data
4. Assembles the final JSON packet
5. Checks token estimate before returning — logs a warning if over budget

It is called by the Orchestrator immediately before each agent invocation.
It has no LLM calls — it is pure data assembly.
