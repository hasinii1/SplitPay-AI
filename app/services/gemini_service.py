"""
Gemini AI Service for SplitPay AI
Handles:
1. Multimodal OCR & Line Item Extraction from receipt images.
2. Natural Language Instruction Parsing (mapping plain English to item assignments).
3. Contextual AI Nudge & Reminder Generator across customizable personas.
"""

import json
import logging
import re
import urllib.parse
from typing import List, Dict, Any, Optional
from PIL import Image
import io

from app.config import get_settings
from app.models import (
    ReceiptExtractionResponse,
    ExtractedItem,
    InstructionParseResponse,
    ItemAssignment,
    NudgeResponse,
)

logger = logging.getLogger(__name__)


class GeminiServiceError(RuntimeError):
    """Raised when a Gemini operation cannot produce a valid result."""


def _receipt_extraction_error_message(error: Exception) -> str:
    api_message = getattr(error, "message", None)
    if api_message:
        status = getattr(error, "status", None)
        code = getattr(error, "code", None)
        error_code = f"{code} {status}".strip() if code or status else "API error"
        return f"Gemini API error ({error_code}): {api_message}"

    if isinstance(error, Image.UnidentifiedImageError):
        return "The uploaded file is not a readable image. Try a clear JPG, PNG, or WEBP receipt photo."

    if isinstance(error, json.JSONDecodeError):
        return "Gemini returned an unreadable response. Please retry the upload."

    return (
        f"Receipt extraction failed ({type(error).__name__}). "
        "Check the server terminal for details."
    )


def _get_gemini_client():
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=settings.gemini_api_key)
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI client: {e}")
        return None


# --- Mock Fallbacks for testing without API Key ---

MOCK_RECEIPT = ReceiptExtractionResponse(
    merchant="Mario's Trattoria & Pizzeria",
    date="2026-10-26",
    currency="USD",
    items=[
        ExtractedItem(name="Wood-Fired Margherita Pizza", price=16.50, quantity=1, consumers=[]),
        ExtractedItem(name="Fettuccine Alfredo with Truffle", price=22.00, quantity=1, consumers=[]),
        ExtractedItem(name="Crispy Calamari Fritti", price=14.00, quantity=1, consumers=[]),
        ExtractedItem(name="Tiramisu Classico", price=9.50, quantity=1, consumers=[]),
        ExtractedItem(name="San Pellegrino Sparkling (1L)", price=6.00, quantity=1, consumers=[]),
        ExtractedItem(name="Chianti Classico Glass", price=12.00, quantity=1, consumers=[]),
    ],
    subtotal=80.00,
    tax=7.20,
    tip=16.00,
    discount=0.00,
    total=103.20,
    confidence_notes="Extracted successfully (sample demo receipt).",
    calculated_items_sum=80.00,
    has_discrepancy=False,
)


def _offline_instruction_response(
    instruction: str,
    items: List[ExtractedItem],
    known_people: Optional[List[str]],
    gemini_unavailable: bool = False,
) -> InstructionParseResponse:
    people = list(dict.fromkeys(
        person.strip() for person in (known_people or []) if person.strip()
    ))
    if not people:
        participant_list = re.search(
            r"\b(?:among|between)\s+(.+?)(?=[.!?;]|$)",
            instruction,
            flags=re.IGNORECASE,
        )
        if participant_list:
            people = list(dict.fromkeys(
                re.findall(
                    r"\b[A-Z][a-z]+(?:['’-][A-Z]?[a-z]+)?(?:\s+[A-Z][a-z]+)*\b",
                    participant_list.group(1),
                )
            ))
    if not people:
        people = ["Friend 1", "Friend 2"]

    reason = (
        "Gemini could not be reached, so"
        if gemini_unavailable
        else "Offline mode:"
    )
    return InstructionParseResponse(
        assignments=[
            ItemAssignment(item_name=item.name, consumers=people)
            for item in items
        ],
        unassigned_items=[],
        people_found=people,
        ai_summary=(
            f"{reason} each item is provisionally shared among "
            f"{', '.join(people)}. Review or edit the assignments before continuing."
        ),
    )


async def extract_receipt_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> ReceiptExtractionResponse:
    """
    Sends receipt image bytes to Gemini Vision model to extract merchant, line items,
    subtotal, tax, tip, and total. Returns structured JSON.
    """
    settings = get_settings()
    client = _get_gemini_client()

    if not client:
        logger.error("GEMINI_API_KEY is not set or the Gemini client is unavailable.")
        raise GeminiServiceError(
            "Gemini is unavailable. Check GEMINI_API_KEY and the server logs."
        )

    prompt = """
You are an expert receipt parsing AI. Analyze this receipt photo and extract:
1. "merchant": restaurant or store name.
2. "date": date of receipt if visible (YYYY-MM-DD or readable string).
3. "currency": currency printed on the receipt, either "USD" or "INR". Do not convert amounts.
4. "items": array of objects, each with:
   - "name": clean, concise item description (exclude line numbers or codes).
   - "price": total price for that item line in the receipt currency (float).
   - "quantity": integer quantity (default 1).
5. "subtotal": printed subtotal before taxes/tips (float).
6. "tax": printed tax amount (float).
7. "tip": printed tip or gratuity (float, 0 if not pre-printed).
8. "discount": printed discounts/coupons (positive float, 0 if none).
9. "total": final printed total amount (float).
10. "confidence_notes": brief note on readability or unlisted service fees.

Return ONLY valid JSON matching this schema:
{
  "merchant": "string",
  "date": "string or null",
  "currency": "USD or INR",
  "items": [{"name": "string", "price": 0.0, "quantity": 1}],
  "subtotal": 0.0,
  "tax": 0.0,
  "tip": 0.0,
  "discount": 0.0,
  "total": 0.0,
  "confidence_notes": "string"
}
"""

    try:
        from google.genai import types
        # Validate image with Pillow
        img = Image.open(io.BytesIO(image_bytes))

        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        text_content = response.text.strip()
        data = json.loads(text_content)
        currency = str(data.get("currency", "USD")).upper()
        if currency not in {"USD", "INR"}:
            raise ValueError(f"Unsupported receipt currency: {currency}")

        extracted_items = [
            ExtractedItem(
                name=it.get("name", "Unknown Item"),
                price=float(it.get("price", 0.0)),
                quantity=int(it.get("quantity", 1)),
                consumers=[],
            )
            for it in data.get("items", [])
        ]

        items_sum = round(sum(it.price for it in extracted_items), 2)
        subtotal = float(data.get("subtotal", items_sum))
        tax = float(data.get("tax", 0.0))
        tip = float(data.get("tip", 0.0))
        discount = float(data.get("discount", 0.0))
        total = float(data.get("total", round(items_sum + tax + tip - discount, 2)))

        has_discrepancy = abs(items_sum - subtotal) > 0.05

        return ReceiptExtractionResponse(
            merchant=data.get("merchant", "Restaurant"),
            date=data.get("date"),
            currency=currency,
            items=extracted_items,
            subtotal=subtotal,
            tax=tax,
            tip=tip,
            discount=discount,
            total=total,
            confidence_notes=data.get("confidence_notes"),
            calculated_items_sum=items_sum,
            has_discrepancy=has_discrepancy,
        )

    except Exception as e:
        logger.exception("Gemini receipt extraction failed.")
        raise GeminiServiceError(_receipt_extraction_error_message(e)) from e


async def parse_split_instructions(
    instruction: str,
    items: List[ExtractedItem],
    known_people: Optional[List[str]] = None,
) -> InstructionParseResponse:
    """
    Parses natural language instructions like:
    "Alice had the pizza, Bob and Charlie split the calamari and pasta, we all shared drinks and dessert"
    and maps them accurately to item consumers.
    """
    client = _get_gemini_client()
    settings = get_settings()

    item_names = [it.name for it in items]

    if not client:
        logger.info("Using offline instruction assignment because Gemini is unavailable.")
        return _offline_instruction_response(
            instruction=instruction,
            items=items,
            known_people=known_people,
        )

    prompt = f"""
You are an intelligent bill splitting assistant.
Here is the list of items from the receipt:
{json.dumps(item_names, indent=2)}

Here is the user's natural language instruction on who ordered/consumed what:
"{instruction}"

Instructions:
1. Map each item in the receipt to one or more person names who consumed or split that item.
2. If the user mentions "we all", "everyone", "shared", or "all of us", assign all detected people to that item.
3. Be flexible with partial item matches (e.g., if receipt has "Wood-Fired Margherita Pizza", "pizza" refers to it).
4. Extract the full list of distinct people mentioned.
5. Provide a clear, friendly 1-2 sentence summary of how items were assigned.

Return ONLY JSON matching this format:
{{
  "assignments": [
    {{"item_name": "exact name from the receipt item list", "consumers": ["Alice", "Bob"]}}
  ],
  "unassigned_items": [],
  "people_found": ["Alice", "Bob"],
  "ai_summary": "Alice had the Pizza; Bob and Charlie split the Calamari; drinks and dessert were shared among all three."
}}
"""

    try:
        from google.genai import types
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        data = json.loads(response.text.strip())

        assignments = [
            ItemAssignment(
                item_name=a.get("item_name", ""),
                consumers=[c.strip().title() for c in a.get("consumers", []) if c.strip()],
            )
            for a in data.get("assignments", [])
        ]

        return InstructionParseResponse(
            assignments=assignments,
            unassigned_items=data.get("unassigned_items", []),
            people_found=data.get("people_found", []),
            ai_summary=data.get("ai_summary", "Assigned items successfully."),
        )

    except Exception as e:
        logger.error(f"Gemini instruction parsing failed: {e}")
        return _offline_instruction_response(
            instruction=instruction,
            items=items,
            known_people=known_people,
            gemini_unavailable=True,
        )


async def generate_nudge_message(
    person: str,
    amount: float,
    merchant: str,
    items: List[str],
    payment_link: str,
    tone: str = "polite",
) -> NudgeResponse:
    """
    Generates a personalized payment reminder message using Gemini with selectable tones:
    - polite
    - funny
    - shakespeare
    - pirate
    - passive-aggressive
    """
    client = _get_gemini_client()
    settings = get_settings()

    amount_str = f"${amount:.2f}"
    items_str = ", ".join(items[:4]) if items else "your meal"

    # Pre-crafted fallback templates if offline
    fallbacks = {
        "polite": f"Hi {person}! Thanks for joining at {merchant}. Your share for {items_str} comes to {amount_str}. Whenever you get a chance, you can settle it securely via PayPal here: {payment_link} – thank you!",
        "funny": f"Hey {person}! Rumor has it the chef at {merchant} is looking for {amount_str} for that delicious {items_str}. Save me from washing dishes: {payment_link} 😉",
        "shakespeare": f"Hark, gentle {person}! The feast at {merchant} hath concluded, and the ledger demands its due of {amount_str} for {items_str}. Pray click yon link to settle thy noble debt: {payment_link}",
        "pirate": f"Ahoy {person}! Yer share o' the plunder at {merchant} be {amount_str} in gold doubloons for the {items_str}. Toss yer booty into the PayPal chest here, or walk the plank! 🏴‍☠️ {payment_link}",
        "passive-aggressive": f"Hey {person}, just checking in... my bank account noticed you haven't covered your {amount_str} from {merchant} yet. Not that I'm keeping track or anything! Link is here: {payment_link}",
    }

    selected_text = fallbacks.get(tone, fallbacks["polite"])

    if client:
        prompt = f"""
Write a single short payment reminder text message (under 350 characters) to send to a friend.
Friend Name: {person}
Amount Due: {amount_str}
Restaurant/Place: {merchant}
Items they had: {items_str}
PayPal Payment Link: {payment_link}
Requested Tone: {tone}

Instructions:
- Include the exact amount ({amount_str}) and the payment link ({payment_link}).
- Make the tone unmistakably {tone}.
- Return ONLY the raw message string without quotes or markdown headers.
"""
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=[prompt],
            )
            generated = response.text.strip()
            if payment_link in generated:
                selected_text = generated
        except Exception as e:
            logger.warning(f"Gemini nudge generation error: {e}. Using fallback.")

    whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(selected_text)}"

    return NudgeResponse(
        person=person,
        tone=tone,
        message=selected_text,
        shareable_whatsapp_url=whatsapp_url,
    )
