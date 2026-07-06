import logging
import threading
import time

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph
from sqlalchemy.engine import make_url

from app.config import settings
from app.graph.nodes import intake, lifestyle_audit, pattern, protocol, research, root_cause
from app.graph.state import MigraineState


def _psycopg_connect(database_url: str, autocommit: bool = False) -> psycopg.Connection:
    """Parse DB URL via SQLAlchemy (handles special chars in passwords) and connect."""
    u = make_url(database_url)
    return psycopg.connect(
        host=u.host,
        port=u.port or 5432,
        dbname=u.database,
        user=u.username,
        password=u.password,
        autocommit=autocommit,
    )


# ── Intent → node routing ─────────────────────────────────────────────────────

_END: str = END  # langgraph END constant typed as str for mypy


def route_intent(state: MigraineState) -> str:
    intent: str = state.get("intent", "")

    if state.get("moh_alert_active") or state.get("red_flag_active"):
        return _END

    routing: dict[str, str] = {
        "log_entry": "intake",
        "pattern_review": "pattern",
        "research_request": "research",
        "root_cause_review": "root_cause",
        "protocol_review": "protocol",
        "lifestyle_audit": "lifestyle_audit",
    }
    return routing.get(intent, _END)


def should_run_pattern(state: MigraineState) -> str:
    stats = state.get("deterministic_stats", {})
    total = stats.get("total_events_logged", 0)
    if total >= 2 and total % 2 == 0:
        return "pattern"
    return _END


def should_run_research(state: MigraineState) -> str:
    confirmed = set(state.get("confirmed_triggers", []))
    seen = set(state.get("research_triggers_seen", []))
    if confirmed - seen:
        return "research"
    return _END


def should_run_protocol(state: MigraineState) -> str:
    return "protocol" if state.get("protocol_refresh_recommended") else _END


def should_run_root_cause(state: MigraineState) -> str:
    confirmed = set(state.get("confirmed_triggers", []))
    suspected = set(state.get("suspected_triggers", []))
    current = confirmed | suspected
    seen = set(state.get("root_cause_triggers_seen", []))
    if current and current != seen:
        return "root_cause"
    return _END


# ── Graph definition ──────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    graph = StateGraph(MigraineState)

    graph.add_node("intake", intake.run)
    graph.add_node("pattern", pattern.run)
    graph.add_node("research", research.run)
    graph.add_node("root_cause", root_cause.run)
    graph.add_node("protocol", protocol.run)
    graph.add_node("lifestyle_audit", lifestyle_audit.run)

    graph.set_conditional_entry_point(
        route_intent,
        {
            "intake": "intake",
            "pattern": "pattern",
            "research": "research",
            "root_cause": "root_cause",
            "protocol": "protocol",
            "lifestyle_audit": "lifestyle_audit",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "intake",
        should_run_pattern,
        {"pattern": "pattern", END: END},
    )

    graph.add_conditional_edges(
        "pattern",
        should_run_root_cause,
        {"root_cause": "root_cause", END: END},
    )

    graph.add_edge("research", END)
    graph.add_conditional_edges(
        "root_cause",
        should_run_research,
        {"research": "research", END: END},
    )
    graph.add_edge("protocol", END)
    graph.add_conditional_edges(
        "lifestyle_audit",
        should_run_protocol,
        {"protocol": "protocol", END: END},
    )

    return graph


def compile_graph():
    graph = build_graph()
    conn = _psycopg_connect(settings.database_url, autocommit=True)
    conn.execute("SET statement_timeout = 0")  # allow CREATE INDEX CONCURRENTLY to finish
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
    return graph.compile(checkpointer=checkpointer)


# Lazy singleton — thread-safe; warmup thread and request handler may race on first call.
_graph = None
_graph_lock = threading.Lock()
_logger = logging.getLogger(__name__)


def get_graph():
    global _graph
    if _graph is None:
        with _graph_lock:
            if _graph is None:
                _logger.info("graph_compile_start")
                t = time.monotonic()
                try:
                    _graph = compile_graph()
                    _logger.info(
                        "graph_compile_success",
                        extra={"duration_ms": round((time.monotonic() - t) * 1000)},
                    )
                except Exception:
                    _logger.exception(
                        "graph_compile_failed",
                        extra={"duration_ms": round((time.monotonic() - t) * 1000)},
                    )
                    raise
    return _graph


def is_graph_ready() -> bool:
    return _graph is not None
