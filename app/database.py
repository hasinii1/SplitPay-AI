"""
SQLite Database Layer for SplitPay AI
Manages persistent storage of Bills, Items, Shares, and PayPal Orders.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from app.config import get_settings


def get_db_path() -> str:
    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    return "splitpay.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db():
    """Initializes database tables if they do not exist."""
    conn = get_connection()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS bills (
            id TEXT PRIMARY KEY,
            merchant TEXT NOT NULL,
            date TEXT,
            subtotal REAL DEFAULT 0.0,
            tax REAL DEFAULT 0.0,
            tip REAL DEFAULT 0.0,
            discount REAL DEFAULT 0.0,
            total REAL DEFAULT 0.0,
            currency TEXT NOT NULL DEFAULT 'USD',
            receipt_currency TEXT NOT NULL DEFAULT 'USD',
            exchange_rate REAL,
            exchange_rate_date TEXT,
            status TEXT DEFAULT 'DRAFT',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bill_items (
            id TEXT PRIMARY KEY,
            bill_id TEXT NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER DEFAULT 1,
            consumers TEXT DEFAULT '[]',
            FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bill_shares (
            id TEXT PRIMARY KEY,
            bill_id TEXT NOT NULL,
            person TEXT NOT NULL,
            items_subtotal REAL DEFAULT 0.0,
            tax REAL DEFAULT 0.0,
            tip REAL DEFAULT 0.0,
            discount REAL DEFAULT 0.0,
            total REAL DEFAULT 0.0,
            paypal_order_id TEXT,
            paypal_approval_url TEXT,
            paypal_amount REAL,
            paypal_currency TEXT DEFAULT 'USD',
            status TEXT DEFAULT 'PENDING',
            paid_at TEXT,
            assigned_items_json TEXT DEFAULT '[]',
            qr_code_data TEXT,
            FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_bill_shares_order_id ON bill_shares(paypal_order_id);
        CREATE INDEX IF NOT EXISTS idx_bill_shares_bill_id ON bill_shares(bill_id);
        """)
        bill_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(bills)").fetchall()
        }
        if "currency" not in bill_columns:
            conn.execute(
                "ALTER TABLE bills ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD'"
            )
        if "receipt_currency" not in bill_columns:
            conn.execute(
                "ALTER TABLE bills ADD COLUMN receipt_currency TEXT NOT NULL DEFAULT 'USD'"
            )
            conn.execute(
                "UPDATE bills SET receipt_currency = currency WHERE currency = 'INR'"
            )
        if "exchange_rate" not in bill_columns:
            conn.execute("ALTER TABLE bills ADD COLUMN exchange_rate REAL")
        if "exchange_rate_date" not in bill_columns:
            conn.execute("ALTER TABLE bills ADD COLUMN exchange_rate_date TEXT")

        share_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(bill_shares)").fetchall()
        }
        if "paypal_amount" not in share_columns:
            conn.execute("ALTER TABLE bill_shares ADD COLUMN paypal_amount REAL")
        if "paypal_currency" not in share_columns:
            conn.execute(
                "ALTER TABLE bill_shares ADD COLUMN paypal_currency TEXT DEFAULT 'USD'"
            )
    conn.close()


# --- Database Operations ---

def create_bill(
    merchant: str,
    date: Optional[str],
    subtotal: float,
    tax: float,
    tip: float,
    discount: float,
    total: float,
    items: List[Dict[str, Any]],
    bill_id: Optional[str] = None,
    currency: str = "USD",
) -> str:
    conn = get_connection()
    b_id = bill_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO bills (id, merchant, date, subtotal, tax, tip, discount, total, currency, receipt_currency, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?)
            """,
            (
                b_id,
                merchant,
                date or "",
                subtotal,
                tax,
                tip,
                discount,
                total,
                currency,
                currency,
                now,
            ),
        )
        # Clear existing items if replacing
        conn.execute("DELETE FROM bill_items WHERE bill_id = ?", (b_id,))
        for item in items:
            item_id = str(uuid.uuid4())
            consumers_json = json.dumps(item.get("consumers", []))
            conn.execute(
                """
                INSERT INTO bill_items (id, bill_id, name, price, quantity, consumers)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (item_id, b_id, item.get("name", "Item"), float(item.get("price", 0.0)), int(item.get("quantity", 1)), consumers_json),
            )
    conn.close()
    return b_id


def save_shares(bill_id: str, shares: Dict[str, Any]):
    """Saves calculated individual shares for a bill."""
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM bill_shares WHERE bill_id = ?", (bill_id,))
        for person, data in shares.items():
            share_id = str(uuid.uuid4())
            assigned_json = json.dumps(data.get("assigned_items", []))
            conn.execute(
                """
                INSERT INTO bill_shares (
                    id, bill_id, person, items_subtotal, tax, tip, discount, total,
                    paypal_order_id, paypal_approval_url, status, assigned_items_json, qr_code_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    share_id,
                    bill_id,
                    person,
                    float(data.get("items_subtotal", 0.0)),
                    float(data.get("tax", 0.0)),
                    float(data.get("tip", 0.0)),
                    float(data.get("discount", 0.0)),
                    float(data.get("total", 0.0)),
                    data.get("paypal_order_id"),
                    data.get("paypal_approval_url"),
                    data.get("status", "PENDING"),
                    assigned_json,
                    data.get("qr_code_data"),
                ),
            )
        conn.execute("UPDATE bills SET status = 'SPLIT' WHERE id = ?", (bill_id,))
    conn.close()


def update_bill_currency(bill_id: str, currency: str):
    conn = get_connection()
    with conn:
        conn.execute(
            """
            UPDATE bills
            SET currency = ?,
                exchange_rate = CASE WHEN ? = 'INR' THEN exchange_rate ELSE NULL END,
                exchange_rate_date = CASE WHEN ? = 'INR' THEN exchange_rate_date ELSE NULL END
            WHERE id = ?
            """,
            (currency, currency, currency, bill_id),
        )
    conn.close()


def update_bill_exchange_rate(bill_id: str, rate: float, rate_date: str):
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE bills SET exchange_rate = ?, exchange_rate_date = ? WHERE id = ?",
            (rate, rate_date, bill_id),
        )
    conn.close()


def update_paypal_order(
    bill_id: str,
    person: str,
    paypal_order_id: str,
    paypal_approval_url: str,
    qr_code_data: Optional[str] = None,
    paypal_amount: Optional[float] = None,
    paypal_currency: str = "USD",
):
    conn = get_connection()
    with conn:
        conn.execute(
            """
            UPDATE bill_shares
            SET paypal_order_id = ?, paypal_approval_url = ?, qr_code_data = ?,
                paypal_amount = ?, paypal_currency = ?
            WHERE bill_id = ? AND person = ?
            """,
            (
                paypal_order_id,
                paypal_approval_url,
                qr_code_data,
                paypal_amount,
                paypal_currency,
                bill_id,
                person,
            ),
        )
        conn.execute("UPDATE bills SET status = 'PENDING_PAYMENT' WHERE id = ?", (bill_id,))
    conn.close()


def mark_share_paid(paypal_order_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    share_row = None
    with conn:
        cur = conn.execute(
            "SELECT * FROM bill_shares WHERE paypal_order_id = ?", (paypal_order_id,)
        )
        share_row = cur.fetchone()
        if share_row:
            conn.execute(
                """
                UPDATE bill_shares
                SET status = 'PAID', paid_at = ?
                WHERE paypal_order_id = ?
                """,
                (now, paypal_order_id),
            )
            # Check if all shares for this bill are now paid
            bill_id = share_row["bill_id"]
            pending_cur = conn.execute(
                "SELECT COUNT(*) as count FROM bill_shares WHERE bill_id = ? AND status != 'PAID'",
                (bill_id,),
            )
            if pending_cur.fetchone()["count"] == 0:
                conn.execute("UPDATE bills SET status = 'COMPLETED' WHERE id = ?", (bill_id,))
    conn.close()
    return dict(share_row) if share_row else None


def get_bill(bill_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,))
    bill = cur.fetchone()
    if not bill:
        conn.close()
        return None

    items_cur = conn.execute("SELECT * FROM bill_items WHERE bill_id = ?", (bill_id,))
    items = []
    for r in items_cur.fetchall():
        items.append({
            "id": r["id"],
            "name": r["name"],
            "price": r["price"],
            "quantity": r["quantity"],
            "consumers": json.loads(r["consumers"] or "[]"),
        })

    shares_cur = conn.execute("SELECT * FROM bill_shares WHERE bill_id = ?", (bill_id,))
    shares = []
    for s in shares_cur.fetchall():
        shares.append({
            "id": s["id"],
            "person": s["person"],
            "items_subtotal": s["items_subtotal"],
            "tax": s["tax"],
            "tip": s["tip"],
            "discount": s["discount"],
            "total": s["total"],
            "paypal_amount": s["paypal_amount"],
            "paypal_currency": s["paypal_currency"],
            "paypal_order_id": s["paypal_order_id"],
            "paypal_approval_url": s["paypal_approval_url"],
            "status": s["status"],
            "paid_at": s["paid_at"],
            "assigned_items": json.loads(s["assigned_items_json"] or "[]"),
            "qr_code_data": s["qr_code_data"],
        })

    conn.close()
    res = dict(bill)
    res["items"] = items
    res["shares"] = shares
    return res


def list_recent_bills(limit: int = 10) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.execute(
        """
        SELECT b.*,
               (SELECT COUNT(*) FROM bill_shares WHERE bill_id = b.id) as total_shares,
               (SELECT COUNT(*) FROM bill_shares WHERE bill_id = b.id AND status = 'PAID') as paid_shares
        FROM bills b
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
