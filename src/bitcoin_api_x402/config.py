"""Configuration for x402 stablecoin micropayments."""

import os
from dataclasses import dataclass, field


@dataclass
class X402Config:
    """x402 configuration loaded from environment variables.

    Required:
        X402_PAY_TO_ADDRESS: EVM wallet address to receive USDC payments.

    Optional:
        X402_NETWORK: EIP-155 chain identifier (default: Base mainnet).
        X402_FACILITATOR_URL: x402 facilitator service URL.
        X402_SCHEME: Payment scheme (default: exact).
        X402_DEFAULT_PRICE: Fallback price for unmatched endpoints (default: $0.001).
    """

    pay_to_address: str = ""
    network: str = "eip155:8453"
    facilitator_url: str = "https://x402.org/facilitator"
    scheme: str = "exact"
    default_price: str = "$0.001"

    def validate(self) -> None:
        """Raise ValueError if required fields are missing."""
        if not self.pay_to_address:
            raise ValueError(
                "X402_PAY_TO_ADDRESS is required. "
                "Set it to your EVM wallet address for USDC payments."
            )
        if not self.pay_to_address.startswith("0x") or len(self.pay_to_address) != 42:
            raise ValueError(
                f"X402_PAY_TO_ADDRESS must be a valid EVM address (0x + 40 hex chars), "
                f"got: {self.pay_to_address!r}"
            )


def load_config() -> X402Config:
    """Load x402 configuration from environment variables."""
    return X402Config(
        pay_to_address=os.getenv("X402_PAY_TO_ADDRESS", ""),
        network=os.getenv("X402_NETWORK", "eip155:8453"),
        facilitator_url=os.getenv("X402_FACILITATOR_URL", "https://x402.org/facilitator"),
        scheme=os.getenv("X402_SCHEME", "exact"),
        default_price=os.getenv("X402_DEFAULT_PRICE", "$0.001"),
    )
