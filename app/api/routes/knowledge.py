from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from app.api.deps import get_current_user
from app.database import get_session_dep
from app.models.user import User
from app.services.rag_service import delete_source, ingest_pdf, list_sources

router = APIRouter()

_VALID_SOURCE_TYPES = {"doctor_note"}


@router.post("/upload")
async def upload_knowledge(
    file: UploadFile = File(...),
    source_type: str = Form(...),
    title: str = Form(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    """
    Upload a PDF into the personal knowledge base.

    source_type must be: doctor_note (neurology consult notes, lab results,
    prescription summaries, MRI/CT reports, discharge instructions).
    """
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    if source_type not in _VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"source_type must be one of: {', '.join(sorted(_VALID_SOURCE_TYPES))}",
        )
    if not title.strip():
        raise HTTPException(status_code=400, detail="title is required.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    assert current_user.id is not None
    chunks_stored = ingest_pdf(session, current_user.id, source_type, title.strip(), pdf_bytes)
    return {
        "status": "ok",
        "title": title.strip(),
        "source_type": source_type,
        "chunks_stored": chunks_stored,
    }


@router.get("/sources")
def get_sources(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    """List all documents in the user's knowledge base."""
    assert current_user.id is not None
    return list_sources(session, current_user.id)


@router.delete("/source/{doc_id}")
def remove_source(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
):
    """Remove a document and all its chunks from the knowledge base."""
    assert current_user.id is not None
    deleted = delete_source(session, current_user.id, doc_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "ok", "deleted_chunks": deleted}
