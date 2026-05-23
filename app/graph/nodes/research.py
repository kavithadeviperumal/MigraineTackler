import json
import re
import httpx
from datetime import date

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.graph.state import MigraineState
from app.config import settings

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=settings.google_api_key,
    max_tokens=2048,
)

SYSTEM_PROMPT = """\
You are the Research Agent for MigraineTackler. The user has asked a research question about \
migraines, triggers, treatments, or related physiology. Your job is to provide a clear, \
evidence-based answer grounded in established medical literature.

You are a knowledgeable medical researcher. You do not diagnose or prescribe. \
You explain mechanisms, summarize evidence, and help the user understand the science \
behind their condition.

## CRITICAL CITATION RULES

Every factual claim MUST be supported by a real, verifiable citation.

- Only cite papers you are certain exist with the exact PMID or DOI
- NEVER fabricate or guess a PMID or DOI — they are verified against PubMed in real time
- If you are not confident in a PMID or DOI, omit that citation entirely
- Fewer verified citations is far better than many hallucinated ones
- Each citation must include: author (last name + initials), year, full title as it \
  appears in PubMed, journal name, and at minimum one of: PMID or DOI

## How to Answer

1. MECHANISM — explain the underlying physiological mechanism if relevant
   (e.g., cortical spreading depression, trigeminovascular pathway, CGRP, estrogen withdrawal)

2. EVIDENCE QUALITY — distinguish clearly:
   - Well-established: consistent across multiple RCTs or meta-analyses
   - Emerging: promising but limited studies
   - Anecdotal/theoretical: reported but not yet well-studied

3. PERSONAL RELEVANCE — if the user's trigger profile or hypothesis is provided, \
   connect the research finding to their specific situation

4. PRACTICAL TAKEAWAY — one concrete thing the user can do or log based on this finding

5. MEDICAL CONSULTATION — flag anything that requires a doctor's involvement

## Output Format

### RESEARCH FINDINGS
Your evidence-based answer — 3–6 sentences. Reference citations inline as [1], [2], etc.
Be specific about mechanisms and evidence quality.

### STRUCTURED DATA
```json
{
  "topic": "short topic label (3-5 words)",
  "key_finding": "one sentence summary of the most important finding",
  "evidence_quality": "well-established | emerging | anecdotal",
  "medical_framework": "name of the relevant clinical framework or pathway, if any",
  "action": "one concrete thing to log or try",
  "citations": [
    {
      "ref": 1,
      "author": "Last FM",
      "year": 2017,
      "title": "Full paper title exactly as it appears in PubMed",
      "journal": "Journal Name",
      "pmid": "28271591",
      "doi": "10.1186/s10194-017-0729-9",
      "claim": "The specific claim this citation supports"
    }
  ]
}
```
"""

_PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_CROSSREF_WORKS  = "https://api.crossref.org/works"


def _verify_via_pubmed(citation: dict) -> dict:
    pmid = str(citation.get("pmid", "")).strip()
    if not pmid:
        return citation

    try:
        r = httpx.get(
            _PUBMED_ESUMMARY,
            params={"db": "pubmed", "id": pmid, "retmode": "json"},
            timeout=10,
        )
        if r.status_code != 200:
            return citation

        result = r.json().get("result", {}).get(pmid, {})
        if not result or result.get("uid") != pmid:
            return citation

        # Author last-name match (case-insensitive)
        claimed_last = citation.get("author", "").split()[0].lower()
        pub_authors   = [a.get("name", "").lower() for a in result.get("authors", [])]
        author_ok     = any(claimed_last in a for a in pub_authors)

        # Year match
        pubdate  = result.get("pubdate", "")
        year_ok  = str(citation.get("year", "")) in pubdate

        citation["verified"]     = author_ok and year_ok
        citation["pubmed_title"] = result.get("title", "")
        citation["pubmed_url"]   = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    except Exception:
        pass

    return citation


def _verify_via_crossref(citation: dict) -> dict:
    doi = str(citation.get("doi", "")).strip()
    if not doi:
        return citation

    try:
        r = httpx.get(
            f"{_CROSSREF_WORKS}/{doi}",
            timeout=10,
            headers={"User-Agent": "MigraineTackler/1.0 (mailto:support@migrainetackler.com)"},
        )
        if r.status_code != 200:
            return citation

        item = r.json().get("message", {})

        # Year match
        date_parts = item.get("published", {}).get("date-parts", [[]])
        pub_year   = str(date_parts[0][0]) if date_parts and date_parts[0] else ""
        year_ok    = str(citation.get("year", "")) == pub_year

        # Author last-name match
        claimed_last = citation.get("author", "").split()[0].lower()
        cr_authors   = [a.get("family", "").lower() for a in item.get("author", [])]
        author_ok    = any(claimed_last in a for a in cr_authors)

        citation["verified"]   = author_ok and year_ok
        citation["pubmed_url"] = f"https://doi.org/{doi}"
    except Exception:
        pass

    return citation


def _verify_citation(citation: dict) -> dict:
    """Try PubMed first, fall back to CrossRef."""
    citation = _verify_via_pubmed(citation)
    if not citation.get("verified") and citation.get("doi"):
        citation = _verify_via_crossref(citation)
    if "verified" not in citation:
        citation["verified"] = False
    return citation


def _verify_citations(citations: list[dict]) -> list[dict]:
    return [_verify_citation(c) for c in citations]


def _format_citations_block(citations: list[dict]) -> str:
    if not citations:
        return ""

    lines = ["\n\n---\n**References**"]
    for c in citations:
        ref     = c.get("ref", "?")
        author  = c.get("author", "Unknown")
        year    = c.get("year", "")
        title   = c.get("pubmed_title") or c.get("title", "")
        journal = c.get("journal", "")
        url     = c.get("pubmed_url", "")
        verified = c.get("verified", False)

        status = "✓ verified" if verified else "⚠ could not verify"
        link   = f" [[PubMed]]({url})" if url and verified else ""
        lines.append(f"[{ref}] {author} ({year}). *{title}*. {journal}.{link} `{status}`")

    return "\n".join(lines)


def _extract_question(state: MigraineState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def _build_context(state: MigraineState, question: str) -> str:
    lst = lambda v: ", ".join(v) if v else "none identified"
    lines = [
        f"RESEARCH QUESTION: {question}",
        "",
        "=== USER CONTEXT (for relevance) ===",
        f"Migraine subtype:    {state.get('migraine_subtype', 'unknown')}",
        f"Confirmed triggers:  {lst(state.get('confirmed_triggers', []))}",
        f"Suspected triggers:  {lst(state.get('suspected_triggers', []))}",
        f"Current hypothesis:  {state.get('current_root_cause_hypothesis', 'none yet')}",
        "",
        "=== PRIOR RESEARCH FINDINGS ===",
        "\n".join(state.get("research_findings", [])) or "None recorded yet.",
    ]
    return "\n".join(lines)


def _parse_structured(text: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def run(state: MigraineState) -> dict:
    question = _extract_question(state)
    if not question:
        return {
            "current_agent": "research",
            "messages": [AIMessage(content="No research question provided. Please ask a specific question about migraines or your triggers.")],
        }

    context = _build_context(state, question)
    try:
        response = _llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=context),
        ])
    except Exception as exc:
        return {
            "current_agent": "research",
            "messages": [AIMessage(content=f"Research lookup failed — the AI service returned an error: {exc}. Please check your Google API key and try again.")],
        }

    text       = response.content
    structured = _parse_structured(text)

    raw_citations      = structured.get("citations", [])
    verified_citations = _verify_citations(raw_citations)
    citations_block    = _format_citations_block(verified_citations)

    n_verified = sum(1 for c in verified_citations if c.get("verified"))
    n_total    = len(verified_citations)

    final_content = text + citations_block if citations_block else text
    final_message = AIMessage(content=final_content)

    updates: dict = {
        "current_agent": "research",
        "messages": [final_message],
    }

    if structured.get("key_finding") and structured.get("topic"):
        suffix = f" ({n_verified}/{n_total} citations verified)" if n_total else ""
        updates["research_findings"] = [
            f"[{date.today()}] {structured['topic']}: {structured['key_finding']}{suffix}"
        ]

    if structured.get("medical_framework"):
        updates["medical_frameworks_applied"] = [structured["medical_framework"]]

    return updates
