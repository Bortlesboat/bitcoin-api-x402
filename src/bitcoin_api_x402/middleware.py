"""FastAPI middleware for x402 stablecoin micropayments."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import load_config
from .pricing import get_endpoint_price_usd

log = logging.getLogger(__name__)

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
    """Build a 402 Payment Required response with x402 payment requirements."""
    amount = _parse_price_to_dollars(price_usd)

    payment_requirements = {
        "x402Version": 1,
        "scheme": scheme,
        "network": network,
        "payTo": pay_to,
        "maxAmountRequired": amount,
        "resource": path,
        "description": f"Satoshi API: {path}",
        "mimeType": "application/json",
        "outputSchema": None,
        "extra": {
            "facilitatorUrl": facilitator_url,
        },
    }

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
            "paymentRequirements": payment_requirements,
        },
    )
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
            from x402 import (
                x402ResourceServerSync,
                PaymentRequirementsV1,
                parse_payment_payload,
            )
            from x402.http import HTTPFacilitatorClientSync

            facilitator = HTTPFacilitatorClientSync(base_url=facilitator_url)
            server = x402ResourceServerSync(facilitator)
            server.initialize()

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
                return True, f"x402:{hash(payment_header) & 0xFFFFFFFF:08x}"
            return False, result.invalid_reason or "payment verification failed"
        except Exception as e:
            log.warning("x402: SDK verification error: %s", e)
            return False, str(e)
    else:
        # No SDK -- accept payment header presence for dev/testing
        log.warning(
            "x402 SDK not available; accepting payment header at face value. "
            "Install x402[fastapi] for production use."
        )
        return True, "x402-dev"


def enable_x402(
    app: FastAPI,
    *,
    pay_to: str = "",
    network: str = "eip155:8453",
    facilitator_url: str = "https://x402.org/facilitator",
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
        if facilitator_url != "https://x402.org/facilitator"
        else cfg.facilitator_url
    )
    _scheme = scheme if scheme != "exact" else cfg.scheme

    if not _pay_to:
        log.warning(
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
            if valid:
                request.state.tier = "pro"
                request.state.key_hash = f"x402:{payment_id}"
                log.info("x402: Valid payment for %s", request.url.path)
                return await call_next(request)
            else:
                log.warning(
                    "x402: Invalid payment for %s: %s",
                    request.url.path,
                    payment_id,
                )
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
