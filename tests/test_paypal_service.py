"""
Tests for PayPal integration data flows, database statuses, and order lifecycle.
"""

import unittest
import uuid
import os
import tempfile
from unittest.mock import patch
from app.database import (
    init_db,
    get_connection,
    create_bill,
    update_paypal_order,
    mark_share_paid,
    get_bill,
    save_shares,
)


class TestPayPalDatabaseFlow(unittest.TestCase):

    def setUp(self):
        self.database_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.database_dir.name, "test_splitpay.db")
        self.database_path_patcher = patch(
            "app.database.get_db_path",
            return_value=self.database_path,
        )
        self.database_path_patcher.start()
        init_db()

    def tearDown(self):
        self.database_path_patcher.stop()
        self.database_dir.cleanup()

    def test_order_creation_and_mark_paid(self):
        # 1. Create a bill
        bill_id = create_bill(
            merchant="Mario's Pizza",
            date="2026-10-26",
            subtotal=30.0,
            tax=3.0,
            tip=6.0,
            discount=0.0,
            total=39.0,
            items=[{"name": "Pizza", "price": 30.0, "consumers": ["Alice"]}],
            currency="INR",
        )
        self.assertIsNotNone(bill_id)

        # 2. Simulate saving a share
        save_shares(bill_id, {
            "Alice": {
                "items_subtotal": 30.0,
                "tax": 3.0,
                "tip": 6.0,
                "discount": 0.0,
                "total": 39.0,
                "status": "PENDING"
            }
        })

        # 3. Simulate updating with PayPal Order details
        mock_order_id = f"SANDBOX-ORD-{uuid.uuid4().hex[:8]}"
        mock_approve_url = "https://www.sandbox.paypal.com/checkoutnow?token=TEST"
        update_paypal_order(
            bill_id=bill_id,
            person="Alice",
            paypal_order_id=mock_order_id,
            paypal_approval_url=mock_approve_url,
            qr_code_data="",
            paypal_amount=0.46,
            paypal_currency="USD",
        )

        bill = get_bill(bill_id)
        self.assertEqual(bill["currency"], "INR")
        self.assertEqual(bill["status"], "PENDING_PAYMENT")
        alice_share = [s for s in bill["shares"] if s["person"] == "Alice"][0]
        self.assertEqual(alice_share["paypal_order_id"], mock_order_id)
        self.assertEqual(alice_share["paypal_amount"], 0.46)
        self.assertEqual(alice_share["paypal_currency"], "USD")
        self.assertEqual(alice_share["status"], "PENDING")

        # 4. Simulate payment capture on return
        result = mark_share_paid(mock_order_id)
        self.assertIsNotNone(result)

        updated_bill = get_bill(bill_id)
        updated_alice = [s for s in updated_bill["shares"] if s["person"] == "Alice"][0]
        self.assertEqual(updated_alice["status"], "PAID")
        self.assertIsNotNone(updated_alice["paid_at"])
        # Bill should now be COMPLETED since Alice was the sole participant
        self.assertEqual(updated_bill["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
