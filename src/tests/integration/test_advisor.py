import json

import pytest
import pytest_asyncio

from app.api.v1 import advisor as advisor_api
from app.core.config import settings
from app.main import app
from app.services.knowledge_base import sync_catalog
from app.services.llm_client import LLMError
from tests.fake_llm import FakeLLM

URL = "/api/v1/advisor/recommend"
REQUIREMENTS = "Web shop with about 200 requests per second at peak, PostgreSQL database, needs to be highly available."
ANSWER = json.dumps({
    "summary": "Two-tier web application",
    "assumptions": ["Peak is 200 rps"],
    "components": [{"name": "DB", "aws_service": "RDS PostgreSQL Multi-AZ", "sizing": "db.m6g.large",
                    "rationale": "HA", "basis": "general_knowledge", "sources": []}],
    "open_questions": [],
    "risks": [],
})


@pytest.fixture(autouse=True)
def clean_rate_limit():
    advisor_api._calls.clear()
    yield
    advisor_api._calls.clear()
    app.dependency_overrides.pop(advisor_api.get_llm, None)


def use_llm(llm):
    async def override():
        yield llm
    app.dependency_overrides[advisor_api.get_llm] = override


@pytest_asyncio.fixture
async def loaded_llm(db_session):
    llm = FakeLLM([ANSWER] * 20)
    await sync_catalog(db_session, llm)
    use_llm(llm)
    return llm


@pytest.mark.asyncio
async def test_recommend_returns_plan_with_sources(client, auth_headers, loaded_llm):
    response = await client.post(URL, json={"requirements": REQUIREMENTS}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["plan"]["components"][0]["aws_service"] == "RDS PostgreSQL Multi-AZ"
    assert data["model"] == "fake-chat"
    assert 1 <= len(data["sources"]) <= 14
    assert data["plan"]["components"][0]["basis"] == "general_knowledge"
    assert "verified" in data["note"]


@pytest.mark.asyncio
async def test_requires_authentication(client, loaded_llm):
    response = await client.post(URL, json={"requirements": REQUIREMENTS})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_short_requirements_are_rejected(client, auth_headers, loaded_llm):
    response = await client.post(URL, json={"requirements": "too short"}, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_too_long_requirements_are_rejected(client, auth_headers, loaded_llm, monkeypatch):
    monkeypatch.setattr(settings, "ADVISOR_MAX_REQUIREMENTS_CHARS", 50)
    response = await client.post(URL, json={"requirements": "x" * 51}, headers=auth_headers)
    assert response.status_code == 413
    assert loaded_llm.calls == []


@pytest.mark.asyncio
async def test_not_configured_returns_503(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    response = await client.post(URL, json={"requirements": REQUIREMENTS}, headers=auth_headers)
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


@pytest.mark.asyncio
async def test_empty_knowledge_base_returns_503(client, auth_headers):
    use_llm(FakeLLM([ANSWER]))
    response = await client.post(URL, json={"requirements": REQUIREMENTS}, headers=auth_headers)
    assert response.status_code == 503
    assert "Knowledge base" in response.json()["detail"]


@pytest.mark.asyncio
async def test_provider_failure_returns_502_without_internals(client, auth_headers, db_session):
    class Broken(FakeLLM):
        async def complete_json(self, system, user):
            raise LLMError("provider said: secret-token-123")

    llm = Broken()
    await sync_catalog(db_session, llm)
    use_llm(llm)

    response = await client.post(URL, json={"requirements": REQUIREMENTS}, headers=auth_headers)

    assert response.status_code == 502
    assert "secret-token" not in response.text


@pytest.mark.asyncio
async def test_rate_limit_returns_429(client, auth_headers, loaded_llm, monkeypatch):
    monkeypatch.setattr(settings, "ADVISOR_RATE_LIMIT_PER_HOUR", 2)

    codes = [
        (await client.post(URL, json={"requirements": REQUIREMENTS}, headers=auth_headers)).status_code
        for _ in range(3)
    ]

    assert codes == [200, 200, 429]
