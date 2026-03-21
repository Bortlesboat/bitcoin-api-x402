"""Tests for x402 endpoint pricing."""

from bitcoin_api_x402.pricing import get_endpoint_price_usd, ENDPOINT_PRICES


class TestGetEndpointPriceUsd:
    """Test regex-based endpoint price lookup."""

    # --- Premium (paid) endpoints ---

    def test_ai_explain_paid(self):
        assert get_endpoint_price_usd("/api/v1/ai/explain") == "$0.01"

    def test_ai_chat_paid(self):
        assert get_endpoint_price_usd("/api/v1/ai/chat") == "$0.01"

    def test_ai_fee_advice_paid(self):
        assert get_endpoint_price_usd("/api/v1/ai/fee-advice") == "$0.01"

    def test_broadcast_paid(self):
        assert get_endpoint_price_usd("/api/v1/broadcast") == "$0.01"

    def test_nextblock_paid(self):
        assert get_endpoint_price_usd("/api/v1/mining/nextblock") == "$0.01"

    # --- Mid-tier ($0.005) endpoints ---

    def test_observatory_scoreboard_paid(self):
        assert get_endpoint_price_usd("/api/v1/fees/observatory/scoreboard") == "$0.005"

    def test_observatory_block_stats_paid(self):
        assert get_endpoint_price_usd("/api/v1/fees/observatory/block-stats") == "$0.005"

    def test_observatory_estimates_paid(self):
        assert get_endpoint_price_usd("/api/v1/fees/observatory/estimates") == "$0.005"

    def test_fees_landscape_paid(self):
        assert get_endpoint_price_usd("/api/v1/fees/landscape") == "$0.005"

    # --- Everything else is FREE ---

    def test_health_free(self):
        assert get_endpoint_price_usd("/api/v1/health") is None

    def test_status_free(self):
        assert get_endpoint_price_usd("/api/v1/status") is None

    def test_fees_free(self):
        assert get_endpoint_price_usd("/api/v1/fees") is None

    def test_fees_recommended_free(self):
        assert get_endpoint_price_usd("/api/v1/fees/recommended") is None

    def test_blocks_latest_free(self):
        assert get_endpoint_price_usd("/api/v1/blocks/latest") is None

    def test_block_by_height_free(self):
        assert get_endpoint_price_usd("/api/v1/blocks/800000") is None

    def test_tx_free(self):
        assert get_endpoint_price_usd("/api/v1/tx/abcdef0123456789") is None

    def test_mempool_free(self):
        assert get_endpoint_price_usd("/api/v1/mempool") is None

    def test_mining_free(self):
        assert get_endpoint_price_usd("/api/v1/mining") is None

    def test_network_free(self):
        assert get_endpoint_price_usd("/api/v1/network") is None

    def test_unknown_endpoint_free(self):
        assert get_endpoint_price_usd("/api/v1/nonexistent") is None

    def test_root_free(self):
        assert get_endpoint_price_usd("/") is None

    def test_docs_free(self):
        assert get_endpoint_price_usd("/docs") is None


class TestEndpointPricesTable:
    """Test the pricing table structure."""

    def test_all_prices_have_patterns(self):
        for ep in ENDPOINT_PRICES:
            assert ep.pattern, f"Empty pattern: {ep}"

    def test_all_prices_have_descriptions(self):
        for ep in ENDPOINT_PRICES:
            assert ep.description, f"Empty description for {ep.pattern}"

    def test_only_premium_endpoints_priced(self):
        """Only 5 endpoint patterns should be priced."""
        priced = [ep for ep in ENDPOINT_PRICES if ep.price_usd is not None]
        assert len(priced) == 5

    def test_no_free_entries_in_table(self):
        """Table should only contain paid endpoints. Unlisted = free."""
        for ep in ENDPOINT_PRICES:
            assert ep.price_usd is not None, f"Free endpoint shouldn't be in table: {ep.pattern}"
