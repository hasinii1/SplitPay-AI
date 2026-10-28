import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from app.services.paypal_service import (
    PayPalServiceError,
    get_paypal_access_token,
)


class TestPayPalAuthentication(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_credentials_do_not_fall_back_to_demo_token(self):
        response = httpx.Response(
            401,
            request=httpx.Request(
                "POST",
                "https://api-m.sandbox.paypal.com/v1/oauth2/token",
            ),
        )
        client = Mock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.post = AsyncMock(return_value=response)

        with (
            patch(
                "app.services.paypal_service.get_settings",
                return_value=Mock(
                    is_paypal_configured=True,
                    paypal_api_base="https://api-m.sandbox.paypal.com",
                    paypal_client_id="sandbox-client-id",
                    paypal_client_secret="sandbox-client-secret",
                ),
            ),
            patch("app.services.paypal_service.httpx.AsyncClient", return_value=client),
            patch("app.services.paypal_service._cached_token", None),
            patch("app.services.paypal_service._token_expiry", 0.0),
        ):
            with self.assertRaisesRegex(PayPalServiceError, "authentication failed"):
                await get_paypal_access_token()


if __name__ == "__main__":
    unittest.main()
