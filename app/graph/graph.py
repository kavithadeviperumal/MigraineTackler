from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from app.graph.state import MigraineState
from app.graph.nodes import intake, pattern, research, root_cause, protocol
from app.config import settings


# ── Intent → node routing ─────────────────────────────────────────────────────

def route_intent(state: MigraineState) -> str:
    """
    Conditional edge from START. Routes based on the intent field set by the
    Orchestrator before the graph runs.

    Returns the name of the next node.
    """
    intent = state.get("intent", "")

    # Safety: MOH or red-flag alerts short-circuit to END immediately.
    # The alert content is already in state — Streamlit UI renders it.
    if state.get("moh_alert_active") or state.get("red_flag_active"):
        return END

    routing = {
        "log_entry":       "intake",
        "pattern_review":  "pattern",
        "research_request": "research",
        "root_cause_review": "root_cause",
        "protocol_review": "protocol",
    }
    return routing.get(intent, END)


def should_run_pattern(state: MigraineState) -> str:
    """
    After intake completes, check if the Pattern Agent should auto-run.
    Triggers when total_events_logged crosses a multiple of 5.
    """
    stats = state.get("deterministic_stats", {})
    total = stats.get("total_events_logged", 0)
    if total >= 2 and total % 2 == 0:
        return "pattern"
    return END


def should_run_root_cause(state: MigraineState) -> str:
    """
    After pattern completes, check if Root Cause Agent should auto-run.
    Triggers when triggers have been identified but no hypothesis exists yet.
    """
    has_triggers = bool(
        state.get("confirmed_triggers") or state.get("suspected_triggers")
    )
    has_hypothesis = bool(state.get("current_root_cause_hypothesis", "").strip())
    if has_triggers and not has_hypothesis:
        return "root_cause"
    return END


# ── Graph definition ──────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(MigraineState)

    # Register nodes
    graph.add_node("intake",      intake.run)
    graph.add_node("pattern",     pattern.run)
    graph.add_node("research",    research.run)
    graph.add_node("root_cause",  root_cause.run)
    graph.add_node("protocol",    protocol.run)

    # Entry point — Orchestrator sets intent in state before invoking the graph
    graph.set_conditional_entry_point(
        route_intent,
        {
            "intake":      "intake",
            "pattern":     "pattern",
            "research":    "research",
            "root_cause":  "root_cause",
            "protocol":    "protocol",
            END:           END,
        },
    )

    # After intake: maybe auto-trigger pattern analysis
    graph.add_conditional_edges(
        "intake",
        should_run_pattern,
        {"pattern": "pattern", END: END},
    )

    # After pattern: maybe auto-trigger root cause
    graph.add_conditional_edges(
        "pattern",
        should_run_root_cause,
        {"root_cause": "root_cause", END: END},
    )

    # All other nodes terminate the graph
    graph.add_edge("research",   END)
    graph.add_edge("root_cause", END)
    graph.add_edge("protocol",   END)

    return graph


def compile_graph(db_path: str | None = None):
    """
    Compiles the graph with SQLite-backed checkpointing.
    Persists MigraineState across sessions in data/langgraph.db.
    Pass db_path=":memory:" in tests to avoid touching the filesystem.
    """
    import sqlite3 as _sqlite3
    graph = build_graph()
    path = db_path or settings.langgraph_db_path
    conn = _sqlite3.connect(path, check_same_thread=False)
    memory = SqliteSaver(conn)
    return graph.compile(checkpointer=memory)


# Lazy singleton — opened on first call, not at import time.
# This avoids creating data/langgraph.db before the data/ dir exists
# and allows tests to call compile_graph(":memory:") before get_graph().
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        import os
        os.makedirs(os.path.dirname(settings.langgraph_db_path), exist_ok=True)
        _graph = compile_graph()
    return _graph
