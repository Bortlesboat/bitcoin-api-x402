# bitcoin-api-x402

x402 stablecoin micropayment extension for [Satoshi API](https://github.com/Bortlesboat/bitcoin-api). Pay per request with USDC on Base.

## Install

```bash
pip install -e .
```

## Usage

```python
from bitcoin_api_x402 import enable_x402

# In your FastAPI app setup:
enable_x402(app)
```

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `X402_PAY_TO_ADDRESS` | Yes | — | EVM wallet address for USDC |
| `X402_NETWORK` | No | `eip155:8453` | Base mainnet chain ID |
| `X402_FACILITATOR_URL` | No | `https://x402.org/facilitator` | x402 facilitator |
| `X402_SCHEME` | No | `exact` | Payment scheme |

Or pass directly:

```python
enable_x402(app, pay_to="0x...", network="eip155:8453")
```

## Endpoint pricing

Almost everything is **free**. Only endpoints that cost real resources to serve are gated:

| Price | Endpoints | Why |
|-------|-----------|-----|
| $0.01 | `/ai/*` | LLM inference costs |
| $0.01 | `/broadcast` | Node relay resources |
| $0.01 | `/mining/nextblock` | Heavy computation |

Everything else (fees, blocks, txs, mempool, mining, network, etc.) is free for all users. Requests with an `X-API-Key` header bypass x402 payment entirely.

## How it works

1. Anonymous request hits a priced endpoint
2. API returns `402 Payment Required` with x402 payment requirements JSON
3. Client sends payment via `X-PAYMENT` header
4. Middleware verifies payment and grants access

## Development

```bash
pip install -e ".[dev]"
pytest -v
```
