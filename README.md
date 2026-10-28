# 🧾 SplitPay AI

> **Zero-Error Receipt Splitting with PayPal Orders v2 & Google Gemini AI**  

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PayPal](https://img.shields.io/badge/PayPal-Orders_v2_API-003087?logo=paypal)](https://developer.paypal.com/)
[![Google Gemini](https://img.shields.io/badge/AI-Gemini_3.6_Flash-4285F4?logo=google)](https://aistudio.google.com/)
[![AG Grid](https://img.shields.io/badge/Sponsor-AG_Grid_Community-00E676)](https://ag-grid.com/)
[![Postman](https://img.shields.io/badge/Sponsor-Postman_Collection-FF6C37?logo=postman)](https://www.postman.com/)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render)](https://render.com/)
[![Python](https://img.shields.io/badge/Backend-Python_3.11_%2B_FastAPI-3776AB?logo=python)](https://fastapi.tiangolo.com/)

---

## 💡 The Problem & The Solution

**The Problem:**  
Splitting restaurant bills with friends is notoriously awkward. Someone manually keys numbers into a calculator, people disagree on tax and tip distribution, rounding errors lose pennies, and the person who fronted the bill spends the next two weeks chasing friends for payment.

**The SplitPay AI Solution:**  
1. **Snap or Upload Receipt:** Google Gemini 3.6 Flash extracts all line items, currency, tax, tip, and totals in seconds.
2. **Describe in Plain English:** Simply type or speak: *"Alice had the pizza, Bob and Charlie split the pasta and calamari, we all shared drinks."* Gemini accurately maps dishes to friends.
3. **Zero-Hallucination Math:** Final calculations are **never performed by the LLM**. Our deterministic `split_engine.py` converts all numbers to integer cents and runs the **Hare-Niemeyer (Largest Remainder) algorithm** to guarantee that individual shares sum **exactly to the bill total** with zero penny discrepancies.
4. **Instant PayPal Orders v2 Checkout:** The host generates a PayPal Sandbox order per friend with `CAPTURE` intent. Friends can click their payment link or scan a **table-side QR code** directly on their phones.
5. **Live Payment Dashboard & AI Nudges:** The host tracks incoming payments in real time. If a friend hasn't paid, Gemini generates a custom payment reminder in hilarious or polite personas (*Shakespearean*, *Pirate*, *Passive-Aggressive*, *Polite*) with 1-click WhatsApp sharing!

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    User["Host / Payer"] -->|1. Upload Receipt| WebUI["SplitPay AI Web App\n(HTML5 + Tailwind + AG Grid)"]
    WebUI -->|2. Image Bytes| GeminiVision["Google Gemini 3.6 Flash\n(Multimodal OCR)"]
    GeminiVision -->|3. Extracted Items JSON| WebUI
    
    User -->|4. Natural Language Instruction| WebUI
    WebUI -->|5. Plain English Prompt| GeminiNL["Google Gemini AI\n(Intent Parser)"]
    GeminiNL -->|6. Friend-to-Dish Mapping| SplitEngine["Split Engine (Python 3.11)\n(Integer Cents + Hare-Niemeyer)"]
    
    SplitEngine -->|7. Audit Breakdown| AGGrid["AG Grid Table\n(Proportional Tax & Tip)"]
    SplitEngine -->|8. Verified Shares| SQLite[("SQLite Database\n(Bills, Items, Shares)")]
    
    WebUI -->|9. Create Individual Orders| PayPalAPI["PayPal Sandbox Orders v2 API\n(OAuth Caching, Idempotency, CAPTURE)"]
    PayPalAPI -->|10. Approval URLs + QR Codes| WebUI
    
    Friend["Friends / Diners"] -->|11. Scan QR / Click Link| PayPalCheckout["PayPal Checkout\n(Sandbox Approval)"]
    PayPalCheckout -->|12. Return Redirect| PayPalCapture["/api/paypal/return\n(Order Capture)"]
    PayPalCapture -->|13. Mark PAID| SQLite
    SQLite -.->|14. Live Polling (4s)| WebUI
```

---

## 🌟 Platform Integrations

### 1. PayPal Developer Platform (Core Requirement)
- **Orders v2 API**: Implements `POST /v2/checkout/orders` with `CAPTURE` intent and individual line items.
- **Client Credentials OAuth Token Caching**: In-memory caching with TTL safety buffer to prevent redundant authentication round-trips.
- **Idempotency**: Sends unique `PayPal-Request-Id` headers with every order to prevent duplicate charges.
- **Approval Link Extraction**: Dynamically isolates the `rel: "approve"` / `rel: "payer-action"` URL for each participant.
- **Automatic Capture on Return**: `/api/paypal/return` executes `POST /v2/checkout/orders/{id}/capture` and updates the database to `PAID`.
- **Table-Side QR Codes**: Encodes each friend's approval link into a high-contrast QR code for instant mobile camera checkout.
- **Currency Handling**: PayPal orders are created in USD. INR bill shares use the latest available USD/INR reference rate, with a fallback rate if the rate service is unavailable; each checkout card shows the USD charge.

### 2. AG Grid Community (Official Sponsor)
- AG Grid is embedded directly on Step 3 for transparent mathematical review.
- Displays sortable, filterable, and formatted columns: **Friend**, **Subtotal**, **Proportional Tax**, **Proportional Tip**, **Total Share**, and **Assigned Dishes**.

### 3. Postman (Official Sponsor)
- Includes [`splitpay.postman_collection.json`](./splitpay.postman_collection.json) featuring pre-configured environments, automated assertion scripts (`pm.test`), and complete end-to-end coverage across all 7 endpoints.

### 4. Render (Official Sponsor)
- Includes [`render.yaml`](./render.yaml) for 1-click cloud deployment on Render's free tier.

---

## 🧮 The Largest Remainder Math Engine

LLMs frequently hallucinate arithmetic. SplitPay AI strictly separates **AI reasoning** from **mathematical computation**:

1. **Integer-Cent Precision:** Every dollar amount is converted to an integer number of cents ($C = \text{round}(\text{amount} \times 100)$).
2. **Item Partitioning:** If $k$ people share an item of $C$ cents, the base price is $\lfloor C / k \rfloor$, and the remaining $C \pmod k$ cents are distributed deterministically.
3. **Proportional Tax, Tip & Discount:** Each person's quota of tax is:
   $$q_j = \frac{I_j \times T_{\text{cents}}}{S_{\text{items}}}$$
   Each person receives $\lfloor q_j \rfloor$, and the remaining cents are assigned to the participants with the largest fractional remainders ($q_j - \lfloor q_j \rfloor$).
4. **Mathematical Guarantee:**
   $$\sum_{j=1}^N \text{total}_j \equiv S_{\text{items}} + T_{\text{cents}} + P_{\text{cents}} - D_{\text{cents}}$$
   Every single penny is accounted for with **zero floating point error**.

---

## 🚀 Quickstart & Setup Guide

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/splitpay-ai.git
cd splitpay-ai
```

### 2. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the template:

```bash
cp .env.example .env
```

Edit `.env` with your sandbox credentials:

```ini
# Google Gemini API (Get free key at https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash

# PayPal Sandbox Credentials (Get at https://developer.paypal.com/dashboard)
PAYPAL_CLIENT_ID=your_paypal_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_paypal_sandbox_client_secret
PAYPAL_MODE=sandbox
APP_BASE_URL=http://localhost:8000
```

> **Note:** If no credentials are provided, SplitPay AI automatically runs in **Offline/Demo Mode** with simulated PayPal sandbox checkouts so you can test every feature immediately!

### 4. Run the Unit Tests

```bash
python -m pytest -q
```

### 5. Launch the Application

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser to: **`http://localhost:8000`**

---

## 🧪 Postman API Testing (Sponsor Tool)

1. Open **Postman**.
2. Click **Import** and select [`splitpay.postman_collection.json`](./splitpay.postman_collection.json).
3. Run the collection to test all endpoints:
   - `GET /api/health`
   - `POST /api/receipt/sample`
   - `POST /api/split/parse-instruction`
   - `POST /api/split/calculate`
   - `POST /api/paypal/create-orders`
   - `POST /api/paypal/capture-order/{order_id}`
   - `POST /api/nudge/generate`

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
