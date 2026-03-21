"""Endpoint pricing for x402 stablecoin micropayments (USD)."""

import re
from dataclasses import dataclass


@dataclass
class EndpointPrice:
    pattern: str
    price_usd: str | None  # None = free, e.g. "$0.001"
    description: str


# Pricing tiers (USD per request)
# PHILOSOPHY: Almost everything is FREE. Only gate endpoints that cost us real
# resources (AI/LLM calls, tx broadcast) or provide premium analytics.
# Free users first — upsell later once there's traction.
ENDPOINT_PRICES: list[EndpointPrice] = [
    # Premium only — these cost real resources to serve
    EndpointPrice(r"/api/v1/ai/", "$0.01", "AI-powered analysis (LLM calls)"),
    EndpointPrice(r"/api/v1/broadcast$", "$0.01", "Broadcast transaction"),
    EndpointPrice(r"/api/v1/mining/nextblock$", "$0.01", "Next block prediction"),
]

# Compile patterns once
_COMPILED_PRICES = [(re.compile(ep.pattern), ep) for ep in ENDPOINT_PRICES]


def get_endpoint_price_usd(path: str) -> str | None:
    """Get the price in USD for a given endpoint path.

    Returns:
        Price string like "$0.001" for priced endpoints, or None for free/unmatched.
    """
    for pattern, ep in _COMPILED_PRICES:
        if pattern.search(path):
            return ep.price_usd
    return None  # Default: free for unknown endpoints
