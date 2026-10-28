import asyncio
from io import BytesIO
import json
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from app.services.gemini_service import (
    GeminiServiceError,
    extract_receipt_from_image,
    _receipt_extraction_error_message,
    parse_split_instructions,
)
from app.models import ExtractedItem


class TestGeminiReceiptExtraction(unittest.TestCase):
    def test_missing_client_raises_instead_of_returning_demo_receipt(self):
        with patch("app.services.gemini_service._get_gemini_client", return_value=None):
            with self.assertRaises(GeminiServiceError):
                asyncio.run(extract_receipt_from_image(b"receipt"))

    def test_api_failure_raises_instead_of_returning_demo_receipt(self):
        image_bytes = BytesIO()
        Image.new("RGB", (1, 1)).save(image_bytes, format="PNG")
        client = Mock()
        client.models.generate_content.side_effect = RuntimeError("model unavailable")

        with patch("app.services.gemini_service._get_gemini_client", return_value=client):
            with self.assertRaises(GeminiServiceError):
                asyncio.run(
                    extract_receipt_from_image(
                        image_bytes.getvalue(),
                        mime_type="image/png",
                    )
                )

    def test_inr_receipt_currency_and_amounts_are_preserved(self):
        image_bytes = BytesIO()
        Image.new("RGB", (1, 1)).save(image_bytes, format="PNG")
        client = Mock()
        client.models.generate_content.return_value.text = json.dumps({
            "merchant": "Hotel Amer Palace",
            "date": "2021-07-24",
            "currency": "INR",
            "items": [{"name": "Veg Manchaw Soup", "price": 119.0, "quantity": 1}],
            "subtotal": 119.0,
            "tax": 0.0,
            "tip": 0.0,
            "discount": 0.0,
            "total": 119.0,
            "confidence_notes": "Receipt currency identified as INR.",
        })

        with patch("app.services.gemini_service._get_gemini_client", return_value=client):
            receipt = asyncio.run(
                extract_receipt_from_image(
                    image_bytes.getvalue(),
                    mime_type="image/png",
                )
            )

        self.assertEqual(receipt.currency, "INR")
        self.assertEqual(receipt.items[0].price, 119.0)
        self.assertEqual(receipt.total, 119.0)

    def test_api_error_detail_is_preserved_without_exposing_request_details(self):
        error = RuntimeError("unavailable")
        error.code = 503
        error.status = "UNAVAILABLE"
        error.message = "Model is temporarily overloaded."

        message = _receipt_extraction_error_message(error)

        self.assertEqual(
            message,
            "Gemini API error (503 UNAVAILABLE): Model is temporarily overloaded.",
        )

    def test_instruction_parse_uses_demo_participants_when_gemini_is_unreachable(self):
        client = Mock()
        client.models.generate_content.side_effect = OSError(
            "[Errno 11001] getaddrinfo failed"
        )
        items = [
            ExtractedItem(name="Wood-Fired Margherita Pizza", price=16.50),
            ExtractedItem(name="Fettuccine Alfredo with Truffle", price=22.00),
        ]

        with patch("app.services.gemini_service._get_gemini_client", return_value=client):
            result = asyncio.run(
                parse_split_instructions(
                    "Split everything equally among Alice, Bob, and Charlie.",
                    items,
                )
            )

        self.assertEqual(result.people_found, ["Alice", "Bob", "Charlie"])
        self.assertEqual(
            [assignment.consumers for assignment in result.assignments],
            [["Alice", "Bob", "Charlie"], ["Alice", "Bob", "Charlie"]],
        )
        self.assertNotIn("getaddrinfo", result.ai_summary)
        self.assertIn("Gemini could not be reached", result.ai_summary)


if __name__ == "__main__":
    unittest.main()
