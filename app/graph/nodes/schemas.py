"""
Pydantic output schemas for LangChain structured output.

Each schema maps to one agent node. Using llm.with_structured_output(Model)
guarantees the LLM returns valid JSON matching the schema — no regex parsing,
no silent failures on malformed output.
"""

from typing import Literal
from pydantic import BaseModel, Field


class PatternOutput(BaseModel):
    pattern_summary: str = Field(description="2-4 sentences, conversational and clinical. Lead with the most actionable finding. If insufficient data, say so clearly.")
    confirmed_triggers: list[str] = Field(default_factory=list, description="Triggers appearing before ≥70% of migraine days. Min 2 occurrences. Empty list if insufficient data.")
    suspected_triggers: list[str] = Field(default_factory=list, description="Triggers appearing before 40-69% of migraine days. Empty list if insufficient data.")
    unknown_trigger_candidates: list[str] = Field(default_factory=list, description="Items from novel_exposures appearing on ≥2 migraine days only. Never include standard trigger list items.")
    key_insight: str = Field(default="", description="Single most important finding in one sentence.")
    trend: Literal["improving", "worsening", "stable"] = Field(default="stable")


class EvidenceItem(BaseModel):
    claim: str = Field(description="Specific claim this evidence supports.")
    source: str = Field(description="Exact reference in the data, e.g. '6 of 8 migraine days', 'pattern summary'.")
    source_type: Literal["log_history", "onboarding", "weather", "agent_memory", "stats"]


class RootCauseOutput(BaseModel):
    root_cause_summary: str = Field(description="3-5 sentences explaining the hypothesis and reasoning in plain language. Name the mechanism, not just the trigger. If data is insufficient, say so.")
    hypothesis: str = Field(default="", description="One clear sentence stating the most likely root cause.")
    migraine_subtype: Literal[
        "hormonal_migraine",
        "sleep_disorder_migraine",
        "stress_tension_migraine",
        "environmental_migraine",
        "dietary_migraine",
        "moh_migraine",
        "chronic_migraine",
        "mixed_trigger_migraine",
    ] = Field(default="mixed_trigger_migraine")
    confidence: Literal["low", "medium", "high"] = Field(default="low")
    reasoning: str = Field(default="", description="2-3 sentences explaining what data supports this hypothesis.")
    evidence: list[EvidenceItem] = Field(default_factory=list)
    what_to_watch: list[str] = Field(default_factory=list, description="Next data points or patterns to confirm or rule out this hypothesis.")


class ResearchOutput(BaseModel):
    research_findings: str = Field(description="3-6 sentence synthesized answer with inline citations as [1], [KB-1], etc.")
    topic: str = Field(default="", description="Short topic label, 3-5 words.")
    key_finding: str = Field(default="", description="One sentence summary of the most important finding.")
    evidence_quality: Literal["well-established", "emerging", "anecdotal"] = Field(default="emerging")
    medical_framework: str = Field(default="", description="Name of the relevant clinical framework or pathway, if any.")
    action: str = Field(default="", description="One concrete thing the user can log or try.")
    cited_indices: list[int] = Field(default_factory=list, description="1-based indices of cited PubMed abstracts.")
    cited_kb_indices: list[int] = Field(default_factory=list, description="1-based indices of cited knowledge base passages.")


class ProtocolItemOutput(BaseModel):
    intervention: str
    tier: int = Field(ge=1, le=4)
    dose_or_detail: str
    rationale: str
    what_to_log: str
    assessment_weeks: int = Field(ge=1, le=12)


class ProtocolOutput(BaseModel):
    protocol_summary: str = Field(description="3-5 sentences explaining the overall strategy — what is being targeted and why, in plain language the user can act on today.")
    active_tier: int = Field(default=1, ge=1, le=4)
    active_items: list[ProtocolItemOutput] = Field(default_factory=list, description="Interventions to start now, max 4-5.")
    on_deck: list[ProtocolItemOutput] = Field(default_factory=list, description="Interventions to consider if active_items don't produce results in 8 weeks.")
