"""
Unit tests for the Deterministic Split Engine.
Verifies integer-cent precision, proportional tax/tip, and Largest Remainder penny distribution.
Runs with pytest or python -m unittest.
"""

import unittest
from app.services.split_engine import (
    to_cents,
    to_dollars,
    largest_remainder_distribute,
    ItemInput,
    calculate_split,
)


class TestSplitEngine(unittest.TestCase):

    def test_to_cents_and_dollars(self):
        self.assertEqual(to_cents(10.00), 1000)
        self.assertEqual(to_cents("15.75"), 1575)
        self.assertEqual(to_cents(0.01), 1)
        self.assertEqual(to_cents("0.009"), 1)  # rounds to 1 cent
        self.assertEqual(to_dollars(1575), 15.75)
        self.assertEqual(to_dollars(1000), 10.00)

    def test_largest_remainder_distribution_sum(self):
        # 100 cents distributed across 3 equal weights
        weights = {"Alice": 10, "Bob": 10, "Charlie": 10}
        distributed = largest_remainder_distribute(100, weights)
        self.assertEqual(sum(distributed.values()), 100)
        # 100 / 3 = 33.33 -> Two get 33, one gets 34
        self.assertEqual(sorted(list(distributed.values())), [33, 33, 34])

    def test_three_way_split_exact_ten_dollars(self):
        # $10.00 item split 3 ways: 333 + 333 + 334 = 1000 cents ($10.00)
        items = [ItemInput(name="Pizza", price=10.00, consumers=["Alice", "Bob", "Charlie"])]
        result = calculate_split(items=items, tax=0.00, tip=0.00)

        self.assertTrue(result.is_balanced)
        self.assertEqual(result.total_cents, 1000)
        individual_sum = sum(s.total_cents for s in result.shares.values())
        self.assertEqual(individual_sum, 1000)
        self.assertEqual(result.total, 10.00)

    def test_proportional_tax_and_tip(self):
        # Alice orders $10 item, Bob orders $20 item. Total items = $30.
        # Tax = $3.00, Tip = $6.00.
        # Bob's items are 2x Alice's -> Bob must pay 2x tax ($2.00 vs $1.00) and 2x tip ($4.00 vs $2.00).
        items = [
            ItemInput(name="Salad", price=10.00, consumers=["Alice"]),
            ItemInput(name="Steak", price=20.00, consumers=["Bob"]),
        ]
        result = calculate_split(items=items, tax=3.00, tip=6.00)

        self.assertTrue(result.is_balanced)
        alice = result.shares["Alice"]
        bob = result.shares["Bob"]

        self.assertEqual(alice.items_subtotal, 10.00)
        self.assertEqual(alice.tax, 1.00)
        self.assertEqual(alice.tip, 2.00)
        self.assertEqual(alice.total, 13.00)

        self.assertEqual(bob.items_subtotal, 20.00)
        self.assertEqual(bob.tax, 2.00)
        self.assertEqual(bob.tip, 4.00)
        self.assertEqual(bob.total, 26.00)

        self.assertEqual(result.total, 39.00)
        self.assertEqual(alice.total + bob.total, 39.00)

    def test_complex_shared_bill_with_penny_reconciliation(self):
        # Real-world scenario:
        # - Shared Nachos: $14.99 (Alice, Bob, Carol)
        # - Burger: $12.50 (Alice)
        # - Salmon: $21.75 (Bob)
        # - Pasta: $16.20 (Carol)
        # - Tax: $5.83
        # - Tip: $12.00
        # - Discount: $5.00 coupon
        items = [
            ItemInput(name="Nachos", price=14.99, consumers=["Alice", "Bob", "Carol"]),
            ItemInput(name="Burger", price=12.50, consumers=["Alice"]),
            ItemInput(name="Salmon", price=21.75, consumers=["Bob"]),
            ItemInput(name="Pasta", price=16.20, consumers=["Carol"]),
        ]
        result = calculate_split(items=items, tax=5.83, tip=12.00, discount=5.00)

        self.assertTrue(result.is_balanced)
        shares_cents = [s.total_cents for s in result.shares.values()]
        self.assertEqual(sum(shares_cents), result.total_cents)

        # Total items: 14.99 + 12.50 + 21.75 + 16.20 = 65.44 (6544 cents)
        # Tax: 583 cents
        # Tip: 1200 cents
        # Discount: 500 cents
        # Total expected: 6544 + 583 + 1200 - 500 = 7827 cents ($78.27)
        self.assertEqual(result.total_cents, 7827)
        self.assertEqual(result.total, 78.27)
        self.assertEqual(sum(shares_cents), 7827)

    def test_zero_tax_tip_discount(self):
        items = [
            ItemInput(name="Coffee", price=4.50, consumers=["Dave"]),
            ItemInput(name="Bagel", price=3.50, consumers=["Dave"]),
        ]
        result = calculate_split(items=items, tax=0.0, tip=0.0, discount=0.0)
        self.assertTrue(result.is_balanced)
        self.assertEqual(result.shares["Dave"].total, 8.00)
        self.assertEqual(result.total, 8.00)

    def test_override_total_reconciliation(self):
        # Printed total on receipt is $20.00, but items only sum to $18.00 (e.g. unlisted service fee)
        items = [
            ItemInput(name="Burger", price=9.00, consumers=["Alice"]),
            ItemInput(name="Pasta", price=9.00, consumers=["Bob"]),
        ]
        result = calculate_split(items=items, tax=0.0, tip=0.0, override_total=20.00)
        self.assertTrue(result.is_balanced)
        self.assertEqual(result.total_cents, 2000)
        self.assertEqual(result.shares["Alice"].total, 10.00)
        self.assertEqual(result.shares["Bob"].total, 10.00)

    def test_ten_way_one_dollar_split(self):
        # 100 cents split 3 ways: 34, 33, 33
        items = [
            ItemInput(name="Shared Drink", price=1.00, consumers=[f"Friend{i}" for i in range(3)])
        ]
        result = calculate_split(items=items)
        self.assertTrue(result.is_balanced)
        self.assertEqual(result.total_cents, 100)
        values = sorted([s.total_cents for s in result.shares.values()])
        self.assertEqual(values, [33, 33, 34])
        self.assertEqual(sum(values), 100)


if __name__ == "__main__":
    unittest.main()
