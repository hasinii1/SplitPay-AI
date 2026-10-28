import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from app.database import (
    create_bill,
    mark_share_paid,
    save_shares,
    update_paypal_order,
)
from app.main import app


class TestPayPalReturnDashboard(unittest.TestCase):
    def setUp(self):
        self.database_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.database_dir.name, "test_splitpay.db")
        self.database_path_patcher = patch(
            "app.database.get_db_path",
            return_value=self.database_path,
        )
        self.database_path_patcher.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.database_path_patcher.stop()
        self.database_dir.cleanup()

    def test_return_captures_payment_and_redirects_to_same_bill(self):
        bill_id = create_bill(
            merchant="Cafe",
            date="2026-10-27",
            subtotal=100.0,
            tax=5.0,
            tip=0.0,
            discount=0.0,
            total=105.0,
            items=[{"name": "Lunch", "price": 100.0, "consumers": ["Ravi"]}],
            currency="INR",
        )
        save_shares(
            bill_id,
            {
                "Ravi": {
                    "items_subtotal": 100.0,
                    "tax": 5.0,
                    "tip": 0.0,
                    "discount": 0.0,
                    "total": 105.0,
                    "assigned_items": [
                        {
                            "item_name": "Lunch",
                            "share_dollars": 100.0,
                            "split_with": ["Ravi"],
                        }
                    ],
                }
            },
        )
        order_id = "SANDBOX-ORD-TEST123"
        update_paypal_order(
            bill_id=bill_id,
            person="Ravi",
            paypal_order_id=order_id,
            paypal_approval_url="https://example.test/approve",
            paypal_amount=1.05,
        )

        async def capture_mock_order(paypal_order_id):
            mark_share_paid(paypal_order_id)
            return {"status": "COMPLETED"}

        with patch("app.main.capture_paypal_order", side_effect=capture_mock_order):
            response = self.client.get(
                "/api/paypal/return",
                params={
                    "token": order_id,
                    "bill_id": bill_id,
                    "person": "Ravi",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        redirect = urlsplit(response.headers["location"])
        self.assertEqual(
            parse_qs(redirect.query),
            {"bill_id": [bill_id], "payment": ["success"], "person": ["Ravi"]},
        )

        bill_response = self.client.get(f"/api/bills/{bill_id}")
        self.assertEqual(bill_response.status_code, 200)
        bill_data = bill_response.json()
        self.assertEqual(bill_data["currency"], "INR")
        self.assertEqual(bill_data["shares"][0]["person"], "Ravi")
        self.assertEqual(bill_data["shares"][0]["status"], "PAID")


if __name__ == "__main__":
    unittest.main()
