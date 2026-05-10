# MigraineTackler — Production Readiness Worklist

**Audit date:** 2026-05-10  
**Overall score:** 5.3/10 — MVP-ready for internal testing; NOT ready for production users

---

## Critical (fix before any public access)

- [ ] **Rotate exposed Google API key** — old key `AIzaSyCOShP...` was visible; rotate at aistudio.google.com → Get API key
- [ ] **Add `.env` to `.gitignore`** — ✅ already done; confirm before first `git init`
- [ ] **Enforce HTTPS** — configure reverse proxy (nginx, Caddy, CloudFront) to terminate TLS; never run on plain HTTP with health data
- [ ] **Set up database backups** — SQLite files in `data/` have no backup; add daily backup to S3/GCS and test restore
- [ ] **Add LLM error handling** — all 5 nodes in `app/graph/nodes/` call `.invoke()` with no try/except; if Gemini is down the graph crashes
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
- [ ] Wrap all `.invoke()` calls in try/except with fallback response strings in each node
- [ ] Add configurable timeout on LLM calls (httpx timeout or `asyncio.wait_for`)
- [ ] Implement prompt caching — patient context is re-sent on every call; 3–5x cost reduction possible

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
| Documentation | 7/10 | Architecture clear; no runbooks or deploy guide |
