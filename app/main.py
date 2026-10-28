"""
SplitPay AI - Main FastAPI Application
Seamless receipt OCR, natural-language item splitting,
deterministic penny-perfect arithmetic, and PayPal Orders v2 integration.
"""

import os
import logging
from urllib.parse import urlencode
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import (
    init_db,
    create_bill,
    save_shares,
    get_bill,
    list_recent_bills,
    mark_share_paid,
    update_bill_currency,
    update_bill_exchange_rate,
)
from app.models import (
    ReceiptExtractionResponse,
    InstructionParseRequest,
    InstructionParseResponse,
    CalculateSplitRequest,
    BillSplitResponse,
    PersonShareDetail,
    CreatePayPalOrdersRequest,
    CreatePayPalOrdersResponse,
    PayPalOrderSummary,
    CaptureOrderResponse,
    NudgeRequest,
    NudgeResponse,
)
from app.services.split_engine import calculate_split, ItemInput
from app.services.gemini_service import (
    extract_receipt_from_image,
    parse_split_instructions,
    generate_nudge_message,
    MOCK_RECEIPT,
    GeminiServiceError,
)
from app.services.paypal_service import (
    create_paypal_order_for_person,
    capture_paypal_order,
    get_order_details,
    PayPalServiceError,
    convert_to_paypal_usd,
    get_usd_to_inr_exchange_rate,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure SQLite tables exist
    init_db()
    yield


app = FastAPI(
    title="SplitPay AI",
    description="AI-powered receipt splitting with deterministic arithmetic and PayPal Sandbox integration.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static directories exist
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=FileResponse)
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>SplitPay AI API is running! Static UI not yet deployed.</h1>")


# --- System & Health ---

@app.get("/api/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "online",
        "app": "SplitPay AI",
        "paypal_configured": settings.is_paypal_configured,
        "paypal_mode": settings.paypal_mode,
        "gemini_configured": settings.is_gemini_configured,
        "gemini_model": settings.gemini_model,
    }


@app.get("/api/exchange-rate")
async def exchange_rate():
    """Returns the latest reference USD/INR exchange rate used for conversions."""
    try:
        return await get_usd_to_inr_exchange_rate()
    except PayPalServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


# --- Receipt OCR & Upload ---

@app.post("/api/receipt/upload", response_model=Dict[str, Any])
async def upload_receipt(file: UploadFile = File(...)):
    """Uploads a receipt image and uses Gemini Vision to extract line items."""
    try:
        content = await file.read()
        mime_type = file.content_type or "image/jpeg"
        extraction = await extract_receipt_from_image(content, mime_type=mime_type)

        # Persist initial bill in database
        items_payload = [it.model_dump() for it in extraction.items]
        bill_id = create_bill(
            merchant=extraction.merchant,
            date=extraction.date,
            subtotal=extraction.subtotal,
            tax=extraction.tax,
            tip=extraction.tip,
            discount=extraction.discount,
            total=extraction.total,
            items=items_payload,
            currency=extraction.currency,
        )

        resp = extraction.model_dump()
        resp["bill_id"] = bill_id
        return resp
    except GeminiServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process receipt: {str(e)}")


@app.post("/api/receipt/sample")
async def load_sample_receipt():
    """Provides a sample Italian dinner receipt for instant testing without uploading an image."""
    extraction = MOCK_RECEIPT.model_copy()
    items_payload = [it.model_dump() for it in extraction.items]
    bill_id = create_bill(
        merchant=extraction.merchant,
        date=extraction.date,
        subtotal=extraction.subtotal,
        tax=extraction.tax,
        tip=extraction.tip,
        discount=extraction.discount,
        total=extraction.total,
        items=items_payload,
        currency=extraction.currency,
    )
    resp = extraction.model_dump()
    resp["bill_id"] = bill_id
    return resp


# --- Natural Language Parsing & Item Assignment ---

@app.post("/api/split/parse-instruction", response_model=InstructionParseResponse)
async def parse_instructions_endpoint(req: InstructionParseRequest):
    """Parses plain-English instructions and assigns items to friends."""
    return await parse_split_instructions(
        instruction=req.instruction,
        items=req.items,
        known_people=req.known_people,
    )


# --- Deterministic Mathematical Calculation ---

@app.post("/api/split/calculate", response_model=BillSplitResponse)
async def calculate_split_endpoint(req: CalculateSplitRequest, bill_id: Optional[str] = None):
    """
    Computes penny-perfect shares with proportional tax and tip.
    Guarantees sum(shares) == total down to the cent.
    """
    engine_items = [
        ItemInput(name=it.name, price=it.price, consumers=it.consumers)
        for it in req.items
    ]

    split_result = calculate_split(
        items=engine_items,
        tax=req.tax,
        tip=req.tip,
        discount=req.discount,
        override_total=req.override_total,
    )

    if bill_id:
        update_bill_currency(bill_id, req.currency)

    # Convert to response schema
    shares_dict: Dict[str, PersonShareDetail] = {}
    for person, s in split_result.shares.items():
        shares_dict[person] = PersonShareDetail(
            person=s.person,
            items_subtotal=s.items_subtotal,
            tax=s.tax,
            tip=s.tip,
            discount=s.discount,
            total=s.total,
            items_subtotal_cents=s.items_subtotal_cents,
            tax_cents=s.tax_cents,
            tip_cents=s.tip_cents,
            discount_cents=s.discount_cents,
            total_cents=s.total_cents,
            assigned_items=s.assigned_items,
        )

    # Persist shares to database if bill_id exists
    if bill_id:
        shares_for_db = {k: v.model_dump() for k, v in shares_dict.items()}
        save_shares(bill_id, shares_for_db)

    return BillSplitResponse(
        bill_id=bill_id,
        shares=shares_dict,
        total_items=split_result.total_items,
        tax=split_result.tax,
        tip=split_result.tip,
        discount=split_result.discount,
        total=split_result.total,
        is_balanced=split_result.is_balanced,
    )


# --- PayPal Sandbox Integration ---

@app.post("/api/paypal/create-orders", response_model=CreatePayPalOrdersResponse)
async def create_paypal_orders(req: CreatePayPalOrdersRequest):
    """
    Generates a PayPal Sandbox order (Orders v2 API with CAPTURE intent)
    for each participant's individual share.
    """
    bill = get_bill(req.bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    shares = bill.get("shares", [])
    if not shares:
        raise HTTPException(status_code=400, detail="No calculated shares found for this bill. Run split calculation first.")

    source_currency = bill.get("currency", req.currency).upper()
    if source_currency != req.currency.upper():
        raise HTTPException(
            status_code=409,
            detail="Bill currency changed. Reload the bill before creating PayPal orders.",
        )
    exchange_rate_data = None
    if source_currency == "INR":
        try:
            exchange_rate_data = await get_usd_to_inr_exchange_rate()
        except PayPalServiceError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        update_bill_exchange_rate(
            req.bill_id,
            exchange_rate_data["rate"],
            exchange_rate_data["date"],
        )

    orders_summary: List[PayPalOrderSummary] = []

    for share in shares:
        person = share["person"]
        amount = share["total"]
        assigned_items = share.get("assigned_items", [])

        # Skip participants with 0 balance
        if amount <= 0:
            continue

        paypal_amount = convert_to_paypal_usd(
            amount,
            source_currency,
            exchange_rate_data["rate"] if exchange_rate_data else None,
        )
        try:
            res = await create_paypal_order_for_person(
                bill_id=req.bill_id,
                person=person,
                merchant=bill["merchant"],
                amount=paypal_amount,
                assigned_items=assigned_items,
                currency="USD",
            )
        except PayPalServiceError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

        orders_summary.append(
            PayPalOrderSummary(
                person=person,
                order_id=res["order_id"],
                approval_url=res["approval_url"],
                total_amount=paypal_amount,
                currency="USD",
                status=res["status"],
                qr_code_data=res.get("qr_code_data"),
            )
        )

    return CreatePayPalOrdersResponse(
        bill_id=req.bill_id,
        orders=orders_summary,
        exchange_rate=exchange_rate_data["rate"] if exchange_rate_data else None,
        exchange_rate_date=exchange_rate_data["date"] if exchange_rate_data else None,
    )


@app.post("/api/paypal/capture-order/{order_id}", response_model=CaptureOrderResponse)
async def capture_order_endpoint(order_id: str):
    """Captures payment for an approved PayPal order and marks share as PAID."""
    try:
        res = await capture_paypal_order(order_id)
        # Find person from DB
        conn = get_bill_by_order_id(order_id)
        person_name = conn.get("person", "Friend") if conn else "Friend"
        return CaptureOrderResponse(
            order_id=order_id,
            person=person_name,
            status=res["status"],
            capture_id=res.get("capture_id"),
            message=res.get("message", "Payment processed"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paypal/return")
async def paypal_return(token: Optional[str] = None, PayerID: Optional[str] = None, bill_id: Optional[str] = None, person: Optional[str] = None):
    """
    Return redirect URL from PayPal checkout.
    Captures the order and returns the payer to the same bill dashboard.
    """
    if not token:
        raise HTTPException(status_code=400, detail="PayPal did not provide an order token.")

    try:
        capture = await capture_paypal_order(token)
    except Exception as e:
        logger.exception("Could not capture PayPal order on return.")
        raise HTTPException(
            status_code=502,
            detail="PayPal returned from checkout, but payment capture failed. Check bill status before retrying.",
        ) from e

    if capture.get("status") != "COMPLETED":
        raise HTTPException(
            status_code=502,
            detail=f"PayPal returned order status {capture.get('status', 'UNKNOWN')}; payment was not marked complete.",
        )

    order_share = get_bill_by_order_id(token)
    bill_id = bill_id or (order_share.get("bill_id") if order_share else None)
    person = person or (order_share.get("person") if order_share else None)
    if not bill_id:
        raise HTTPException(status_code=404, detail="Paid order is not associated with a bill.")

    query = urlencode({"bill_id": bill_id, "payment": "success", "person": person or ""})
    return RedirectResponse(url=f"/?{query}", status_code=303)


@app.get("/api/paypal/mock-approve")
async def mock_paypal_approve(order_id: str, bill_id: str, person: str, amount: str, currency: str = "USD"):
    """Interactive simulated PayPal approval screen for local and offline testing."""
    symbol = "₹" if currency.upper() == "INR" else "$"
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>PayPal Sandbox Checkout Simulator - SplitPay AI</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-[#064734] min-h-screen flex items-center justify-center p-4 font-sans">
        <div class="max-w-md w-full bg-slate-900 border border-[#E0FFC2]/30 rounded-3xl p-8 shadow-2xl text-white">
            <div class="flex items-center justify-between pb-4 border-b border-slate-800 mb-6">
                <div class="text-2xl font-extrabold italic text-[#E0FFC2]">PayPal <span class="text-emerald-400">Sandbox</span></div>
                <span class="text-xs font-semibold px-2.5 py-1 bg-[#064734] text-[#E0FFC2] border border-[#E0FFC2]/40 rounded-full">Test Environment ({currency})</span>
            </div>
            <h2 class="text-xl font-bold text-white mb-1">Pay with PayPal</h2>
            <p class="text-slate-400 text-sm mb-6">Settling share for SplitPay Bill</p>

            <div class="bg-slate-950 border border-slate-800 rounded-2xl p-4 mb-6">
                <div class="flex justify-between text-sm text-slate-400 mb-1">
                    <span>Payer:</span>
                    <span class="font-semibold text-white">{person}</span>
                </div>
                <div class="flex justify-between text-sm text-slate-400 mb-3">
                    <span>Order Reference:</span>
                    <span class="font-mono text-xs text-slate-500">{order_id}</span>
                </div>
                <div class="border-t border-slate-800 pt-3 flex justify-between items-baseline">
                    <span class="text-base font-bold text-slate-300">Total Due:</span>
                    <span class="text-3xl font-extrabold text-[#E0FFC2]">{symbol}{amount}</span>
                </div>
            </div>

            <form action="/api/paypal/return" method="GET">
                <input type="hidden" name="token" value="{order_id}">
                <input type="hidden" name="bill_id" value="{bill_id}">
                <input type="hidden" name="person" value="{person}">
                <button type="submit" class="w-full py-4 bg-[#E0FFC2] hover:bg-[#bceba0] text-[#064734] font-extrabold rounded-full transition shadow-lg flex items-center justify-center gap-2 mb-3">
                    <span>Complete Purchase (Simulate Pay Now)</span>
                </button>
            </form>

            <a href="/" class="block text-center text-xs text-slate-400 hover:text-slate-200 underline">Cancel and return to merchant</a>
        </div>
    </body>
    </html>
    """)


@app.get("/api/paypal/cancel")
async def paypal_cancel(bill_id: Optional[str] = None, person: Optional[str] = None):
    if not bill_id:
        return RedirectResponse(url="/", status_code=303)
    query = urlencode({"bill_id": bill_id, "payment": "cancelled", "person": person or ""})
    return RedirectResponse(url=f"/?{query}", status_code=303)


# --- Bill Details & Polling ---

def get_bill_by_order_id(order_id: str) -> Optional[Dict[str, Any]]:
    from app.database import get_connection
    conn = get_connection()
    cur = conn.execute("SELECT * FROM bill_shares WHERE paypal_order_id = ?", (order_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


@app.get("/api/bills/{bill_id}")
async def get_bill_details(bill_id: str):
    """Returns the full state of a bill, its items, and individual participant payment status."""
    bill = get_bill(bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


@app.get("/api/bills")
async def get_recent_bills():
    """Lists recent bills for the history tab."""
    return list_recent_bills(limit=10)


# --- AI Reminder / Nudge Generator ---

@app.post("/api/nudge/generate", response_model=NudgeResponse)
async def generate_nudge(req: NudgeRequest):
    """Generates an AI-written payment reminder with selected persona and WhatsApp link."""
    return await generate_nudge_message(
        person=req.person,
        amount=req.amount,
        merchant=req.merchant,
        items=req.items,
        payment_link=req.payment_link,
        tone=req.tone,
    )
