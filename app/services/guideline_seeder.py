"""
System-side seeder for clinical migraine guidelines.

Fetches curated PubMed abstracts and stores them under SYSTEM_USER_ID=0
as source_type="clinical_guideline". Idempotent — safe to run on every startup.

To add more guidelines: find the PMID on pubmed.ncbi.nlm.nih.gov and append
to _GUIDELINE_PMIDS below.
"""

import xml.etree.ElementTree as ET

import httpx
from sqlmodel import Session

from app.services.rag_service import store_research_chunk

SYSTEM_USER_ID = None  # NULL = shared content, no FK owner required

# Verified migraine guideline PMIDs — add more as needed
_GUIDELINE_PMIDS = [
    "22529202",  # AAN 2012: Evidence-based guideline update — prevention of episodic migraine
    "26025924",  # AAN 2015: Pharmacological treatment for episodic migraine prevention in adults
    "29691490",  # AHS 2018: Acute treatment of migraine in adults
    "31529127",  # AHS 2019: The American Headache Society position statement on CGRP mAbs
    "33650870",  # IHS 2021: ICHD-3 — International Classification of Headache Disorders
]

_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _fetch_titles(pmids: list[str]) -> dict[str, str]:
    try:
        r = httpx.get(
            _ESUMMARY,
            params={"db": "pubmed", "id": ",".join(pmids), "retmode": "json"},
            timeout=15,
        )
        result = r.json().get("result", {})
        return {pmid: result.get(pmid, {}).get("title", f"Guideline PMID:{pmid}") for pmid in pmids}
    except Exception:
        return {pmid: f"Guideline PMID:{pmid}" for pmid in pmids}


def _fetch_abstracts(pmids: list[str]) -> dict[str, str]:
    try:
        r = httpx.get(
            _EFETCH,
            params={"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"},
            timeout=20,
        )
        root = ET.fromstring(r.text)
        out = {}
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            if pmid_el is None:
                continue
            parts = article.findall(".//AbstractText")
            sections = []
            for p in parts:
                label = p.get("Label", "")
                body = (p.text or "").strip()
                if body:
                    sections.append(f"{label}: {body}" if label else body)
            if sections and pmid_el.text:
                out[pmid_el.text] = " ".join(sections)
        return out
    except Exception:
        return {}


def seed_guidelines(session: Session) -> int:
    """
    Fetch curated guideline abstracts from PubMed and store under SYSTEM_USER_ID.
    Returns the number of new chunks stored (0 if all already exist).
    """
    pmids = _GUIDELINE_PMIDS
    titles = _fetch_titles(pmids)
    abstracts = _fetch_abstracts(pmids)

    stored = 0
    for pmid in pmids:
        abstract = abstracts.get(pmid, "")
        if not abstract:
            continue
        store_research_chunk(
            session=session,
            user_id=SYSTEM_USER_ID,
            source_type="clinical_guideline",
            doc_title=titles.get(pmid, f"Guideline PMID:{pmid}"),
            doc_id=f"guideline_{pmid}",
            text_body=abstract,
        )
        stored += 1

    return stored
