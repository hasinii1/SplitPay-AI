import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from app.services.paypal_service import (
    PayPalServiceError,
    get_usd_to_inr_exchange_rate,
)


class TestExchangeRate(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_latest_usd_inr_reference_rate(self):
        response = Mock()
        response.json.return_value = {
            "base": "USD",
            "date": "2026-10-27",
            "rates": {"INR": 95.12},
        }
        response.raise_for_status = Mock()
        client = Mock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.get = AsyncMock(return_value=response)

        with (
            patch("app.services.paypal_service.httpx.AsyncClient", return_value=client),
            patch("app.services.paypal_service._cached_usd_to_inr_rate", None),
            patch("app.services.paypal_service._cached_exchange_rate_date", None),
            patch("app.services.paypal_service._exchange_rate_expires_at", 0.0),
        ):
            result = await get_usd_to_inr_exchange_rate()

        self.assertEqual(result["rate"], 95.12)
        self.assertEqual(result["date"], "2026-10-27")
        client.get.assert_awaited_once()

    async def test_exchange_provider_failure_is_reported(self):
        client = Mock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.get = AsyncMock(
            side_effect=httpx.ConnectError("network unavailable")
        )

        with (
            patch("app.services.paypal_service.httpx.AsyncClient", return_value=client),
            patch("app.services.paypal_service._cached_usd_to_inr_rate", None),
            patch("app.services.paypal_service._cached_exchange_rate_date", None),
            patch("app.services.paypal_service._exchange_rate_expires_at", 0.0),
        ):
            with self.assertRaisesRegex(PayPalServiceError, "latest USD/INR"):
                await get_usd_to_inr_exchange_rate()


if __name__ == "__main__":
    unittest.main()
