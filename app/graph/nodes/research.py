import json
import re
import httpx
import xml.etree.ElementTree as ET
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

# ── API endpoints ─────────────────────────────────────────────────────────────
_PUBMED_ESEARCH   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_PUBMED_ESUMMARY  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_PUBMED_EFETCH    = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1/paper/search"
_SS_FIELDS        = "title,authors,year,abstract,externalIds,citationCount,venue"

SYSTEM_PROMPT = """\
You are the Research Agent for MigraineTackler. You have been provided with real research paper \
abstracts retrieved from PubMed and Semantic Scholar. Synthesize a clear, evidence-based answer \
using ONLY the provided abstracts.

## CRITICAL RULES
- Cite ONLY papers from the RETRIEVED ABSTRACTS list using their index number [1], [2], etc.
- Do NOT introduce facts, statistics, or claims not present in the provided abstracts
- Do NOT add citations from your training knowledge — if the retrieved papers don't cover it, say so
- If retrieved papers are insufficient to answer, state that explicitly

## How to Answer

1. MECHANISM — explain the underlying physiological mechanism if present in the abstracts
2. EVIDENCE QUALITY — based on what the abstracts describe (RCT, meta-analysis, observational, etc.)
3. PERSONAL RELEVANCE — connect findings to the user's trigger profile where relevant
4. PRACTICAL TAKEAWAY — one concrete thing the user can do or log
5. MEDICAL CONSULTATION — flag anything requiring a doctor's involvement

## Output Format

### RESEARCH FINDINGS
Your synthesized answer — 3–6 sentences. Cite inline as [1], [2], etc.

### STRUCTURED DATA
```json
{
  "topic": "short topic label (3-5 words)",
  "key_finding": "one sentence summary of the most important finding",
  "evidence_quality": "well-established | emerging | anecdotal",
  "medical_framework": "name of the relevant clinical framework or pathway, if any",
  "action": "one concrete thing to log or try",
  "cited_indices": [1, 2]
}
```
"""


# ── PubMed retrieval ──────────────────────────────────────────────────────────

def _pubmed_search(query: str, max_results: int = 5) -> list[str]:
    """Return a list of PMIDs for the query."""
    try:
        r = httpx.get(
            _PUBMED_ESEARCH,
            params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"},
            timeout=10,
        )
        return r.json().get("esearchresult", {}).get("idlist", [])
    except Exception:
        return []


def _pubmed_metadata(pmids: list[str]) -> dict[str, dict]:
    """Return {pmid: {title, authors, year, journal, doi}} via esummary."""
    if not pmids:
        return {}
    try:
        r = httpx.get(
            _PUBMED_ESUMMARY,
            params={"db": "pubmed", "id": ",".join(pmids), "retmode": "json"},
            timeout=10,
        )
        result = r.json().get("result", {})
        out = {}
        for pmid in pmids:
            item = result.get(pmid, {})
            if not item:
                continue
            authors = [a.get("name", "") for a in item.get("authors", [])]
            doi = next(
                (
                    aid.get("value", "")
                    for aid in item.get("articleids", [])
                    if aid.get("idtype") == "doi"
                ),
                "",
            )
            out[pmid] = {
                "title":   item.get("title", ""),
                "authors": authors[:3],
                "year":    item.get("pubdate", "")[:4],
                "journal": item.get("fulljournalname", item.get("source", "")),
                "doi":     doi,
            }
        return out
    except Exception:
        return {}


def _pubmed_abstracts(pmids: list[str]) -> dict[str, str]:
    """Return {pmid: abstract_text} via efetch XML."""
    if not pmids:
        return {}
    try:
        r = httpx.get(
            _PUBMED_EFETCH,
            params={"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"},
            timeout=15,
        )
        root = ET.fromstring(r.text)
        out = {}
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            if pmid_el is None:
                continue
            # Structured abstracts have multiple AbstractText elements with Label attributes
            abstract_parts = article.findall(".//AbstractText")
            if not abstract_parts:
                continue
            sections = []
            for part in abstract_parts:
                label = part.get("Label", "")
                text  = (part.text or "").strip()
                if text:
                    sections.append(f"{label}: {text}" if label else text)
            out[pmid_el.text] = " ".join(sections)
        return out
    except Exception:
        return {}


def _search_pubmed(query: str, max_results: int = 5) -> list[dict]:
    pmids    = _pubmed_search(query, max_results)
    metadata = _pubmed_metadata(pmids)
    abstracts = _pubmed_abstracts(pmids)

    papers = []
    for pmid in pmids:
        abstract = abstracts.get(pmid, "")
        if not abstract:
            continue
        meta = metadata.get(pmid, {})
        papers.append({
            "pmid":           pmid,
            "doi":            meta.get("doi", ""),
            "title":          meta.get("title", ""),
            "authors":        meta.get("authors", []),
            "year":           meta.get("year", ""),
            "journal":        meta.get("journal", ""),
            "abstract":       abstract,
            "citation_count": None,
            "source":         "PubMed",
            "url":            f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    return papers


# ── Semantic Scholar retrieval ────────────────────────────────────────────────

def _search_semantic_scholar(query: str, max_results: int = 5) -> list[dict]:
    try:
        r = httpx.get(
            _SEMANTIC_SCHOLAR,
            params={"query": query, "fields": _SS_FIELDS, "limit": max_results},
            timeout=15,
            headers={"User-Agent": "MigraineTackler/1.0"},
        )
        if r.status_code != 200:
            return []
        papers = []
        for item in r.json().get("data", []):
            abstract = (item.get("abstract") or "").strip()
            if not abstract:
                continue
            external = item.get("externalIds") or {}
            authors  = [a.get("name", "") for a in (item.get("authors") or [])[:3]]
            pmid     = str(external.get("PubMed", ""))
            doi      = external.get("DOI", "")
            papers.append({
                "pmid":           pmid,
                "doi":            doi,
                "title":          item.get("title", ""),
                "authors":        authors,
                "year":           str(item.get("year") or ""),
                "journal":        item.get("venue", ""),
                "abstract":       abstract,
                "citation_count": item.get("citationCount"),
                "source":         "Semantic Scholar",
                "url":            f"https://doi.org/{doi}" if doi else "",
            })
        return papers
    except Exception:
        return []


# ── Merge & deduplicate ───────────────────────────────────────────────────────

def _deduplicate(pubmed: list[dict], ss: list[dict]) -> list[dict]:
    """PubMed wins on PMID conflict; Semantic Scholar fills in papers not in PubMed."""
    seen_pmids = {p["pmid"] for p in pubmed if p["pmid"]}
    merged = list(pubmed)
    for paper in ss:
        if paper["pmid"] and paper["pmid"] in seen_pmids:
            continue
        merged.append(paper)
    return merged


def _retrieve_papers(query: str, max_per_source: int = 5) -> list[dict]:
    pubmed = _search_pubmed(query, max_per_source)
    ss     = _search_semantic_scholar(query, max_per_source)
    return _deduplicate(pubmed, ss)


# ── Prompt helpers ────────────────────────────────────────────────────────────

def _format_papers_block(papers: list[dict]) -> str:
    lines = ["=== RETRIEVED RESEARCH ABSTRACTS ==="]
    for i, p in enumerate(papers, 1):
        authors = "; ".join(p["authors"]) or "Unknown"
        cite_note = f" | {p['citation_count']} citations" if p["citation_count"] is not None else ""
        url_note  = f" | {p['url']}" if p["url"] else ""
        lines += [
            f"\n[{i}] {p['title']}",
            f"    {authors} ({p['year']}) — {p['journal']}{cite_note} [{p['source']}]{url_note}",
            f"    PMID: {p['pmid'] or 'n/a'} | DOI: {p['doi'] or 'n/a'}",
            f"    ABSTRACT: {p['abstract']}",
        ]
    return "\n".join(lines)


def _build_context(papers: list[dict], question: str, state: MigraineState) -> str:
    lst = lambda v: ", ".join(dict.fromkeys(v)) if v else "none identified"
    user_ctx = "\n".join([
        "=== USER CONTEXT (for relevance) ===",
        f"Migraine subtype:    {state.get('migraine_subtype', 'unknown')}",
        f"Confirmed triggers:  {lst(state.get('confirmed_triggers', []))}",
        f"Suspected triggers:  {lst(state.get('suspected_triggers', []))}",
        f"Current hypothesis:  {state.get('current_root_cause_hypothesis', 'none yet')}",
    ])
    papers_block = _format_papers_block(papers) if papers else "No papers retrieved."
    return "\n\n".join([f"RESEARCH QUESTION: {question}", user_ctx, papers_block])


def _extract_question(state: MigraineState) -> tuple[str, bool]:
    """Returns (question, is_auto_triggered)."""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content, False
    confirmed = set(state.get("confirmed_triggers", []))
    seen = set(state.get("research_triggers_seen", []))
    new_triggers = confirmed - seen
    if new_triggers:
        trigger_list = ", ".join(sorted(new_triggers))
        return (
            f"What is the evidence for {trigger_list} as migraine triggers? "
            "Include physiological mechanisms, evidence quality, and practical logging suggestions.",
            True,
        )
    return "", False


def _parse_structured(text: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _format_references_block(papers: list[dict], cited_indices: list[int]) -> str:
    cited = [papers[i - 1] for i in cited_indices if 1 <= i <= len(papers)]
    if not cited:
        return ""
    lines = ["\n\n---\n**References**"]
    for i, p in enumerate(cited, 1):
        authors = "; ".join(p["authors"]) or "Unknown"
        url     = p.get("url", "")
        link    = f" [[{p['source']}]]({url})" if url else f" [{p['source']}]"
        lines.append(f"[{i}] {authors} ({p['year']}). *{p['title']}*. {p['journal']}.{link}")
    return "\n".join(lines)


# ── Node entry point ──────────────────────────────────────────────────────────

def run(state: MigraineState) -> dict:
    question, is_auto = _extract_question(state)
    if not question:
        return {
            "current_agent": "research",
            "messages": [AIMessage(content="No research question provided. Please ask a specific question about migraines or your triggers.")],
        }

    papers = _retrieve_papers(question)

    if not papers:
        return {
            "current_agent": "research",
            "messages": [AIMessage(content="Could not retrieve research papers from PubMed or Semantic Scholar. Please check your internet connection and try again.")],
        }

    context = _build_context(papers, question, state)

    try:
        response = _llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=context),
        ])
    except Exception as exc:
        return {
            "current_agent": "research",
            "messages": [AIMessage(content=f"Research synthesis failed — AI service error: {exc}.")],
        }

    text       = response.content
    structured = _parse_structured(text)

    cited_indices   = structured.get("cited_indices", [])
    references_block = _format_references_block(papers, cited_indices)
    final_content   = text + references_block if references_block else text

    updates: dict = {
        "current_agent": "research",
        "messages": [AIMessage(content=final_content)],
    }

    if structured.get("key_finding") and structured.get("topic"):
        n_cited = len(cited_indices)
        suffix  = f" ({n_cited} papers retrieved from PubMed/Semantic Scholar)"
        updates["research_findings"] = [
            f"[{date.today()}] {structured['topic']}: {structured['key_finding']}{suffix}"
        ]

    if structured.get("medical_framework"):
        updates["medical_frameworks_applied"] = [structured["medical_framework"]]

    if is_auto:
        updates["research_triggers_seen"] = list(state.get("confirmed_triggers", []))

    return updates
