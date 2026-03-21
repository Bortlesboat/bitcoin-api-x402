"""Shared test fixtures for bitcoin-api-x402."""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from bitcoin_api_x402 import enable_x402


def _create_test_app(
    *,
    pay_to: str = "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01",
    **kwargs,
) -> FastAPI:
    """Create a minimal FastAPI app with x402 middleware for testing."""
    app = FastAPI()

    enable_x402(app, pay_to=pay_to, **kwargs)

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/status")
    async def status():
        return {"status": "running"}

    @app.get("/api/v1/fees")
    async def fees():
        return {"data": {"fast": 10, "medium": 5, "slow": 1}}

    @app.get("/api/v1/blocks/latest")
    async def blocks_latest():
        return {"data": {"height": 800000}}

    @app.get("/api/v1/blocks/{block_id}")
    async def block_detail(block_id: str):
        return {"data": {"hash": block_id}}

    @app.get("/api/v1/tx/{txid}")
    async def tx_detail(txid: str):
        return {"data": {"txid": txid}}

    @app.get("/api/v1/mining/nextblock")
    async def nextblock():
        return {"data": {"predicted_fees": 42}}

    @app.get("/api/v1/mempool")
    async def mempool():
        return {"data": {"size": 5000}}

    @app.get("/api/v1/broadcast")
    async def broadcast():
        return {"data": {"submitted": True}}

    @app.get("/api/v1/ai/explain")
    async def ai_explain():
        return {"data": {"explanation": "test"}}

    @app.get("/api/v1/ai/chat")
    async def ai_chat():
        return {"data": {"response": "test"}}

    return app


@pytest.fixture
def app():
    """Test FastAPI app with x402 middleware."""
    return _create_test_app()


@pytest.fixture
def client(app):
    """Test client for the x402-enabled app."""
    return TestClient(app)
