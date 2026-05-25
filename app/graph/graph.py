import psycopg
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from app.graph.state import MigraineState
from app.graph.nodes import intake, pattern, research, root_cause, protocol, preventive_care
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
        "preventive_care":    "preventive_care",
    }
    return routing.get(intent, END)


def should_run_pattern(state: MigraineState) -> str:
    stats = state.get("deterministic_stats", {})
    total = stats.get("total_events_logged", 0)
    if total >= 2 and total % 2 == 0:
        return "pattern"
    return END


def should_run_root_cause(state: MigraineState) -> str:
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

    graph.add_node("intake",           intake.run)
    graph.add_node("pattern",          pattern.run)
    graph.add_node("research",         research.run)
    graph.add_node("root_cause",       root_cause.run)
    graph.add_node("protocol",         protocol.run)
    graph.add_node("preventive_care",  preventive_care.run)

    graph.set_conditional_entry_point(
        route_intent,
        {
            "intake":           "intake",
            "pattern":          "pattern",
            "research":         "research",
            "root_cause":       "root_cause",
            "protocol":         "protocol",
            "preventive_care":  "preventive_care",
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

    graph.add_edge("research",        END)
    graph.add_edge("root_cause",      END)
    graph.add_edge("protocol",        END)
    graph.add_edge("preventive_care", END)

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
