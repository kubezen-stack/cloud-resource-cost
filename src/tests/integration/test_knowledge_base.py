import pytest
from sqlalchemy import select

from app.models.knowledge_chunk import KnowledgeChunk
from app.services.knowledge_base import Chunk, load_catalog, retrieve, sync_catalog
from tests.fake_llm import FakeLLM


async def _rows(db):
    return (await db.execute(select(KnowledgeChunk))).scalars().all()


@pytest.mark.asyncio
async def test_sync_loads_whole_catalog(db_session):
    llm = FakeLLM()

    result = await sync_catalog(db_session, llm)

    assert result.added == len(load_catalog())
    assert len(await _rows(db_session)) == result.added


@pytest.mark.asyncio
async def test_second_sync_embeds_nothing(db_session):
    llm = FakeLLM()
    await sync_catalog(db_session, llm)
    llm.embedded.clear()

    result = await sync_catalog(db_session, llm)

    assert (result.added, result.updated, result.removed) == (0, 0, 0)
    assert llm.embedded == []


@pytest.mark.asyncio
async def test_sync_updates_changed_and_removes_missing_chunks(db_session):
    llm = FakeLLM()
    await sync_catalog(db_session, llm, [Chunk("a.md", "A", "one"), Chunk("b.md", "B", "two")])
    llm.embedded.clear()

    result = await sync_catalog(db_session, llm, [Chunk("a.md", "A", "changed")])

    assert (result.added, result.updated, result.removed) == (0, 1, 1)
    rows = await _rows(db_session)
    assert [(r.source, r.content) for r in rows] == [("a.md", "changed")]
    assert len(llm.embedded) == 1


@pytest.mark.asyncio
async def test_changing_embedding_model_reembeds_everything(db_session):
    llm = FakeLLM()
    chunks = [Chunk("a.md", "A", "one")]
    await sync_catalog(db_session, llm, chunks)

    llm.embedding_model = "another-model"
    result = await sync_catalog(db_session, llm, chunks)

    assert result.updated == 1


@pytest.mark.asyncio
async def test_retrieve_ranks_the_relevant_chunk_first(db_session):
    llm = FakeLLM()
    await sync_catalog(db_session, llm)

    results = await retrieve(db_session, llm, "which database instance class and multi-az backups for production postgres", k=3)

    assert len(results) == 3
    assert results[0].source == "rds-databases.md"
    assert results[0].score >= results[1].score >= results[2].score


@pytest.mark.asyncio
async def test_retrieve_on_empty_knowledge_base_returns_nothing(db_session):
    llm = FakeLLM()

    assert await retrieve(db_session, llm, "anything") == []
    assert llm.embedded == []


@pytest.mark.asyncio
async def test_retrieve_ignores_chunks_from_another_embedding_model(db_session):
    llm = FakeLLM()
    await sync_catalog(db_session, llm, [Chunk("a.md", "A", "one")])

    llm.embedding_model = "another-model"

    assert await retrieve(db_session, llm, "one") == []
