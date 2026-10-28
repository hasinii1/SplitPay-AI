"""
PDF Documentation Generator for SplitPay AI using PyMuPDF.
Generates an in-depth, professional PDF document explaining every detail of the project.
"""

import pymupdf

def create_splitpay_pdf():
    doc = pymupdf.open()

    # Colors
    DARK_FOREST = (6/255, 71/255, 52/255)    # #064734
    LEAF = (224/255, 255/255, 194/255)       # #E0FFC2
    CHARCOAL = (30/255, 41/255, 59/255)
    GRAY = (100/255, 116/255, 139/255)
    LIGHT_BG = (248/255, 250/255, 252/255)

    def add_page_header_footer(page, page_num, total_pages, title="SplitPay AI — Master Architecture & Technical Guide"):
        rect = page.rect
        # Top banner
        page.draw_rect(pymupdf.Rect(0, 0, rect.width, 36), fill=DARK_FOREST)
        page.insert_text(pymupdf.Point(36, 23), title, fontsize=9, color=LEAF, fontname="helv")
        # Bottom footer
        page.draw_line(pymupdf.Point(36, rect.height - 30), pymupdf.Point(rect.width - 36, rect.height - 30), color=GRAY, width=0.5)
        page.insert_text(pymupdf.Point(36, rect.height - 18), "SplitPay AI • Comprehensive Technical Documentation", fontsize=8, color=GRAY, fontname="helv")
        page.insert_text(pymupdf.Point(rect.width - 70, rect.height - 18), f"Page {page_num}", fontsize=8, color=GRAY, fontname="helv")

    # ================= PAGE 1: TITLE & EXECUTIVE SUMMARY =================
    p1 = doc.new_page()
    rect = p1.rect

    # Hero Banner
    p1.draw_rect(pymupdf.Rect(0, 0, rect.width, 220), fill=DARK_FOREST)
    p1.insert_text(pymupdf.Point(40, 70), "SplitPay AI", fontsize=32, color=LEAF, fontname="helv")
    p1.insert_text(pymupdf.Point(40, 105), "Intelligent Dining Bill Settlement & Instant Payments Platform", fontsize=15, color=(1, 1, 1), fontname="helv")
    p1.insert_text(pymupdf.Point(40, 135), "Full Technical Specification & Architectural Blueprint", fontsize=11, color=LEAF, fontname="helv")
    p1.insert_text(pymupdf.Point(40, 180), "Multimodal Vision OCR • Hare-Niemeyer Integer Cents • PayPal Orders v2 • AG Grid", fontsize=9, color=(0.9, 0.9, 0.9), fontname="helv")

    y = 250
    p1.insert_text(pymupdf.Point(40, y), "1. Executive Summary", fontsize=16, color=DARK_FOREST, fontname="helv")
    p1.draw_line(pymupdf.Point(40, y + 4), pymupdf.Point(rect.width - 40, y + 4), color=DARK_FOREST, width=1.5)

    y += 24
    summary_text = (
        "SplitPay AI is a production-grade fintech application that eliminates the awkwardness, mathematical\n"
        "errors, and friction of splitting group dining bills. Users upload a raw receipt photograph, describe\n"
        "who ordered what in conversational plain English, and the system handles the rest:\n\n"
        "  • Multimodal Extraction: Google Gemini 3.6 Flash extracts all line items, currency, tax, tip, and totals.\n"
        "  • Conversational Parsing: Gemini maps natural-language instructions to specific dishes.\n"
        "  • Deterministic Arithmetic: A pure Python engine applies the Hare-Niemeyer (Largest Remainder)\n"
        "    algorithm to guarantee individual shares sum identically to the total down to the exact cent.\n"
        "  • Instant PayPal Settlement: Automatically creates PayPal Orders v2 with CAPTURE intent,\n"
        "    generates table-side scannable QR codes, and tracks live settlement on a real-time dashboard.\n"
        "  • Multi-Persona Nudges: Generates polite, witty, or humorous reminder texts with 1-click WhatsApp sharing.\n"
        "  • Dual Currency Support: Seamlessly operates in both US Dollars ($ USD) and Indian Rupees (₹ INR)."
    )
    p1.insert_text(pymupdf.Point(40, y), summary_text, fontsize=10, color=CHARCOAL, fontname="helv")

    y += 200
    p1.insert_text(pymupdf.Point(40, y), "2. The Real-World Problem", fontsize=14, color=DARK_FOREST, fontname="helv")
    p1.draw_line(pymupdf.Point(40, y + 4), pymupdf.Point(rect.width - 40, y + 4), color=DARK_FOREST, width=1)

    y += 20
    problem_text = (
        "Group dining is one of the most common social activities, yet bill settlement remains broken:\n"
        "  1. The Rounding Dilemma: Dividing items unevenly across people creates floating-point fractions\n"
        "     ($10.00 / 3 = $3.333...). Standard calculator rounding produces lost pennies ($9.99 vs $10.00).\n"
        "  2. Proportional Tax & Tip Unfairness: Applying flat tax/tip unfairly burdens light eaters who\n"
        "     only ordered an appetizer, while heavy spenders pay proportionally less.\n"
        "  3. Collection Friction: The host who fronts the bill spends days sending awkward reminder texts."
    )
    p1.insert_text(pymupdf.Point(40, y), problem_text, fontsize=10, color=CHARCOAL, fontname="helv")

    add_page_header_footer(p1, 1, 4)

    # ================= PAGE 2: TECH STACK BREAKDOWN =================
    p2 = doc.new_page()
    y = 55
    p2.insert_text(pymupdf.Point(40, y), "3. Comprehensive Technology Breakdown (What, Why, How, Where)", fontsize=16, color=DARK_FOREST, fontname="helv")
    p2.draw_line(pymupdf.Point(40, y + 4), pymupdf.Point(rect.width - 40, y + 4), color=DARK_FOREST, width=1.5)

    modules = [
        ("FastAPI & Uvicorn (Backend Core)",
         "What: High-performance asynchronous Python web framework and ASGI server.\n"
         "Why: Native async execution, automatic OpenAPI schema generation, and sub-millisecond route handling.\n"
         "Where: app/main.py | How: Serves REST endpoints (/api/receipt/upload, /api/paypal/create-orders, etc.)."),

        ("Google Gemini 3.6 Flash (Multimodal AI)",
         "What: Google's ultra-fast multimodal reasoning model with native JSON schema outputs.\n"
         "Why: Traditional OCR lacks spatial understanding; Gemini understands bill layouts, discounts, and intent.\n"
         "Where: app/services/gemini_service.py | How: Extracts items from images and parses plain-English instructions."),

        ("Deterministic Hare-Niemeyer Math Engine (split_engine.py)",
         "What: Pure mathematical algorithm utilizing integer cents and Largest Remainder distribution.\n"
         "Why: LLMs hallucinate numbers and must NEVER do final math. Floats leak fractional pennies.\n"
         "Where: app/services/split_engine.py | How: Converts amounts to cents, guarantees Sum(shares) == Total."),

        ("PayPal Developer Platform & Orders v2 API",
         "What: PayPal's global payments infrastructure with client-credentials OAuth and Orders v2.\n"
         "Why: Universal payment trust, sandbox simulation, CAPTURE intent, and direct return-redirect workflows.\n"
         "Where: app/services/paypal_service.py | How: Creates orders with idempotency, captures on return redirect."),

        ("SQLite with WAL Mode (Database)",
         "What: Serverless ACID-compliant SQL database running with Write-Ahead Logging.\n"
         "Why: Zero cloud database maintenance, persistent storage, and non-blocking concurrent reads/writes.\n"
         "Where: app/database.py | How: Persists Bills, Bill Items, Individual Shares, and PayPal Order States."),

        ("AG Grid Community (Audit & Review Grid)",
         "What: Leading enterprise JavaScript data grid.\n"
         "Why: Provides tabular transparency: friends see exactly their subtotal, proportional tax, tip, and total.\n"
         "Where: app/static/index.html & app.js | How: Renders dynamic, sortable breakdown table in Step 3.")
    ]

    y += 24
    for title, desc in modules:
        # Card box
        p2.draw_rect(pymupdf.Rect(40, y, rect.width - 40, y + 68), fill=LIGHT_BG, color=DARK_FOREST, width=0.5)
        p2.draw_rect(pymupdf.Rect(40, y, 44, y + 68), fill=DARK_FOREST)
        p2.insert_text(pymupdf.Point(52, y + 16), title, fontsize=11, color=DARK_FOREST, fontname="helv")
        p2.insert_text(pymupdf.Point(52, y + 30), desc, fontsize=8.5, color=CHARCOAL, fontname="helv")
        y += 76

    add_page_header_footer(p2, 2, 4)

    # ================= PAGE 3: MATHEMATICAL PROOF & CODEBASE WALKTHROUGH =================
    p3 = doc.new_page()
    y = 55
    p3.insert_text(pymupdf.Point(40, y), "4. Mathematical Engine: Proof of Zero-Penny Discrepancy", fontsize=15, color=DARK_FOREST, fontname="helv")
    p3.draw_line(pymupdf.Point(40, y + 4), pymupdf.Point(rect.width - 40, y + 4), color=DARK_FOREST, width=1.5)

    y += 22
    math_explanation = (
        "Problem: When dividing $10.00 among Alice, Bob, and Charlie, each gets $3.3333... cents.\n"
        "Rounding down results in $9.99 (1 cent short). Rounding up results in $10.02 (2 cents over).\n\n"
        "The Hare-Niemeyer (Largest Remainder) Solution in split_engine.py:\n"
        "  1. Convert to integer cents: Total = 1000 cents. Number of participants N = 3.\n"
        "  2. Base integer quota: floor(1000 / 3) = 333 cents per person (Total = 999 cents).\n"
        "  3. Remainder calculation: 1000 - 999 = 1 cent remainder.\n"
        "  4. Remainder sorting: Participants are ranked by their fractional remainder. The highest gets +1 cent.\n"
        "  5. Output: Alice = $3.34, Bob = $3.33, Charlie = $3.33 -> Sum = $10.00 EXACTLY.\n\n"
        "Proportional Tax and Tip Distribution:\n"
        "  If Alice ate $20 of food and Bob ate $10 of food on a $30 bill with $6.00 tip:\n"
        "    • Alice's Food Ratio = 20 / 30 (66.67%) -> Tip Share = $4.00\n"
        "    • Bob's Food Ratio = 10 / 30 (33.33%) -> Tip Share = $2.00\n"
        "  Largest remainder ensures that even with fractional tax rates (e.g. 8.875%), all penny fractions\n"
        "  are reconciled with zero rounding leakage."
    )
    p3.insert_text(pymupdf.Point(40, y), math_explanation, fontsize=9.5, color=CHARCOAL, fontname="helv")

    y += 230
    p3.insert_text(pymupdf.Point(40, y), "5. Codebase Structure & File Responsibilities", fontsize=14, color=DARK_FOREST, fontname="helv")
    p3.draw_line(pymupdf.Point(40, y + 4), pymupdf.Point(rect.width - 40, y + 4), color=DARK_FOREST, width=1)

    files_list = [
        ("app/main.py", "FastAPI app, REST routes, static file mounting, PayPal return callbacks."),
        ("app/config.py", "Pydantic settings loader (.env), PayPal base URL resolver, credential detector."),
        ("app/database.py", "SQLite connection manager with WAL mode; creates Bills, Items, Shares tables."),
        ("app/models.py", "Strict Pydantic models for OCR responses, NL instructions, Splits, and PayPal schemas."),
        ("app/services/split_engine.py", "Integer-cent math engine implementing Hare-Niemeyer largest-remainder allocation."),
        ("app/services/gemini_service.py", "Multimodal OCR with Gemini 3.6 Flash, natural-language item mapper, AI nudges."),
        ("app/services/paypal_service.py", "PayPal Orders v2 integration: cached OAuth tokens, CAPTURE intent, QR codes."),
        ("app/static/index.html", "Responsive SPA with discrete Landing Page & Dashboard views; Forest/Leaf design."),
        ("app/static/app.js", "Frontend logic: dropzone, view router, AG Grid renderer, live polling, dual currency."),
        ("tests/test_split_engine.py", "Comprehensive test suite verifying zero-penny balance across complex split edge cases.")
    ]

    y += 20
    for filename, purpose in files_list:
        p3.insert_text(pymupdf.Point(45, y), filename, fontsize=9, color=DARK_FOREST, fontname="helv")
        p3.insert_text(pymupdf.Point(180, y), purpose, fontsize=8.5, color=CHARCOAL, fontname="helv")
        y += 18

    add_page_header_footer(p3, 3, 4)

    # ================= PAGE 4: DEMO SCRIPT & LOCAL RUN GUIDE =================
    p4 = doc.new_page()
    y = 55
    p4.insert_text(pymupdf.Point(40, y), "6. Word-for-Word Demo Presentation Script (2m 45s)", fontsize=15, color=DARK_FOREST, fontname="helv")
    p4.draw_line(pymupdf.Point(40, y + 4), pymupdf.Point(rect.width - 40, y + 4), color=DARK_FOREST, width=1.5)

    y += 22
    script_text = (
        "[0:00 - 0:30] The Hook & Problem:\n"
        "  'We've all been there: dinner with friends ends, the bill arrives, and someone spends 20 minutes\n"
        "   punching numbers into a calculator arguing over who pays what share of tax and tip. Splitting equally\n"
        "   is unfair, manual math is tedious, and rounding errors lose pennies. We built SplitPay AI to solve\n"
        "   this end-to-end using Google Gemini AI and the PayPal Developer Platform.'\n\n"
        "[0:30 - 1:10] Multimodal OCR & Natural Language Split:\n"
        "  'Here on the dashboard, a host uploads a receipt photo. Gemini 3.6 Flash extracts every line item,\n"
        "   subtotal, tax, and tip. Next, instead of manual clicking, the host simply types in plain English:\n"
        "   \"Alice had the pizza, Bob and Charlie split the pasta and calamari, we all shared drinks.\"\n"
        "   Gemini parses the human intent and instantly assigns the dishes.'\n\n"
        "[1:10 - 1:45] Zero-Hallucination Math & AG Grid Review:\n"
        "  'Crucially, AI never does the math. Our Python engine converts all amounts to integer cents and applies\n"
        "   the Hare-Niemeyer Largest Remainder algorithm. Tax and tip are distributed proportionally to what each\n"
        "   person ate, with zero penny roundoff error. The interactive AG Grid table transparently audits every share.'\n\n"
        "[1:45 - 2:20] PayPal Orders v2 & Table-Side QR Codes:\n"
        "  'With one click, SplitPay AI calls PayPal Orders v2 with CAPTURE intent. Each friend gets their own\n"
        "   checkout link and a table-side scannable QR code. When a friend approves on their phone, our webhook\n"
        "   captures the order and live polling updates the card from yellow PENDING to green PAID in real time!'\n\n"
        "[2:20 - 2:45] AI Smart Nudge & Conclusion:\n"
        "  'If someone forgets to pay, Gemini generates customized reminders in funny personas — from Shakespearean\n"
        "   to Pirate — with 1-click WhatsApp sharing. SplitPay AI turns dining settlements into an instant, fair,\n"
        "   and enjoyable experience. Thank you!'"
    )
    p4.insert_text(pymupdf.Point(40, y), script_text, fontsize=8.5, color=CHARCOAL, fontname="helv")

    y += 330
    p4.insert_text(pymupdf.Point(40, y), "7. Step-by-Step Localhost Setup Guide", fontsize=14, color=DARK_FOREST, fontname="helv")
    p4.draw_line(pymupdf.Point(40, y + 4), pymupdf.Point(rect.width - 40, y + 4), color=DARK_FOREST, width=1)

    y += 20
    setup_guide = (
        "1. Open Terminal in project directory:  cd 'F:\\SplitPay AI'\n"
        "2. Install dependencies:               pip install -r requirements.txt\n"
        "3. Run automated unit test suite:       python -m unittest discover tests\n"
        "4. Launch local web server:             python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload\n"
        "5. Open browser:                       http://localhost:8000"
    )
    p4.insert_text(pymupdf.Point(40, y), setup_guide, fontsize=9.5, color=DARK_FOREST, fontname="courier")

    add_page_header_footer(p4, 4, 4)

    output_path = r"F:\SplitPay AI\SplitPay_AI_Complete_Documentation.pdf"
    doc.save(output_path)
    doc.close()
    print("PDF generated successfully at:", output_path)

if __name__ == "__main__":
    create_splitpay_pdf()
