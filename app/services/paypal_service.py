"""
PayPal Service for SplitPay AI
Integrates with PayPal Sandbox Orders v2 API:
- OAuth 2.0 client credentials token caching with TTL buffer
- Order creation with CAPTURE intent, idempotency header (PayPal-Request-Id)
- Locating payer-action / approve URL
- Capturing authorized orders on return redirect
- Table-side QR code generation
- Graceful sandbox mock mode when credentials are not configured
"""

import time
import uuid
import logging
from datetime import date
from urllib.parse import urlencode
from typing import Optional, Dict, Any, List
import httpx

from app.config import get_settings
from app.database import update_paypal_order, mark_share_paid

logger = logging.getLogger(__name__)

DEFAULT_USD_TO_INR_RATE = 85.0
EXCHANGE_RATE_URL = "https://api.frankfurter.dev/v1/latest"
_cached_usd_to_inr_rate: Optional[float] = None
_cached_exchange_rate_date: Optional[str] = None
_exchange_rate_expires_at = 0.0


class PayPalServiceError(RuntimeError):
    """Raised when PayPal cannot create or process an order."""


def convert_to_paypal_usd(
    amount: float,
    source_currency: str,
    usd_to_inr_rate: Optional[float] = None,
) -> float:
    """Convert app-denominated share amounts to PayPal's supported USD amount.

    Prefer the live/cached exchange rate when available, but retain a stable fallback
    so INR bills still convert cleanly when the rate lookup is unavailable or slow.
    """
    if source_currency == "USD":
        return round(amount, 2)
    if source_currency == "INR":
        resolved_rate = usd_to_inr_rate
        if resolved_rate is None:
            resolved_rate = _cached_usd_to_inr_rate or DEFAULT_USD_TO_INR_RATE
        if resolved_rate <= 0:
            raise ValueError("A positive USD-to-INR exchange rate is required.")
        return round(amount / resolved_rate, 2)
    raise ValueError(f"Unsupported source currency: {source_currency}")


async def get_usd_to_inr_exchange_rate() -> Dict[str, Any]:
    """Fetch and briefly cache the latest reference USD/INR exchange rate."""
    global _cached_usd_to_inr_rate, _cached_exchange_rate_date, _exchange_rate_expires_at
    now = time.monotonic()
    if (
        _cached_usd_to_inr_rate is not None
        and _cached_exchange_rate_date
        and now < _exchange_rate_expires_at
    ):
        return {
            "base": "USD",
            "quote": "INR",
            "rate": _cached_usd_to_inr_rate,
            "date": _cached_exchange_rate_date,
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                EXCHANGE_RATE_URL,
                params={"base": "USD", "symbols": "INR"},
            )
            response.raise_for_status()
            data = response.json()
            rate = float(data["rates"]["INR"])
            rate_date = str(data["date"])
            date.fromisoformat(rate_date)
            if rate <= 0:
                raise ValueError("Exchange rate must be positive.")
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as e:
        logger.exception("Could not retrieve a valid USD/INR exchange rate.")
        raise PayPalServiceError(
            "Could not retrieve the latest USD/INR reference rate. Please try again."
        ) from e

    _cached_usd_to_inr_rate = rate
    _cached_exchange_rate_date = rate_date
    _exchange_rate_expires_at = now + 3600
    return {
        "base": "USD",
        "quote": "INR",
        "rate": rate,
        "date": rate_date,
    }


def _build_callback_url(path: str, **params: str) -> str:
    settings = get_settings()
    query = urlencode(params)
    return f"{settings.app_base_url.rstrip('/')}{path}?{query}"


# In-memory OAuth token cache
_cached_token: Optional[str] = None
_token_expiry: float = 0.0


async def get_paypal_access_token() -> str:
    """
    Retrieves a cached PayPal OAuth 2.0 access token or requests a new one
    using client credentials.
    """
    global _cached_token, _token_expiry
    now = time.time()

    # Reuse cached token if valid for at least another 60 seconds
    if _cached_token and now < (_token_expiry - 60):
        return _cached_token

    settings = get_settings()
    if not settings.is_paypal_configured:
        logger.warning("PayPal credentials not set in .env. Using mock sandbox token.")
        _cached_token = f"mock-token-{uuid.uuid4().hex[:8]}"
        _token_expiry = now + 3600
        return _cached_token

    token_url = f"{settings.paypal_api_base}/v1/oauth2/token"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                token_url,
                data={"grant_type": "client_credentials"},
                auth=(settings.paypal_client_id, settings.paypal_client_secret),
                headers={"Accept": "application/json", "Accept-Language": "en_US"},
            )
            response.raise_for_status()
            data = response.json()
            _cached_token = data["access_token"]
            expires_in = data.get("expires_in", 32400)
            _token_expiry = now + expires_in
            logger.info("Successfully fetched new PayPal OAuth token.")
            return _cached_token
        except httpx.HTTPStatusError as e:
            logger.error("PayPal OAuth failed with HTTP %s.", e.response.status_code)
            raise PayPalServiceError(
                f"PayPal authentication failed (HTTP {e.response.status_code}). "
                "Verify your Sandbox app credentials."
            ) from e
        except httpx.RequestError as e:
            logger.exception("Could not connect to PayPal OAuth.")
            raise PayPalServiceError(
                "Could not connect to PayPal authentication. Check your internet connection and try again."
            ) from e


def generate_qr_data_url(text: str) -> str:
    """
    Generates a base64 Data URI for a QR code representing the PayPal payment URL.
    Attempts to use the 'qrcode' library, with a clean SVG fallback.
    """
    try:
        import qrcode
        import io
        import base64

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#003087", back_color="white")  # PayPal blue

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    except Exception as e:
        # Client-side QR generator will render from text if data url is empty
        logger.debug(f"Server-side QR generation skipped: {e}")
        return ""


async def create_paypal_order_for_person(
    bill_id: str,
    person: str,
    merchant: str,
    amount: float,
    assigned_items: List[Dict[str, Any]],
    currency: str = "USD",
) -> Dict[str, Any]:
    """
    Creates a PayPal Orders v2 Order with CAPTURE intent for a specific person's share.
    Includes idempotency key header, return and cancel URLs, and extracts the approve link.
    """
    settings = get_settings()
    token = await get_paypal_access_token()

    # Form unique idempotency key
    idempotency_key = f"splitpay-{bill_id}-{person.replace(' ', '_')}-{uuid.uuid4().hex[:8]}"

    # Fallback mock order if credentials not configured or demo token
    if not settings.is_paypal_configured or token.startswith("mock-token-"):
        mock_order_id = f"SANDBOX-ORD-{uuid.uuid4().hex[:10].upper()}"
        mock_approve_url = _build_callback_url(
            "/api/paypal/mock-approve",
            order_id=mock_order_id,
            bill_id=bill_id,
            person=person,
            amount=f"{amount:.2f}",
            currency=currency,
        )
        qr_code = generate_qr_data_url(mock_approve_url)

        update_paypal_order(
            bill_id=bill_id,
            person=person,
            paypal_order_id=mock_order_id,
            paypal_approval_url=mock_approve_url,
            qr_code_data=qr_code,
            paypal_amount=amount,
            paypal_currency=currency,
        )

        return {
            "order_id": mock_order_id,
            "approval_url": mock_approve_url,
            "status": "CREATED",
            "qr_code_data": qr_code,
            "is_mock": True,
        }

    orders_url = f"{settings.paypal_api_base}/v2/checkout/orders"
    return_url = _build_callback_url(
        "/api/paypal/return",
        bill_id=bill_id,
        person=person,
    )
    cancel_url = _build_callback_url(
        "/api/paypal/cancel",
        bill_id=bill_id,
        person=person,
    )

    item_names = [it.get("item_name", "Item") for it in assigned_items]
    description = f"{person}'s share at {merchant}: {', '.join(item_names)[:100]}"

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": f"{bill_id}:{person}",
                "description": description,
                "amount": {
                    "currency_code": currency,
                    "value": f"{amount:.2f}",
                },
            }
        ],
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                    "brand_name": "SplitPay AI",
                    "locale": "en-US",
                    "landing_page": "LOGIN",
                    "shipping_preference": "NO_SHIPPING",
                    "user_action": "PAY_NOW",
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                }
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "PayPal-Request-Id": idempotency_key,
        "Prefer": "return=representation",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(orders_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            order_id = data["id"]
            status = data.get("status", "CREATED")

            # Find payer approval link
            approval_url = None
            for link in data.get("links", []):
                if link.get("rel") in ("approve", "payer-action"):
                    approval_url = link.get("href")
                    break

            if not approval_url:
                raise PayPalServiceError(
                    "PayPal created the order but did not return an approval link."
                )

            qr_code = generate_qr_data_url(approval_url)

            # Persist to database
            update_paypal_order(
                bill_id=bill_id,
                person=person,
                paypal_order_id=order_id,
                paypal_approval_url=approval_url,
                qr_code_data=qr_code,
                paypal_amount=amount,
                paypal_currency=currency,
            )

            return {
                "order_id": order_id,
                "approval_url": approval_url,
                "status": status,
                "qr_code_data": qr_code,
                "is_mock": False,
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"PayPal create order failed: {e.response.status_code} - {e.response.text}")
            try:
                error_data = e.response.json()
            except ValueError:
                error_data = {}
            message = error_data.get("message") or error_data.get("error_description") or e.response.text
            raise PayPalServiceError(
                f"PayPal returned HTTP {e.response.status_code}: {message}"
            ) from e
        except httpx.RequestError as e:
            logger.exception("Could not connect to PayPal Orders v2.")
            raise PayPalServiceError(
                "Could not connect to PayPal. Check your internet connection and try again."
            ) from e


async def capture_paypal_order(order_id: str) -> Dict[str, Any]:
    """
    Captures payment for an approved PayPal order.
    Updates the database record to mark the person's share as PAID.
    """
    settings = get_settings()

    # Handle mock order capture in demo mode
    if order_id.startswith("SANDBOX-ORD-") or not settings.is_paypal_configured:
        mark_share_paid(order_id)
        return {
            "order_id": order_id,
            "status": "COMPLETED",
            "capture_id": f"MOCK-CAP-{uuid.uuid4().hex[:8]}",
            "message": "Payment captured successfully (Sandbox Demo mode).",
        }

    token = await get_paypal_access_token()
    capture_url = f"{settings.paypal_api_base}/v2/checkout/orders/{order_id}/capture"
    idempotency_key = f"capture-{order_id}-{uuid.uuid4().hex[:6]}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "PayPal-Request-Id": idempotency_key,
        "Prefer": "return=representation",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(capture_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            status = data.get("status", "COMPLETED")
            capture_id = None
            try:
                capture_id = data["purchase_units"][0]["payments"]["captures"][0]["id"]
            except (KeyError, IndexError):
                pass

            if status in ("COMPLETED", "APPROVED"):
                mark_share_paid(order_id)

            return {
                "order_id": order_id,
                "status": status,
                "capture_id": capture_id,
                "message": f"Order status is {status}.",
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"PayPal capture failed: {e.response.status_code} - {e.response.text}")
            # If already captured, mark paid anyway
            if "ORDER_ALREADY_CAPTURED" in e.response.text:
                mark_share_paid(order_id)
                return {
                    "order_id": order_id,
                    "status": "COMPLETED",
                    "message": "Order was previously captured.",
                }
            raise RuntimeError(f"Capture failed: {e.response.text}")


async def get_order_details(order_id: str) -> Dict[str, Any]:
    """Fetches real-time status of a PayPal order."""
    settings = get_settings()
    if order_id.startswith("SANDBOX-ORD-") or not settings.is_paypal_configured:
        return {"id": order_id, "status": "COMPLETED"}

    token = await get_paypal_access_token()
    url = f"{settings.paypal_api_base}/v2/checkout/orders/{order_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
