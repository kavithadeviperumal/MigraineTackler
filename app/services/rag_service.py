"""
RAG service: embed, store, retrieve, and aggregate knowledge chunks.

Retrieval returns clean passages — not raw chunks. Each passage is a
contiguous run of chunks (gap-filled up to 2 intermediate chunks) joined
in chunk_index order so the text reads coherently.
"""

import hashlib
import io
import httpx
from sqlalchemy import text
from sqlmodel import Session

from app.config import settings
from app.models.knowledge_chunk import EMBEDDING_DIM, KnowledgeChunk

_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "embedding-001:embedContent"
)

# Maximum gap (in intermediate chunks) allowed before splitting into a new passage.
# Gap of 2 means: if matched indices are 3 and 6, include chunks 4 and 5.
# Gap of 3+ means separate sections — do not join.
_MAX_GAP = 2

_SOURCE_LABELS = {
    "clinical_guideline": "Clinical Guideline",
    "ayurvedic": "Ayurvedic Text",
    "doctor_note": "Doctor Note",
    "pubmed": "PubMed",
    "semantic_scholar": "Semantic Scholar",
}


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed(text_input: str) -> list[float]:
    r = httpx.post(
        _EMBED_URL,
        params={"key": settings.google_api_key},
        json={"content": {"parts": [{"text": text_input}]}},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["embedding"]["values"]


# ── Text chunking ─────────────────────────────────────────────────────────────

def _chunk_text(body: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """
    Split body into overlapping chunks. Splits on paragraph boundaries first;
    falls back to sentence boundaries for paragraphs that exceed chunk_size.
    """
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= chunk_size:
            current = current + "\n\n" + para
        else:
            chunks.append(current)
            tail = current[-overlap:] if len(current) > overlap else current

            if len(para) > chunk_size:
                # Split long paragraph by sentences
                sentences = [s.strip() + "." for s in para.split(". ") if s.strip()]
                sub = tail
                for sent in sentences:
                    if len(sub) + len(sent) + 1 <= chunk_size:
                        sub = (sub + " " + sent).strip()
                    else:
                        if sub and sub != tail:
                            chunks.append(sub)
                        sub = sent
                current = sub
            else:
                current = (tail + " " + para).strip() if tail else para

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]


# ── pgvector init ─────────────────────────────────────────────────────────────

def init_pgvector(engine) -> None:
    """Enable pgvector extension. Must run before create_all()."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()


# ── Storage ───────────────────────────────────────────────────────────────────

def store_research_chunk(
    session: Session,
    user_id: int,
    source_type: str,
    doc_title: str,
    doc_id: str,
    text_body: str,
) -> None:
    """Store a single research abstract as one chunk (idempotent by doc_id)."""
    existing = session.execute(
        text("SELECT id FROM knowledge_chunks WHERE user_id = :uid AND doc_id = :did LIMIT 1"),
        {"uid": user_id, "did": doc_id},
    ).fetchone()
    if existing:
        return

    embedding = _embed(text_body)
    session.add(KnowledgeChunk(
        user_id=user_id,
        source_type=source_type,
        doc_title=doc_title,
        doc_id=doc_id,
        page_number=0,
        chunk_index=0,
        chunk_text=text_body,
        embedding=embedding,
    ))
    session.commit()


def ingest_pdf(
    session: Session,
    user_id: int,
    source_type: str,
    doc_title: str,
    pdf_bytes: bytes,
) -> int:
    """Parse PDF, chunk by page, embed, and store. Returns total chunks stored."""
    from pypdf import PdfReader

    doc_id = hashlib.sha256(pdf_bytes).hexdigest()[:16]

    # Idempotent: remove existing chunks for this exact file
    session.execute(
        text("DELETE FROM knowledge_chunks WHERE user_id = :uid AND doc_id = :did"),
        {"uid": user_id, "did": doc_id},
    )
    session.commit()

    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = 0
    global_chunk_index = 0

    for page_num, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            continue
        for chunk in _chunk_text(page_text):
            embedding = _embed(chunk)
            session.add(KnowledgeChunk(
                user_id=user_id,
                source_type=source_type,
                doc_title=doc_title,
                doc_id=doc_id,
                page_number=page_num + 1,
                chunk_index=global_chunk_index,
                chunk_text=chunk,
                embedding=embedding,
            ))
            global_chunk_index += 1
            total += 1

    session.commit()
    return total


# ── Retrieval + aggregation ───────────────────────────────────────────────────

def _vec_literal(vec: list[float]) -> str:
    """Format a float list as a pgvector literal."""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


def _fetch_chunks_in_range(
    session: Session,
    user_id: int,
    doc_id: str,
    start_idx: int,
    end_idx: int,
) -> list[dict]:
    """Fetch all chunks for a doc between start_idx and end_idx inclusive."""
    rows = session.execute(
        text("""
            SELECT chunk_index, chunk_text
            FROM knowledge_chunks
            WHERE user_id = :uid AND doc_id = :did
              AND chunk_index >= :start AND chunk_index <= :end
            ORDER BY chunk_index
        """),
        {"uid": user_id, "did": doc_id, "start": start_idx, "end": end_idx},
    ).fetchall()
    return [{"chunk_index": r.chunk_index, "chunk_text": r.chunk_text} for r in rows]


def _build_passages(
    session: Session,
    user_id: int,
    hit_rows: list,
) -> list[dict]:
    """
    Given similarity-ranked hit rows, group into coherent passages per document.

    Algorithm:
      1. Group hits by doc_id.
      2. Sort matched chunk indices positionally.
      3. Split into runs: consecutive indices with gap > _MAX_GAP start a new passage.
      4. For each run, fetch gap-fill chunks (start_idx..end_idx inclusive).
      5. Join in chunk_index order.
    """
    # Group: {doc_id: {meta, matched: [(chunk_index, similarity)]}}
    by_doc: dict[str, dict] = {}
    for row in hit_rows:
        did = row.doc_id
        if did not in by_doc:
            by_doc[did] = {
                "source_type": row.source_type,
                "doc_title": row.doc_title,
                "owner_user_id": row.user_id,
                "matched": [],
            }
        by_doc[did]["matched"].append((row.chunk_index, float(row.similarity)))

    passages: list[dict] = []

    for doc_id, info in by_doc.items():
        matched = sorted(info["matched"], key=lambda x: x[0])  # sort by chunk_index
        matched_indices = [m[0] for m in matched]
        sim_by_idx = {m[0]: m[1] for m in matched}

        # Split into runs where gap <= _MAX_GAP intermediate chunks
        # Index diff <= _MAX_GAP + 1 means at most _MAX_GAP chunks between them
        runs: list[list[int]] = []
        current_run = [matched_indices[0]]
        for i in range(1, len(matched_indices)):
            if matched_indices[i] - matched_indices[i - 1] <= _MAX_GAP + 1:
                current_run.append(matched_indices[i])
            else:
                runs.append(current_run)
                current_run = [matched_indices[i]]
        runs.append(current_run)

        for run in runs:
            start_idx = run[0]
            end_idx = run[-1]

            # Fetch all chunks in range (includes gap-fill chunks)
            range_chunks = _fetch_chunks_in_range(
                session, info["owner_user_id"], doc_id, start_idx, end_idx
            )

            combined_text = "\n\n".join(c["chunk_text"] for c in range_chunks)
            top_similarity = max(sim_by_idx[idx] for idx in run if idx in sim_by_idx)

            passages.append({
                "source_type": info["source_type"],
                "doc_title": info["doc_title"],
                "source_label": _SOURCE_LABELS.get(info["source_type"], info["source_type"]),
                "combined_text": combined_text,
                "top_similarity": round(top_similarity, 3),
                "chunk_count": len(range_chunks),
            })

    # Most relevant passages first
    passages.sort(key=lambda p: p["top_similarity"], reverse=True)
    return passages


def retrieve_relevant(
    session: Session,
    user_id: int,
    query: str,
    top_k: int = 8,
    min_similarity: float = 0.55,
) -> list[dict]:
    """
    Return aggregated passages most semantically relevant to the query.

    Chunks are retrieved by cosine similarity, then grouped by document and
    assembled into coherent passages (gap-filled up to _MAX_GAP intermediate
    chunks, joined in chunk_index order).
    """
    try:
        query_vec = _embed(query)
    except Exception:
        return []

    vec_str = _vec_literal(query_vec)

    sql = text(f"""
        SELECT user_id, doc_id, source_type, doc_title, chunk_index,
               1 - (embedding <=> '{vec_str}'::vector) AS similarity
        FROM knowledge_chunks
        WHERE (user_id = :user_id OR user_id = 0)
          AND 1 - (embedding <=> '{vec_str}'::vector) >= :min_sim
        ORDER BY embedding <=> '{vec_str}'::vector
        LIMIT :top_k
    """)

    try:
        rows = session.execute(sql, {
            "user_id": user_id,
            "min_sim": min_similarity,
            "top_k": top_k,
        }).fetchall()
    except Exception:
        return []

    if not rows:
        return []

    return _build_passages(session, user_id, rows)


# ── Source management ─────────────────────────────────────────────────────────

def list_sources(session: Session, user_id: int) -> list[dict]:
    rows = session.execute(
        text("""
            SELECT doc_id, doc_title, source_type,
                   MIN(created_at) AS uploaded_at, COUNT(*) AS chunk_count
            FROM knowledge_chunks
            WHERE user_id = :user_id
            GROUP BY doc_id, doc_title, source_type
            ORDER BY MIN(created_at) DESC
        """),
        {"user_id": user_id},
    ).fetchall()
    return [
        {
            "doc_id": r.doc_id,
            "doc_title": r.doc_title,
            "source_type": r.source_type,
            "source_label": _SOURCE_LABELS.get(r.source_type, r.source_type),
            "uploaded_at": str(r.uploaded_at),
            "chunk_count": r.chunk_count,
        }
        for r in rows
    ]


def delete_source(session: Session, user_id: int, doc_id: str) -> int:
    result = session.execute(
        text("DELETE FROM knowledge_chunks WHERE user_id = :uid AND doc_id = :did"),
        {"uid": user_id, "did": doc_id},
    )
    session.commit()
    return result.rowcount
