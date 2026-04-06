"""FastAPI middleware for x402 stablecoin micropayments."""

import base64
import json
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import load_config
from .pricing import get_endpoint_price_usd

log = logging.getLogger(__name__)

# Injectable payment logger — set via set_payment_logger()
_payment_logger = None


def set_payment_logger(fn):
    """Inject a callback for x402 payment analytics.

    The callback signature is:
        fn(endpoint, price_usd, status, client_ip, payment_id, user_agent)
    """
    global _payment_logger
    _payment_logger = fn


def _log_payment(endpoint, price_usd, status, client_ip="", payment_id="", user_agent=""):
    """Call the injected logger if set. Never raises."""
    if _payment_logger is not None:
        try:
            _payment_logger(endpoint, price_usd, status, client_ip, payment_id, user_agent)
        except Exception:
            log.debug("x402 payment logger error", exc_info=True)


# Payment header used by the x402 protocol
X402_PAYMENT_HEADER = "X-PAYMENT"

# Whether the full x402 SDK is available for server-side verification
_HAS_X402_SDK = False
try:
    from x402.http import (
        HTTPFacilitatorClientSync,
        X_PAYMENT_HEADER as _SDK_PAYMENT_HEADER,
    )

    _HAS_X402_SDK = True
    # Use the SDK's canonical header name if available
    X402_PAYMENT_HEADER = _SDK_PAYMENT_HEADER
except ImportError:
    pass


# Cached x402 server instance (initialized once, reused for all requests)
_cached_server = None
_cached_facilitator_url = None


def _get_cached_server(facilitator_url: str):
    """Return a cached x402ResourceServerSync, creating it on first call."""
    global _cached_server, _cached_facilitator_url
    if _cached_server is None or _cached_facilitator_url != facilitator_url:
        from x402 import x402ResourceServerSync
        from x402.http import HTTPFacilitatorClientSync
        facilitator = HTTPFacilitatorClientSync(base_url=facilitator_url)
        _cached_server = x402ResourceServerSync(facilitator)
        _cached_server.initialize()
        _cached_facilitator_url = facilitator_url
        log.info("x402: Initialized verifier (facilitator=%s)", facilitator_url)
    return _cached_server


def _parse_price_to_dollars(price_str: str) -> str:
    """Convert '$0.001' format to raw decimal string '0.001' for the x402 protocol."""
    return price_str.lstrip("$")


def _build_payment_required_response(
    *,
    price_usd: str,
    pay_to: str,
    network: str,
    facilitator_url: str,
    scheme: str,
    path: str,
    request_id: str,
) -> JSONResponse:
    """Build a 402 Payment Required response (x402 v2 wire format).

    All payment data goes in the base64-encoded ``Payment-Required`` header.
    Body is a minimal human-readable error. This matches the format used by
    all successfully-registered servers on x402scan.
    """
    # USDC on Base
    usdc_asset = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    amount = _parse_price_to_dollars(price_usd)

    payment_required = {
        "x402Version": 2,
        "resource": {
            "url": f"https://bitcoinsapi.com{path}",
            "method": "POST" if "broadcast" in path else "GET",
            "description": f"Satoshi API: {path}",
            "mimeType": "application/json",
        },
        "accepts": [
            {
                "scheme": scheme,
                "network": network,
                "amount": amount,
                "asset": usdc_asset,
                "payTo": pay_to,
                "maxTimeoutSeconds": 300,
                "extra": {
                    "name": "USD Coin",
                    "version": "2",
                    "facilitatorUrl": facilitator_url,
                },
            }
        ],
    }

    header_value = base64.b64encode(
        json.dumps(payment_required, separators=(",", ":")).encode()
    ).decode()

    resp = JSONResponse(
        status_code=402,
        content={
            "error": {
                "status": 402,
                "title": "Payment Required",
                "detail": f"This endpoint costs {price_usd}. "
                f"Send an x402 payment via the {X402_PAYMENT_HEADER} header.",
                "request_id": request_id,
            },
        },
    )
    resp.headers["Payment-Required"] = header_value
    if request_id:
        resp.headers["X-Request-ID"] = request_id
    resp.headers["X-Price-USD"] = price_usd
    return resp


async def _verify_x402_payment(
    payment_header: str,
    *,
    pay_to: str,
    amount_usd: str,
    network: str,
    facilitator_url: str,
    scheme: str,
    resource: str,
) -> tuple[bool, str]:
    """Verify an x402 payment.

    When the x402 SDK is installed, delegates verification to the facilitator.
    Otherwise, accepts the payment header at face value (dev/testing mode).

    Returns:
        (valid, payment_id_or_error) -- True + identifier on success,
        False + error message on failure.
    """
    if _HAS_X402_SDK:
        try:
            from x402 import PaymentRequirementsV1, parse_payment_payload

            server = _get_cached_server(facilitator_url)

            requirements = PaymentRequirementsV1(
                scheme=scheme,
                network=network,
                payTo=pay_to,
                maxAmountRequired=_parse_price_to_dollars(amount_usd),
                resource=resource,
                description=f"Satoshi API: {resource}",
            )

            payload = parse_payment_payload(payment_header)
            result = server.verify(payload, requirements)

            if result.is_valid:
                import hashlib
                pid = hashlib.sha256(payment_header.encode()).hexdigest()[:16]
                return True, f"x402:{pid}"
            return False, result.invalid_reason or "payment verification failed"
        except Exception as e:
            log.warning("x402: SDK verification error: %s", e)
            return False, str(e)
    else:
        # No SDK -- FAIL CLOSED. Do not accept unverified payments.
        log.error(
            "x402 SDK not installed. Cannot verify payments. "
            "Install x402[fastapi] for production use."
        )
        return False, "x402 SDK not installed -- cannot verify payment"


def enable_x402(
    app: FastAPI,
    *,
    pay_to: str = "",
    network: str = "eip155:8453",
    facilitator_url: str = "https://www.x402.org/facilitator",
    scheme: str = "exact",
) -> None:
    """Enable x402 stablecoin micropayments on a FastAPI app.

    Args:
        app: FastAPI application instance.
        pay_to: EVM wallet address (overrides X402_PAY_TO_ADDRESS env var).
        network: EIP-155 chain identifier (default: Base mainnet).
        facilitator_url: x402 facilitator service URL.
        scheme: Payment scheme (default: exact).
    """
    cfg = load_config()

    # Keyword args override env-var config
    _pay_to = pay_to or cfg.pay_to_address
    _network = network if network != "eip155:8453" else cfg.network
    _facilitator_url = (
        facilitator_url
        if facilitator_url != "https://www.x402.org/facilitator"
        else cfg.facilitator_url
    )
    _scheme = scheme if scheme != "exact" else cfg.scheme

    if not _pay_to:
        raise ValueError(
            "x402: No pay-to address configured. "
            "Set X402_PAY_TO_ADDRESS or pass pay_to= to enable_x402()."
        )

    @app.middleware("http")
    async def x402_middleware(request: Request, call_next):
        # 1. If API key present, skip x402 (traditional auth takes priority)
        api_key = request.headers.get("X-API-Key") or request.query_params.get(
            "api_key"
        )
        if api_key:
            return await call_next(request)

        # 2. Look up endpoint price
        price_usd = get_endpoint_price_usd(request.url.path)

        # 3. Free endpoint -- pass through
        if price_usd is None:
            return await call_next(request)

        # 4. Check for x402 payment header
        payment_header = request.headers.get(X402_PAYMENT_HEADER)
        if payment_header:
            valid, payment_id = await _verify_x402_payment(
                payment_header,
                pay_to=_pay_to,
                amount_usd=price_usd,
                network=_network,
                facilitator_url=_facilitator_url,
                scheme=_scheme,
                resource=request.url.path,
            )
            _client_ip = request.client.host if request.client else ""
            _ua = request.headers.get("user-agent", "")
            if valid:
                request.state.tier = "pro"
                request.state.key_hash = f"x402:{payment_id}"
                log.info("x402: Valid payment for %s", request.url.path)
                _log_payment(request.url.path, price_usd, "paid", _client_ip, payment_id, _ua)
                return await call_next(request)
            else:
                log.warning(
                    "x402: Invalid payment for %s: %s",
                    request.url.path,
                    payment_id,
                )
                _log_payment(request.url.path, price_usd, "failed", _client_ip, payment_id, _ua)
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "status": 401,
                            "title": "Payment Invalid",
                            "detail": f"x402 payment verification failed: {payment_id}",
                        }
                    },
                )

        # 5. No payment, priced endpoint -- return 402 with payment requirements
        _client_ip = request.client.host if request.client else ""
        _ua = request.headers.get("user-agent", "")
        _log_payment(request.url.path, price_usd, "challenged", _client_ip, "", _ua)
        request_id = getattr(request.state, "request_id", "")
        return _build_payment_required_response(
            price_usd=price_usd,
            pay_to=_pay_to,
            network=_network,
            facilitator_url=_facilitator_url,
            scheme=_scheme,
            path=request.url.path,
            request_id=request_id,
        )
