from datetime import datetime

from sqlalchemy import Column, Text
from pgvector.sqlalchemy import Vector
from sqlmodel import SQLModel, Field

EMBEDDING_DIM = 768  # OpenAI text-embedding-3-small (dimensions=768)

# Valid source types.
# clinical_guideline is system-seeded (guideline_seeder.py), not user-uploaded.
# doctor_note is the only user-uploadable type.
SOURCE_TYPES = {
    "pubmed",
    "semantic_scholar",
    "clinical_guideline",
    "doctor_note",
}


class KnowledgeChunk(SQLModel, table=True):
    __tablename__ = "knowledge_chunks"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    source_type: str = Field(index=True)
    doc_title: str
    doc_id: str = Field(index=True)   # PMID for pubmed; SHA-256 prefix for uploads
    page_number: int = Field(default=0)
    chunk_index: int = Field(default=0)
    chunk_text: str = Field(sa_column=Column(Text))
    embedding: list | None = Field(default=None, sa_column=Column(Vector(EMBEDDING_DIM)))
    created_at: datetime = Field(default_factory=datetime.utcnow)
