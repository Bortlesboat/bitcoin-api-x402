"""Tests for x402 middleware integration."""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


class TestAnonymousRequests:
    """Test anonymous requests (no API key, no payment)."""

    def test_priced_endpoint_returns_402(self, client):
        resp = client.get("/api/v1/ai/explain")
        assert resp.status_code == 402
        body = resp.json()
        assert body["error"]["status"] == 402
        assert body["error"]["title"] == "Payment Required"
        assert "X-Price-USD" in resp.headers
        # V2: payment data in Payment-Required header, not body
        assert "Payment-Required" in resp.headers
        import base64, json as _json
        pr = _json.loads(base64.b64decode(resp.headers["Payment-Required"]))
        assert pr["x402Version"] == 2
        assert pr["accepts"][0]["scheme"] == "exact"
        assert pr["accepts"][0]["network"] == "eip155:8453"
        assert "amount" in pr["accepts"][0]

    def test_broadcast_returns_402(self, client):
        resp = client.get("/api/v1/broadcast")
        assert resp.status_code == 402

    def test_nextblock_returns_402(self, client):
        resp = client.get("/api/v1/mining/nextblock")
        assert resp.status_code == 402
        assert resp.headers["X-Price-USD"] == "$0.01"

    def test_free_endpoint_passes_through(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_status_is_free(self, client):
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200

    def test_fees_are_free(self, client):
        """Fees should be free - don't pricegate basic data."""
        resp = client.get("/api/v1/fees")
        assert resp.status_code == 200

    def test_blocks_are_free(self, client):
        resp = client.get("/api/v1/blocks/latest")
        assert resp.status_code == 200

    def test_tx_is_free(self, client):
        resp = client.get("/api/v1/tx/abcdef0123456789")
        assert resp.status_code == 200

    def test_mempool_is_free(self, client):
        resp = client.get("/api/v1/mempool")
        assert resp.status_code == 200

    def test_fees_plan_is_free(self, client):
        resp = client.get("/api/v1/fees/plan")
        assert resp.status_code == 200

    def test_fees_savings_is_free(self, client):
        resp = client.get("/api/v1/fees/savings")
        assert resp.status_code == 200

    def test_unknown_endpoint_passes_through(self, client):
        """Unknown endpoints are free by default (no price match)."""
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404  # FastAPI 404, not 402

    def test_402_includes_payment_requirements(self, client):
        resp = client.get("/api/v1/ai/chat")
        assert resp.status_code == 402
        import base64, json as _json
        pr = _json.loads(base64.b64decode(resp.headers["Payment-Required"]))
        reqs = pr["accepts"][0]
        assert reqs["payTo"] == "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
        assert pr["resource"]["url"].endswith("/api/v1/ai/chat")
        assert "amount" in reqs


class TestApiKeyBypass:
    """Test that API key requests bypass x402."""

    def test_api_key_header_bypasses_x402(self, client):
        resp = client.get("/api/v1/ai/explain", headers={"X-API-Key": "test-key-123"})
        assert resp.status_code == 200

    def test_api_key_query_param_bypasses_x402(self, client):
        resp = client.get("/api/v1/ai/explain?api_key=test-key-123")
        assert resp.status_code == 200

    def test_api_key_on_broadcast(self, client):
        resp = client.get(
            "/api/v1/broadcast", headers={"X-API-Key": "test-key"}
        )
        assert resp.status_code == 200


class TestX402Payment:
    """Test x402 payment verification flow."""

    @patch("bitcoin_api_x402.middleware._verify_x402_payment")
    def test_valid_payment_grants_access(self, mock_verify, client):
        mock_verify.return_value = (True, "pay-abc123")
        resp = client.get(
            "/api/v1/ai/explain",
            headers={"X-PAYMENT": "some-valid-payment-token"},
        )
        assert resp.status_code == 200

    @patch("bitcoin_api_x402.middleware._verify_x402_payment")
    def test_valid_payment_on_broadcast(self, mock_verify, client):
        mock_verify.return_value = (True, "pay-xyz")
        resp = client.get(
            "/api/v1/broadcast",
            headers={"X-PAYMENT": "payment-token"},
        )
        assert resp.status_code == 200

    @patch("bitcoin_api_x402.middleware._verify_x402_payment")
    def test_invalid_payment_returns_401(self, mock_verify, client):
        mock_verify.return_value = (False, "insufficient funds")
        resp = client.get(
            "/api/v1/ai/explain",
            headers={"X-PAYMENT": "bad-payment"},
        )
        assert resp.status_code == 401
        assert "verification failed" in resp.json()["error"]["detail"]

    @patch("bitcoin_api_x402.middleware._verify_x402_payment")
    def test_verified_payment_sets_tier(self, mock_verify, app):
        """Verify that valid payment sets request.state.tier to 'pro'."""
        mock_verify.return_value = (True, "pay123")

        tier_seen = {}

        @app.middleware("http")
        async def capture_tier(request, call_next):
            response = await call_next(request)
            if hasattr(request.state, "tier"):
                tier_seen["tier"] = request.state.tier
                tier_seen["key_hash"] = request.state.key_hash
            return response

        client = TestClient(app)
        resp = client.get(
            "/api/v1/ai/explain",
            headers={"X-PAYMENT": "valid-payment"},
        )
        assert resp.status_code == 200
        assert tier_seen.get("tier") == "pro"
        assert tier_seen.get("key_hash") == "x402:pay123"


class TestPricingTiers:
    """All premium endpoints should have the same price ($0.01)."""

    def _get_amount(self, resp):
        import base64, json as _json
        pr = _json.loads(base64.b64decode(resp.headers["Payment-Required"]))
        return pr["accepts"][0]["amount"]

    def test_ai_endpoint_price(self, client):
        resp = client.get("/api/v1/ai/explain")
        assert resp.status_code == 402
        assert self._get_amount(resp) == "0.01"

    def test_broadcast_price(self, client):
        resp = client.get("/api/v1/broadcast")
        assert resp.status_code == 402
        assert self._get_amount(resp) == "0.01"

    def test_nextblock_price(self, client):
        resp = client.get("/api/v1/mining/nextblock")
        assert resp.status_code == 402
        assert self._get_amount(resp) == "0.01"
