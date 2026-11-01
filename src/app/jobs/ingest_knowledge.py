import asyncio
import logging
import sys

from app.core.database import async_session, engine
from app.services.knowledge_base import sync_catalog
from app.services.llm_client import LLMError, get_llm_client

logger = logging.getLogger("knowledge-ingest")

async def run() -> int:
    try:
        llm = get_llm_client()
    except LLMError as e:
        logger.error("Cannot ingest: %s", e)
        return 1
    try:
        async with async_session() as db:
            result = await sync_catalog(db, llm)
    except LLMError as e:
        logger.error("Embedding failed: %s", e)
        return 1
    finally:
        await llm.aclose()
        await engine.dispose()
    logger.info(
        "Done: %d added, %d updated, %d removed, %d unchanged",
        result.added, result.updated, result.removed, result.unchanged,
    )
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
