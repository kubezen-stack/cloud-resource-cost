import logging
import time
from collections import defaultdict, deque
from typing import Annotated, AsyncIterator, Deque, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.advisor import AdvisorRequest, AdvisorResponse, SourceRef
from app.services.advisor_service import AdvisorError, KnowledgeBaseEmpty, recommend
from app.services.llm_client import LLMClient, LLMError, LLMNotConfigured, get_llm_client

logger = logging.getLogger(__name__)

router = APIRouter()

WINDOW_SECONDS = 3600
# Per-process sliding window: with several workers the real limit is a few times
# higher. Enough to stop accidental spend; use a shared store for strict limits.
_calls: Dict[str, Deque[float]] = defaultdict(deque)


def _check_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    calls = _calls[user_id]
    while calls and now - calls[0] > WINDOW_SECONDS:
        calls.popleft()
    if len(calls) >= settings.ADVISOR_RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Advisor request limit reached, try again later",
        )
    calls.append(now)


async def get_llm() -> AsyncIterator[LLMClient]:
    try:
        client = get_llm_client()
    except LLMNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI advisor is not configured",
        )
    try:
        yield client
    finally:
        await client.aclose()


@router.post("/recommend", response_model=AdvisorResponse)
async def recommend_architecture(
    body: AdvisorRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[LLMClient, Depends(get_llm)],
):
    if len(body.requirements) > settings.ADVISOR_MAX_REQUIREMENTS_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Requirements are limited to {settings.ADVISOR_MAX_REQUIREMENTS_CHARS} characters",
        )
    _check_rate_limit(str(current_user.id))

    try:
        result = await recommend(db, llm, body.requirements)
    except KnowledgeBaseEmpty:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge base is not loaded yet",
        )
    except (AdvisorError, LLMError):
        logger.exception("Advisor failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI advisor could not produce a recommendation, try again",
        )

    return AdvisorResponse(
        plan=result.plan,
        sources=[SourceRef(reference=c.reference, score=c.score) for c in result.sources],
        model=llm.model,
    )
