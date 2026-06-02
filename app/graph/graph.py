import psycopg
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from app.graph.state import MigraineState
from app.graph.nodes import intake, pattern, research, root_cause, protocol, lifestyle_audit
from app.config import settings


# ── Intent → node routing ─────────────────────────────────────────────────────

def route_intent(state: MigraineState) -> str:
    intent = state.get("intent", "")

    if state.get("moh_alert_active") or state.get("red_flag_active"):
        return END

    routing = {
        "log_entry":          "intake",
        "pattern_review":     "pattern",
        "research_request":   "research",
        "root_cause_review":  "root_cause",
        "protocol_review":    "protocol",
        "lifestyle_audit":    "lifestyle_audit",
    }
    return routing.get(intent, END)


def should_run_pattern(state: MigraineState) -> str:
    stats = state.get("deterministic_stats", {})
    total = stats.get("total_events_logged", 0)
    if total >= 2 and total % 2 == 0:
        return "pattern"
    return END


def should_run_research(state: MigraineState) -> str:
    confirmed = set(state.get("confirmed_triggers", []))
    seen = set(state.get("research_triggers_seen", []))
    if confirmed - seen:
        return "research"
    return END


def should_run_protocol(state: MigraineState) -> str:
    return "protocol" if state.get("protocol_refresh_recommended") else END


def should_run_root_cause(state: MigraineState) -> str:
    confirmed = set(state.get("confirmed_triggers", []))
    suspected = set(state.get("suspected_triggers", []))
    current = confirmed | suspected
    seen = set(state.get("root_cause_triggers_seen", []))
    if current and current != seen:
        return "root_cause"
    return END


# ── Graph definition ──────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(MigraineState)

    graph.add_node("intake",           intake.run)
    graph.add_node("pattern",          pattern.run)
    graph.add_node("research",         research.run)
    graph.add_node("root_cause",       root_cause.run)
    graph.add_node("protocol",         protocol.run)
    graph.add_node("lifestyle_audit", lifestyle_audit.run)

    graph.set_conditional_entry_point(
        route_intent,
        {
            "intake":           "intake",
            "pattern":          "pattern",
            "research":         "research",
            "root_cause":       "root_cause",
            "protocol":         "protocol",
            "lifestyle_audit":  "lifestyle_audit",
            END:                END,
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

    graph.add_edge("research",         END)
    graph.add_conditional_edges(
        "root_cause",
        should_run_research,
        {"research": "research", END: END},
    )
    graph.add_edge("protocol",        END)
    graph.add_conditional_edges(
        "lifestyle_audit",
        should_run_protocol,
        {"protocol": "protocol", END: END},
    )

    return graph


def compile_graph():
    graph = build_graph()
    conn = psycopg.connect(settings.database_url)
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
    return graph.compile(checkpointer=checkpointer)


# Lazy singleton — opened on first call, not at import time.
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = compile_graph()
    return _graph
