"""Knowledge catalog for the advisor: markdown files -> chunks -> embeddings -> search.

The catalog is small, so similarity is computed in numpy instead of a vector
database. Move to pgvector when it grows into thousands of chunks.
"""
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_chunk import KnowledgeChunk
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

CATALOG_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "catalog"
EMBED_BATCH_SIZE = 64


@dataclass(frozen=True)
class Chunk:
    source: str
    heading: str
    content: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(f"{self.heading}\n{self.content}".encode()).hexdigest()

    @property
    def embedding_text(self) -> str:
        return f"{self.heading}\n{self.content}"


@dataclass(frozen=True)
class RetrievedChunk:
    source: str
    heading: str
    content: str
    score: float

    @property
    def reference(self) -> str:
        return f"{self.source}#{self.heading}"


@dataclass(frozen=True)
class SyncResult:
    added: int
    updated: int
    removed: int
    unchanged: int


def parse_markdown(source: str, text: str) -> List[Chunk]:
    """Split a markdown file into chunks: the intro under '# Title' and every '## Section'."""
    chunks: List[Chunk] = []
    title: Optional[str] = None
    heading: Optional[str] = None
    lines: List[str] = []

    def flush():
        body = "\n".join(lines).strip()
        if heading and body:
            chunks.append(Chunk(source=source, heading=heading, content=body))

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            heading, lines = f"{title} / {line[3:].strip()}" if title else line[3:].strip(), []
        elif line.startswith("# ") and title is None:
            title = line[2:].strip()
            heading, lines = title, []
        else:
            lines.append(line)
    flush()
    return chunks


def load_catalog(directory: Path = CATALOG_DIR) -> List[Chunk]:
    chunks: List[Chunk] = []
    for path in sorted(directory.glob("*.md")):
        chunks.extend(parse_markdown(path.name, path.read_text(encoding="utf-8")))
    return chunks


async def sync_catalog(
    db: AsyncSession, llm: LLMClient, chunks: Optional[List[Chunk]] = None
) -> SyncResult:
    """Make the database match the catalog; only changed chunks are embedded (and paid for)."""
    chunks = load_catalog() if chunks is None else chunks
    rows = (await db.execute(select(KnowledgeChunk))).scalars().all()
    existing: Dict[Tuple[str, str], KnowledgeChunk] = {(r.source, r.heading): r for r in rows}

    wanted = {(c.source, c.heading): c for c in chunks}
    to_embed: List[Chunk] = []
    unchanged = 0
    for key, chunk in wanted.items():
        row = existing.get(key)
        if row and row.content_hash == chunk.content_hash and row.embedding_model == llm.embedding_model:
            unchanged += 1
        else:
            to_embed.append(chunk)

    vectors: List[List[float]] = []
    for offset in range(0, len(to_embed), EMBED_BATCH_SIZE):
        batch = to_embed[offset:offset + EMBED_BATCH_SIZE]
        vectors.extend(await llm.embed([c.embedding_text for c in batch]))

    added = updated = 0
    now = datetime.utcnow()
    for chunk, vector in zip(to_embed, vectors):
        row = existing.get((chunk.source, chunk.heading))
        if row:
            updated += 1
        else:
            added += 1
            row = KnowledgeChunk(source=chunk.source, heading=chunk.heading)
            db.add(row)
        row.content = chunk.content
        row.content_hash = chunk.content_hash
        row.embedding = vector
        row.embedding_model = llm.embedding_model
        row.updated_at = now

    removed = 0
    for key, row in existing.items():
        if key not in wanted:
            await db.delete(row)
            removed += 1

    await db.commit()
    logger.info("Knowledge sync: %d added, %d updated, %d removed, %d unchanged", added, updated, removed, unchanged)
    return SyncResult(added, updated, removed, unchanged)


async def retrieve(db: AsyncSession, llm: LLMClient, query: str, k: int = 6) -> List[RetrievedChunk]:
    """Return the k chunks most similar to the query (cosine similarity)."""
    rows = (
        await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.embedding_model == llm.embedding_model))
    ).scalars().all()
    if not rows:
        return []

    [query_vector] = await llm.embed([query])
    matrix = np.asarray([r.embedding for r in rows], dtype=float)
    query_array = np.asarray(query_vector, dtype=float)

    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_array)
    scores = (matrix @ query_array) / np.where(norms == 0, 1.0, norms)

    order = np.argsort(-scores)[:k]
    return [
        RetrievedChunk(rows[i].source, rows[i].heading, rows[i].content, round(float(scores[i]), 4))
        for i in order
    ]
