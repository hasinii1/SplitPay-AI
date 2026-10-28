"""
SplitPay AI Data Models & Schemas
"""

from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field


# --- Item & OCR Schemas ---

class ExtractedItem(BaseModel):
    name: str = Field(..., description="Name of the food or beverage item")
    price: float = Field(..., description="Total price for this line item in the receipt currency")
    quantity: int = Field(default=1, description="Quantity of the item")
    consumers: List[str] = Field(default_factory=list, description="Names of people sharing this item")


class ReceiptExtractionResponse(BaseModel):
    merchant: str = Field(default="Restaurant", description="Name of the restaurant or store")
    date: Optional[str] = Field(default=None, description="Date on receipt if found")
    currency: str = Field(default="USD", description="Receipt currency code: USD or INR")
    items: List[ExtractedItem] = Field(default_factory=list, description="Extracted line items")
    subtotal: float = Field(default=0.0, description="Printed subtotal")
    tax: float = Field(default=0.0, description="Printed tax")
    tip: float = Field(default=0.0, description="Tip amount if printed")
    discount: float = Field(default=0.0, description="Any discount or coupon applied")
    total: float = Field(default=0.0, description="Final printed total")
    confidence_notes: Optional[str] = Field(default=None, description="Any OCR notes or warning about smudged text")
    calculated_items_sum: float = Field(default=0.0, description="Sum of extracted items")
    has_discrepancy: bool = Field(default=False, description="True if item sum doesn't match subtotal")


# --- Natural Language Parsing Schemas ---

class InstructionParseRequest(BaseModel):
    instruction: str = Field(..., description="Natural language prompt describing who had what")
    items: List[ExtractedItem] = Field(..., description="Current list of items to assign")
    known_people: Optional[List[str]] = Field(default_factory=list, description="List of recognized friends if known")


class ItemAssignment(BaseModel):
    item_name: str
    consumers: List[str]


class InstructionParseResponse(BaseModel):
    assignments: List[ItemAssignment]
    unassigned_items: List[str] = Field(default_factory=list)
    people_found: List[str] = Field(default_factory=list)
    ai_summary: str = Field(..., description="Brief natural explanation of what the AI understood")


# --- Split Calculation Schemas ---

class CalculateSplitRequest(BaseModel):
    items: List[ExtractedItem]
    currency: Literal["USD", "INR"] = "USD"
    tax: float = 0.0
    tip: float = 0.0
    discount: float = 0.0
    override_total: Optional[float] = None


class PersonShareDetail(BaseModel):
    person: str
    items_subtotal: float
    tax: float
    tip: float
    discount: float
    total: float
    items_subtotal_cents: int
    tax_cents: int
    tip_cents: int
    discount_cents: int
    total_cents: int
    assigned_items: List[Dict[str, Any]] = Field(default_factory=list)
    paypal_order_id: Optional[str] = None
    paypal_approval_url: Optional[str] = None
    status: str = "PENDING"
    qr_code_data: Optional[str] = None


class BillSplitResponse(BaseModel):
    bill_id: Optional[str] = None
    shares: Dict[str, PersonShareDetail]
    total_items: float
    tax: float
    tip: float
    discount: float
    total: float
    is_balanced: bool


# --- PayPal Schemas ---

class CreatePayPalOrdersRequest(BaseModel):
    bill_id: str
    host_name: Optional[str] = "Host"
    currency: Literal["USD", "INR"] = "USD"


class PayPalOrderSummary(BaseModel):
    person: str
    order_id: str
    approval_url: str
    total_amount: float
    currency: str = "USD"
    status: str
    qr_code_data: Optional[str] = None


class CreatePayPalOrdersResponse(BaseModel):
    bill_id: str
    orders: List[PayPalOrderSummary]
    exchange_rate: Optional[float] = None
    exchange_rate_date: Optional[str] = None


class CaptureOrderResponse(BaseModel):
    order_id: str
    person: str
    status: str
    capture_id: Optional[str] = None
    amount_captured: Optional[float] = None
    currency: Optional[str] = "USD"
    message: str


# --- AI Reminder / Nudge Schemas ---

class NudgeRequest(BaseModel):
    person: str
    amount: float
    merchant: str
    items: List[str]
    payment_link: str
    tone: str = Field(default="polite", description="polite, funny, shakespeare, pirate, passive-aggressive")


class NudgeResponse(BaseModel):
    person: str
    tone: str
    message: str
    shareable_whatsapp_url: str
