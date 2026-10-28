"""
Deterministic Split Engine
==========================
Uses integer-cent arithmetic and the Hare-Niemeyer (Largest Remainder) method
to ensure that item shares, tax, tip, and discounts sum EXACTLY to the receipt total.
No floating point rounding errors or lost pennies.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP


def to_cents(amount: float | str | int | Decimal) -> int:
    """Converts a dollar amount to integer cents safely."""
    if isinstance(amount, int):
        return amount
    d = Decimal(str(amount))
    return int((d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_dollars(cents: int) -> float:
    """Converts integer cents to a standard float dollar value."""
    return round(cents / 100.0, 2)


def largest_remainder_distribute(total_cents: int, weights: Dict[str, int]) -> Dict[str, int]:
    """
    Distributes an integer pool of cents across participants based on integer weights
    using the Hare-Niemeyer (Largest Remainder) algorithm.
    Guarantees sum(distributed) == total_cents.
    """
    if total_cents == 0:
        return {k: 0 for k in weights}

    total_weight = sum(weights.values())
    if total_weight == 0:
        # Equal split fallback if all weights are zero
        n = len(weights)
        if n == 0:
            return {}
        base = total_cents // n
        rem = total_cents % n
        result = {}
        for idx, (k, _) in enumerate(sorted(weights.items())):
            result[k] = base + (1 if idx < rem else 0)
        return result

    # 1. Compute exact fractional quotas and integer floors
    floors: Dict[str, int] = {}
    remainders: List[tuple[Decimal, str]] = []
    allocated_sum = 0

    for person, weight in weights.items():
        quota = (Decimal(weight) * Decimal(total_cents)) / Decimal(total_weight)
        floor_val = int(quota)
        rem = quota - Decimal(floor_val)
        floors[person] = floor_val
        allocated_sum += floor_val
        remainders.append((rem, person))

    # 2. Distribute remaining cents to highest remainders
    # Tie-break deterministically by person name ascending
    remainders.sort(key=lambda x: (-x[0], x[1]))
    cents_left = total_cents - allocated_sum

    for i in range(cents_left):
        person_to_bump = remainders[i][1]
        floors[person_to_bump] += 1

    return floors


@dataclass
class ItemInput:
    name: str
    price: float | int  # In dollars or cents (auto-detected or flag)
    consumers: List[str]
    is_cents: bool = False


@dataclass
class PersonShare:
    person: str
    items_subtotal_cents: int
    tax_cents: int
    tip_cents: int
    discount_cents: int
    total_cents: int
    assigned_items: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def items_subtotal(self) -> float:
        return to_dollars(self.items_subtotal_cents)

    @property
    def tax(self) -> float:
        return to_dollars(self.tax_cents)

    @property
    def tip(self) -> float:
        return to_dollars(self.tip_cents)

    @property
    def discount(self) -> float:
        return to_dollars(self.discount_cents)

    @property
    def total(self) -> float:
        return to_dollars(self.total_cents)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "person": self.person,
            "items_subtotal": self.items_subtotal,
            "tax": self.tax,
            "tip": self.tip,
            "discount": self.discount,
            "total": self.total,
            "items_subtotal_cents": self.items_subtotal_cents,
            "tax_cents": self.tax_cents,
            "tip_cents": self.tip_cents,
            "discount_cents": self.discount_cents,
            "total_cents": self.total_cents,
            "assigned_items": self.assigned_items,
        }


@dataclass
class SplitResult:
    shares: Dict[str, PersonShare]
    total_items_cents: int
    tax_cents: int
    tip_cents: int
    discount_cents: int
    total_cents: int
    is_balanced: bool

    @property
    def total(self) -> float:
        return to_dollars(self.total_cents)

    @property
    def total_items(self) -> float:
        return to_dollars(self.total_items_cents)

    @property
    def tax(self) -> float:
        return to_dollars(self.tax_cents)

    @property
    def tip(self) -> float:
        return to_dollars(self.tip_cents)

    @property
    def discount(self) -> float:
        return to_dollars(self.discount_cents)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shares": {k: v.to_dict() for k, v in self.shares.items()},
            "total_items": to_dollars(self.total_items_cents),
            "tax": to_dollars(self.tax_cents),
            "tip": to_dollars(self.tip_cents),
            "discount": to_dollars(self.discount_cents),
            "total": to_dollars(self.total_cents),
            "total_items_cents": self.total_items_cents,
            "tax_cents": self.tax_cents,
            "tip_cents": self.tip_cents,
            "discount_cents": self.discount_cents,
            "total_cents": self.total_cents,
            "is_balanced": self.is_balanced,
        }


def calculate_split(
    items: List[ItemInput],
    tax: float | int = 0.0,
    tip: float | int = 0.0,
    discount: float | int = 0.0,
    is_cents: bool = False,
    override_total: Optional[float | int] = None,
) -> SplitResult:
    """
    Computes exact individual shares with proportional tax and tip.
    Every penny is accounted for using integer largest-remainder distribution.
    """
    tax_cents = tax if is_cents else to_cents(tax)
    tip_cents = tip if is_cents else to_cents(tip)
    discount_cents = discount if is_cents else to_cents(discount)

    # 1. Collect all distinct participants
    participants = set()
    for it in items:
        for c in it.consumers:
            clean_c = c.strip()
            if clean_c:
                participants.add(clean_c)

    # If no participants assigned, return empty result
    if not participants:
        return SplitResult(
            shares={},
            total_items_cents=0,
            tax_cents=tax_cents,
            tip_cents=tip_cents,
            discount_cents=discount_cents,
            total_cents=tax_cents + tip_cents - discount_cents,
            is_balanced=True,
        )

    # 2. Divide each item among its assigned consumers down to the exact cent
    person_item_cents: Dict[str, int] = {p: 0 for p in participants}
    person_assigned_items: Dict[str, List[Dict[str, Any]]] = {p: [] for p in participants}
    total_items_cents = 0

    for item in items:
        price_cents = item.price if item.is_cents else to_cents(item.price)
        total_items_cents += price_cents
        consumers = [c.strip() for c in item.consumers if c.strip()]

        if not consumers:
            # Unassigned item, skip or ignore for now
            continue

        k = len(consumers)
        base_cents = price_cents // k
        remainder_cents = price_cents % k

        # Sort consumers deterministically so distribution is stable
        sorted_consumers = sorted(consumers)
        for idx, consumer in enumerate(sorted_consumers):
            extra = 1 if idx < remainder_cents else 0
            share_c = base_cents + extra
            person_item_cents[consumer] += share_c
            person_assigned_items[consumer].append({
                "item_name": item.name,
                "item_total_cents": price_cents,
                "share_cents": share_c,
                "share_dollars": to_dollars(share_c),
                "split_with": consumers,
            })

    # 3. Distribute Tax proportionally using Largest Remainder
    tax_shares = largest_remainder_distribute(tax_cents, person_item_cents)

    # 4. Distribute Tip proportionally using Largest Remainder
    tip_shares = largest_remainder_distribute(tip_cents, person_item_cents)

    # 5. Distribute Discount proportionally using Largest Remainder
    discount_shares = largest_remainder_distribute(discount_cents, person_item_cents)

    # 6. Assemble each person's total and verify penny balance
    shares: Dict[str, PersonShare] = {}
    sum_individual_totals = 0

    for p in sorted(participants):
        p_sub = person_item_cents[p]
        p_tax = tax_shares.get(p, 0)
        p_tip = tip_shares.get(p, 0)
        p_disc = discount_shares.get(p, 0)
        p_tot = p_sub + p_tax + p_tip - p_disc

        shares[p] = PersonShare(
            person=p,
            items_subtotal_cents=p_sub,
            tax_cents=p_tax,
            tip_cents=p_tip,
            discount_cents=p_disc,
            total_cents=p_tot,
            assigned_items=person_assigned_items[p],
        )
        sum_individual_totals += p_tot

    expected_total_cents = total_items_cents + tax_cents + tip_cents - discount_cents

    # If an override total was specified (e.g. receipt total includes unlisted small fee),
    # reconcile difference across participants
    if override_total is not None:
        target_cents = override_total if is_cents else to_cents(override_total)
        diff = target_cents - expected_total_cents
        if diff != 0:
            adjustment = largest_remainder_distribute(diff, person_item_cents)
            for p, adj in adjustment.items():
                shares[p].total_cents += adj
            expected_total_cents = target_cents
            sum_individual_totals = sum(s.total_cents for s in shares.values())

    is_balanced = (sum_individual_totals == expected_total_cents)

    return SplitResult(
        shares=shares,
        total_items_cents=total_items_cents,
        tax_cents=tax_cents,
        tip_cents=tip_cents,
        discount_cents=discount_cents,
        total_cents=expected_total_cents,
        is_balanced=is_balanced,
    )
