"""x402 stablecoin micropayment extension for Satoshi API."""

__version__ = "0.1.0"

from .middleware import enable_x402

__all__ = ["enable_x402"]
