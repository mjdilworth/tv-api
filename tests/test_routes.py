"""API contract tests."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tv_api.main import app

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


@pytest_asyncio.fixture()
async def api_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_health_endpoint(api_client: AsyncClient) -> None:
    response = await api_client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_endpoint(api_client: AsyncClient) -> None:
    response = await api_client.get("/readiness")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_content_listing(api_client: AsyncClient) -> None:
    response = await api_client.get("/content")
    assert response.status_code == 200
    payload = response.json()
    names = {item["name"] for item in payload["items"]}
    assert (ASSETS_DIR / "h-6.mp4").name in names


@pytest.mark.asyncio
async def test_content_download(api_client: AsyncClient) -> None:
    filename = "h-6.mp4"
    response = await api_client.get(f"/content/{filename}")
    assert response.status_code == 200
    assert filename in response.headers.get("content-disposition", "")
    assert response.content == (ASSETS_DIR / filename).read_bytes()


@pytest.mark.asyncio
async def test_content_disallows_path_traversal(api_client: AsyncClient) -> None:
    response = await api_client.get("/content/../pyproject.toml")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_privacy_endpoint_returns_policy(api_client: AsyncClient) -> None:
    response = await api_client.get("/privacy")
    assert response.status_code == 200
    payload = response.json()
    assert "policy" in payload
    assert payload["application"] == "dil.map"


@pytest.mark.asyncio
async def test_user_endpoint_echoes_email(api_client: AsyncClient) -> None:
    response = await api_client.post("/user", json={"email": "demo@example.com"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "demo@example.com"
    assert payload["message"] == "Email received"
