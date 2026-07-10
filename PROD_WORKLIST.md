# MigraineTackler — Production Readiness Worklist

**Audit date:** 2026-05-10  
**Overall score:** 5.3/10 — MVP-ready for internal testing; NOT ready for production users

---

## Critical (fix before any public access)

- [ ] **Rotate exposed Google API key** — old key `AIzaSyCOShP...` was visible; rotate at aistudio.google.com → Get API key
- [ ] **Add `.env` to `.gitignore`** — ✅ already done; confirm before first `git init`
- [ ] **Enforce HTTPS** — configure reverse proxy (nginx, Caddy, CloudFront) to terminate TLS; never run on plain HTTP with health data
- [ ] **Set up database backups** — SQLite files in `data/` have no backup; add daily backup to S3/GCS and test restore
- [x] **Add LLM error handling** — `intake.py` and `lifestyle_audit.py` now have `@retry` + try/except fallback; `pattern`, `root_cause`, `research`, `protocol` were already protected
- [ ] **Clinical review of red-flag rules** — `app/rules/rules_engine.py` makes medical safety calls; get written sign-off before real users

---

## Phase 1 — High priority (before sharing with any users)

### Security
- [ ] Move secrets to a secrets manager (AWS Secrets Manager, Parameter Store, or HashiCorp Vault) — no plaintext keys in `.env` on servers
- [ ] Add CORS middleware to `app/api/main.py` — currently any cross-origin request is blocked or uncontrolled
- [ ] Add rate limiting on `/auth/login` and `/auth/register` (use `slowapi`) — brute-force risk
- [ ] Remove or gate the `/reset` endpoint behind an admin role
- [ ] Disable `/docs` and `/redoc` in production (`app = FastAPI(docs_url=None, redoc_url=None)` behind a flag)
- [ ] Add password strength requirements on register (min length, complexity)
- [ ] Implement token refresh + logout (invalidate JWTs server-side or shorten expiry + use refresh tokens)

### Database
- [ ] Migrate from SQLite to PostgreSQL — SQLite caps at ~10 concurrent users
- [ ] Set up Alembic for schema migrations — current approach uses raw SQL ALTER TABLE in `app/database.py:_migrate()`
- [ ] Wrap multi-step DB operations in explicit transactions (log save + safety check should be atomic)

### AI / LangGraph
- [x] Wrap all `.invoke()` calls in try/except with fallback response strings in each node
- [ ] Add configurable timeout on LLM calls (httpx timeout or `asyncio.wait_for`)
- [ ] Implement prompt caching — patient context is re-sent on every call; 3–5x cost reduction possible
- [ ] **Intake agent asks follow-up questions on migraine days** — violates the 30-second SOS promise; on `migraine_occurred = True` the agent should acknowledge and exit, write a `follow_up_pending` flag to state, and pick it up on the next migraine-free session instead (`app/graph/nodes/intake.py`)
- [ ] **No centralized context builder** — `architecture/context_builder.md` specifies a shared `build_context(agent_name, session_data)` function with per-agent token budgets and a fetch decision table; actual implementation has a private `_build_context` function in each node file with no shared enforcement; refactor into a shared module under `app/graph/context_builder.py`

### Spec/Implementation Gaps (architecture/context_builder.md vs. actual nodes)

**Structural**
- [ ] **No Orchestrator node exists** — spec describes an Orchestrator LLM agent that routes intent and assembles context packets for downstream agents; actual implementation uses pure Python conditional edge functions (`route_intent`, `should_run_pattern`, etc. in `app/graph/graph.py`) — no LLM involved in routing; update `architecture/context_builder.md` to reflect this or build toward the spec
- [ ] **No token budget enforcement** — spec defines per-agent token ceilings (Orchestrator <1k, Pattern <5k, etc.) with compaction fallback rules; no node measures or enforces token counts before invoking the LLM

**Pattern Agent** (`app/graph/nodes/pattern.py`)
- [ ] **Batch size exceeds spec** — spec: default 20 events, max 50, split into two calls if exceeded; actual: `list_recent(limit=60, since=60 days)` fetches up to 60 records with no split logic
- [ ] **Raw free-text notes sent to LLM** — spec: free-text `notes` field should be replaced by the Intake Agent's structured follow-up answer before passing to Pattern Agent; actual: raw `notes` string is included in `_format_entries` output
- [ ] **No `prior_pattern_summary` in context** — spec includes the previous pattern run's summary so the agent can build incrementally; actual: `_build_context` starts fresh each run with no prior summary

**Protocol Agent** (`app/graph/nodes/protocol.py`)
- [ ] **No before/after intervention effectiveness tracking** — spec: Orchestrator fetches a 4-week pre/post aggregation (migraine days + avg pain) for each active intervention to assess whether it's working; actual: `_build_context` sends only current 30-day stats with no historical comparison
- [ ] **No protocol history in context** — spec: `protocol_history` list with version, date, active items, and outcome notes for each prior version; actual: only the current protocol JSON is sent — the agent cannot reason about what has already been tried and failed
- [ ] **No `what_has_been_tried` tracking** — spec: structured list of past interventions with duration, user-reported outcome, and migraine frequency change; this field does not exist in state or context assembly

**Root Cause Agent** (`app/graph/nodes/root_cause.py`)
- [ ] **No anomaly log passed** — spec: Orchestrator detects migraine-free periods ≥5 days and zero-trigger migraine events and passes them as an `anomaly_log`; actual: `_build_context` has no anomaly detection or conditional DB fetch for outlier events
- [ ] **No hypothesis changelog** — spec: `hypothesis_changelog` list of prior hypotheses with version and date; actual: `MigraineState` only stores `current_root_cause_hypothesis` as a single string — prior hypotheses are overwritten and lost
- [x] **Pipeline ordering: Root Cause before Research is intentional** — `pattern → root_cause → research` is the correct order once RAG sources are separated; Root Cause draws from `doctor_note + clinical_guideline` (personalized hypothesis grounded in this user's context first), Research then draws from `pubmed + semantic_scholar` (external validation of that hypothesis); order should be documented as a deliberate design decision, not a gap
- [ ] **RAG has no source type filter** — `retrieve_relevant()` in `app/services/rag_service.py` queries all source types (`pubmed`, `semantic_scholar`, `clinical_guideline`, `doctor_note`) with equal weight; Root Cause Agent should draw only from `doctor_note` + `clinical_guideline` (personalized synthesis), Research Agent should draw only from `pubmed` + `semantic_scholar` (external evidence); fix: add `source_types: list[str] | None = None` parameter to `retrieve_relevant` with a SQL `source_type = ANY(:source_types)` filter, then pass the filter from each node
- [ ] **No staleness protection in RAG retrieval** — `retrieve_relevant()` has no date filter; `KnowledgeChunk` has `created_at` but it is never used in the query; old doctor notes or superseded clinical guidelines surface if semantically similar; fix: add `max_age_days: int | None = None` parameter to `retrieve_relevant` with SQL `AND created_at >= now() - interval` filter; alternatively add an `archived` boolean to `KnowledgeChunk` so users can mark superseded documents without deleting them (`app/services/rag_service.py`, `app/models/knowledge_chunk.py`)
- [ ] **Research RAG query not personalized to user symptom profile** — `_extract_question` in `app/graph/nodes/research.py` builds the query from new trigger names only; user context (migraine subtype, full confirmed trigger list, current hypothesis) is passed to the LLM in `_build_context` for interpretation but does not influence which passages are retrieved from the vector DB; two users with the same new trigger get identical RAG results regardless of their differing subtypes; fix: enrich the embedding query before retrieval — `query = f"{question} {migraine_subtype} {' '.join(confirmed_triggers)}"` — so vector search is anchored to this user's specific profile

### Frontend
- [ ] Make `API_BASE` configurable via env var in `streamlit_app.py` — currently hardcoded to `http://localhost:8000`
- [ ] Handle JWT expiry gracefully — show re-login prompt instead of erroring mid-flow

---

## Phase 2 — Production hardening (before scaling)

### Deployment
- [ ] Write `Dockerfile` for FastAPI app
- [ ] Write `docker-compose.yml` (app + postgres + optional redis)
- [ ] Add `.dockerignore`
- [ ] Add environment-specific config (dev / staging / prod) — use `APP_ENV` flag in `app/config.py`
- [ ] Add `/health` endpoint returning DB connectivity + version
- [ ] Add graceful shutdown handling (SIGTERM → drain requests)

### CI/CD
- [ ] Set up GitHub Actions: run `pytest` + lint on every PR
- [ ] Add pre-commit hooks (ruff, black, secrets scanner)
- [ ] Add `pytest-cov` with minimum coverage gate (target: 70%)

### Observability
- [ ] Switch to structured JSON logging (use `structlog` or `python-json-logger`)
- [ ] Integrate Sentry for error tracking (free tier covers this project's scale)
- [ ] Add request/response logging middleware to FastAPI
- [ ] Log all safety rule triggers (MOH, red-flag) to a separate audit table
- [ ] Add `/metrics` endpoint (Prometheus-compatible) for response time, error rate

### Testing
- [ ] Add integration tests: full flow (register → log → analyze)
- [ ] Add auth tests: expired token, invalid token, wrong password
- [ ] Add LangGraph node tests with mocked LLM responses
- [ ] Add load tests (locust or k6) simulating 10+ concurrent users

---

## Phase 3 — Scale & polish (ongoing)

- [ ] Deploy to managed cloud (Cloud Run, ECS Fargate, or Railway)
- [ ] Set up alerting (CloudWatch, Datadog, or Grafana Cloud)
- [ ] Mobile-responsive UI — Streamlit columns break on small screens; consider React frontend
- [ ] Offline support — cache last analysis result locally; sync on reconnect
- [ ] Session management — auto-refresh tokens; show session expiry warning
- [ ] Audit trail — immutable log of all safety rule triggers for compliance

---

## Scores by area

| Area | Score | Key gap |
|---|---|---|
| API Design | 7/10 | Missing CORS, versioning, docs security |
| AI / LangGraph | 7/10 | No error handling, no cost control |
| Data Model | 8/10 | Strong schema; weak migration strategy |
| Rules Engine | 8/10 | Good logic; no audit trail, no clinical review |
| Security | 3/10 | JWT + hashing OK; exposed keys, no HTTPS |
| Logging / Monitoring | 2/10 | Minimal; not structured; no observability |
| Testing | 4/10 | Basic coverage; missing integration + auth tests |
| Deployment | 1/10 | No Docker, CI/CD, Postgres, or backups |
| Frontend | 6/10 | Feature-complete; poor mobile UX, no offline |
| Documentation | 5/10 | `architecture/context_builder.md` spec does not match implementation; no runbooks or deploy guide |
