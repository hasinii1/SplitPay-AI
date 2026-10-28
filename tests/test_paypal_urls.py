import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from app.services.paypal_service import (
    _build_callback_url,
    convert_to_paypal_usd,
)


class TestPayPalCallbackUrls(unittest.TestCase):
    @patch("app.services.paypal_service.get_settings")
    def test_callback_query_encodes_person_names(self, get_settings):
        get_settings.return_value = Mock(app_base_url="http://localhost:8000/")

        url = _build_callback_url(
            "/api/paypal/return",
            bill_id="test-bill",
            person="Friend 1 & Co",
        )
        parsed = urlsplit(url)

        self.assertEqual(parsed.netloc, "localhost:8000")
        self.assertNotIn(" ", url)
        self.assertEqual(
            parse_qs(parsed.query),
            {"bill_id": ["test-bill"], "person": ["Friend 1 & Co"]},
        )

    def test_inr_amount_converts_to_paypal_usd(self):
        self.assertEqual(convert_to_paypal_usd(8500.0, "INR"), 100.0)

    def test_usd_amount_remains_unchanged(self):
        self.assertEqual(convert_to_paypal_usd(12.34, "USD"), 12.34)

    def test_unsupported_paypal_currency_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported source currency"):
            convert_to_paypal_usd(100.0, "EUR")


if __name__ == "__main__":
    unittest.main()
