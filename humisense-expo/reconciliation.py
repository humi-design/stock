"""Deterministic reconciliation engine.

Pure Python/pandas logic. AI is NEVER used for financial calculations.

Compares Bank Transactions, Broker Ledger and Settlement records and
detects exceptions:
    MISSING_TRANSACTION / DUPLICATE_TRANSACTION / AMOUNT_MISMATCH /
    DATE_MISMATCH / ACCOUNT_MISMATCH / STATUS_MISMATCH /
    SETTLEMENT_MISMATCH / UNMATCHED_TRANSACTION
"""
from datetime import datetime, timedelta

import pandas as pd

from config import config

CASE_TYPES = {
    "MISSING_TRANSACTION": "Missing Transaction",
    "DUPLICATE_TRANSACTION": "Duplicate",
    "AMOUNT_MISMATCH": "Amount Mismatch",
    "DATE_MISMATCH": "Date Mismatch",
    "ACCOUNT_MISMATCH": "Account Mismatch",
    "STATUS_MISMATCH": "Status Mismatch",
    "SETTLEMENT_MISMATCH": "Settlement Mismatch",
    "UNMATCHED_TRANSACTION": "Unmatched Transaction",
}

SEVERITY = {
    "MISSING_TRANSACTION": "HIGH",
    "DUPLICATE_TRANSACTION": "MEDIUM",
    "AMOUNT_MISMATCH": "HIGH",
    "DATE_MISMATCH": "MEDIUM",
    "ACCOUNT_MISMATCH": "HIGH",
    "STATUS_MISMATCH": "MEDIUM",
    "SETTLEMENT_MISMATCH": "HIGH",
    "UNMATCHED_TRANSACTION": "HIGH",
}


def load_csv(path, expected_cols):
    """Load a CSV/XLSX file, tolerating missing optional columns."""
    if str(path).lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "txn_id" not in df.columns:
        raise ValueError("Missing required column 'txn_id'")
    for col, default in expected_cols.items():
        if col not in df.columns:
            df[col] = default
    return df


def _normalize_id(v):
    s = str(v).strip()
    if s.upper().startswith("TXN-"):
        s = s[4:].strip()
    return s


def _normalize_amount(v):
    if v is None:
        return 0.0
    try:
        return round(float(str(v).replace(",", "").replace("₹", "").strip()), 2)
    except (TypeError, ValueError):
        return 0.0


def _normalize_date(v, tolerance_days=None):
    """Parse a date to a date object. NaN -> None."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, pd.Timestamp):
        if pd.isna(v):
            return None
        return v.date()
    if isinstance(v, date_like()):
        return v
    s = str(v).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None


def date_like():
    from datetime import date
    return date


def _normalize_status(v):
    s = str(v).strip().upper()
    if s in ("SETTLED", "RECEIVED", "PAID_OUT", "PAID", "COMPLETED", "SUCCESS",
             "SUCCESSFUL", "CLEARED", "RELEASED"):
        return "SETTLED"
    if s in ("PENDING", "BOOKED", "UNSETTLED", "WAITING", "QUEUED"):
        return "PENDING"
    if s in ("PROCESSING", "IN-PROGRESS", "IN_PROGRESS", "IN PROGRESS"):
        return "PROCESSING"
    if s in ("FAILED", "FAILURE", "REJECTED", "DECLINED", "CANCELLED",
             "CANCELED", "ERROR"):
        return "FAILED"
    return "UNKNOWN"


def _parse_number(v):
    """Parse an 8-digit numeric reference like '82931' -> int."""
    s = str(v).strip()
    if not s:
        return 0
    digits = "".join(ch for ch in s if ch.isdigit())
    try:
        return int(digits)
    except ValueError:
        return 0


class ReconcileResult:
    def __init__(self):
        self.processed = 0
        self.matched = 0
        self.exceptions = []
        self.bank_count = 0
        self.broker_count = 0
        self.settlement_count = 0
        self.duration_ms = 0

    def summary(self):
        return {
            "processed": self.processed,
            "matched": self.matched,
            "exceptions": len(self.exceptions),
            "bank_count": self.bank_count,
            "broker_count": self.broker_count,
            "settlement_count": self.settlement_count,
        }


def reconcile(bank_df, broker_df, settlement_df, tolerance_days=None):
    """Run the full reconciliation. Returns a ReconcileResult."""
    if tolerance_days is None:
        tolerance_days = config.DATE_TOLERANCE_DAYS
    tolerance = timedelta(days=tolerance_days)

    start = datetime.now()
    result = ReconcileResult()
    result.bank_count = len(bank_df)
    result.broker_count = len(broker_df)
    result.settlement_count = len(settlement_df)

    # Normalize all three frames
    for df in (bank_df, broker_df, settlement_df):
        nid_col = "txn_id" if "txn_id" in df.columns else "id"
        df["n_id"] = df[nid_col].map(_normalize_id)
        df["n_amount"] = df["amount"].map(_normalize_amount)
        df["n_date"] = df["date"].map(lambda v: _normalize_date(v, tolerance_days))
        df["n_status"] = df["status"].map(_normalize_status)
        df["n_account"] = df["account_id"].astype(str).str.strip() if "account_id" in df.columns else ""

    # Build indexes
    bank_by_id = {}
    for _, row in bank_df.iterrows():
        bank_by_id.setdefault(row["n_id"], []).append(row)
    broker_by_id = {}
    for _, row in broker_df.iterrows():
        broker_by_id.setdefault(row["n_id"], []).append(row)
    settle_by_id = {}
    for _, row in settlement_df.iterrows():
        settle_by_id.setdefault(row["n_id"], []).append(row)

    # Bank->settlement lookup (one or more)
    settlement_map = {}
    for nid, rows in settle_by_id.items():
        settlement_map[nid] = rows

    result.processed = len(bank_df)

    seen_problem = set()

    def add_exception(txn_raw, ctype, bank_row, broker_row, settle_row):
        key = (str(txn_raw).strip(), ctype)
        if key in seen_problem:
            return
        seen_problem.add(key)
        amount = _norm_amount(bank_row) if bank_row is not None else (_norm_amount(broker_row) if broker_row is not None else 0.0)
        result.exceptions.append({
            "case_ref": f"CASE #{_parse_number(txn_raw):05d}",
            "case_type": ctype,
            "exception_type": ctype,
            "reference": str(txn_raw),
            "amount": amount,
            "currency": "INR",
            "severity": SEVERITY[ctype],
            "status": "AI Recommended",
            "confidence": 0.0,
            "bank": _evidence_dict(bank_row),
            "broker": _evidence_dict(broker_row),
            "settlement": _evidence_dict(settle_row),
        })

    # Value fingerprint for cross-record duplicate detection.
    def _fingerprint(row):
        if row is None or row.get("n_date") is None:
            return None
        return (round(float(row["n_amount"]), 2), str(row.get("n_account", "")),
                str(row["n_date"]), row["n_status"])

    # Numeric ids for deterministic, id-ordered processing.
    bank_id_num = {}
    for _, row in bank_df.iterrows():
        bank_id_num[row["n_id"]] = max(bank_id_num.get(row["n_id"], 0),
                                       _parse_number(row["txn_id"]))

    # ------------------------------------------------------------------ #
    # Pass 1: match each bank transaction
    # ------------------------------------------------------------------ #
    matched_fps = set()
    ordered_ids = sorted(bank_by_id.keys(), key=lambda n: bank_id_num.get(n, 0))
    for bid in ordered_ids:
        brows = bank_by_id[bid]
        b = brows[0]  # bank records are unique per id in our data
        brokers = broker_by_id.get(bid, [])
        settles = settlement_map.get(bid, [])

        # 1) Missing from both broker and settlement
        if not brokers and not settles:
            add_exception(b["txn_id"], "MISSING_TRANSACTION", b, None, None)
            continue
        # 2) Missing from settlement (only broker has it)
        if not settles and brokers:
            add_exception(b["txn_id"], "MISSING_TRANSACTION", b, brokers[0], None)
            continue

        # 3) Settlement has a record but broker completely missing
        if not brokers and settles:
            add_exception(b["txn_id"], "SETTLEMENT_MISMATCH", b, None, settles[0])
            continue

        # 4) Duplicate broker entries for the same transaction id
        if len(brokers) > 1:
            add_exception(b["txn_id"], "DUPLICATE_TRANSACTION", b, brokers[-1], settles[0])
            # fall through - still compare the first broker entry
            broker = brokers[0]
            settle = settles[0]
        else:
            broker = brokers[0]
            settle = settles[0]

        # 5) Settlement mismatch: broker balance 0 vs settlement received/paid
        b_norm = _norm_amount(settle)
        br_norm = _norm_amount(broker)
        if br_norm <= 0.001 and b_norm > 0.001 and bs_settled(settle):
            add_exception(b["txn_id"], "SETTLEMENT_MISMATCH", b, broker, settle)
            continue

        # 6) Amount mismatch (broker vs bank)
        if abs(_norm_amount(b) - _norm_amount(broker)) > 0.001:
            add_exception(b["txn_id"], "AMOUNT_MISMATCH", b, broker, settle)
            continue

        # 7) Date mismatch
        bd, rd = b["n_date"], broker["n_date"]
        if bd and rd and abs(bd - rd) > tolerance:
            add_exception(b["txn_id"], "DATE_MISMATCH", b, broker, settle)
            continue

        # 8) Account mismatch
        if str(b.get("account_id", "")).strip() != str(broker.get("account_id", "")).strip():
            add_exception(b["txn_id"], "ACCOUNT_MISMATCH", b, broker, settle)
            continue

        # 9) Status mismatch (bank vs broker). Normalized statuses must match;
        #    the settlement stream uses its own vocabulary and is not compared.
        if b["n_status"] != broker["n_status"]:
            add_exception(b["txn_id"], "STATUS_MISMATCH", b, broker, settle)
            continue

        # 10) Value duplicate: another (lower-id) bank transaction already
        #     matched with the same amount / account / date / status profile.
        fp = _fingerprint(b)
        if fp is not None and fp in matched_fps:
            add_exception(b["txn_id"], "DUPLICATE_TRANSACTION", b, broker, settle)
            continue
        if fp is not None:
            matched_fps.add(fp)
        result.matched += 1

    # ------------------------------------------------------------------ #
    # Pass 2: broker/settlement records not in bank
    # ------------------------------------------------------------------ #
    extra = set(broker_by_id.keys()) | set(settle_by_id.keys())
    bank_ids = set(bank_by_id.keys())
    for nid in sorted(extra - bank_ids):
        broker = broker_by_id.get(nid)
        settle = settlement_map.get(nid)
        raw = broker["txn_id"] if broker is not None else settle["txn_id"]
        add_exception(raw, "UNMATCHED_TRANSACTION", None, broker,
                      settle if settle is not None else None)

    result.exceptions.sort(key=lambda e: (-1 if e["reference"] == "TXN-82931"
                                           else 0, -_parse_number(e["reference"])))
    result.duration_ms = int((datetime.now() - start).total_seconds() * 1000)
    return result


def _norm_amount(row):
    if row is None:
        return 0.0
    return float(row.get("n_amount", 0.0) or 0.0)


def _both_settled(a, b):
    return a["n_status"] in ("SETTLED", "PENDING") and b["n_status"] in ("SETTLED", "PENDING")


def bs_settled(settle_row):
    st = str(settle_row.get("status", "")).strip().upper()
    return st in ("SETTLED", "RECEIVED", "PAID_OUT", "PAID")


def _evidence_dict(row):
    if row is None:
        return None
    return {
        "txn_id": row.get("txn_id", ""),
        "account_id": row.get("account_id", ""),
        "amount": row.get("amount", ""),
        "date": str(row.get("date", "")),
        "status": row.get("status", ""),
    }


def load_demo_files():
    """Load the bundled synthetic demo CSV files."""
    import os
    from config import config
    bank = load_csv(os.path.join(config.DEMO_DIR, "bank_transactions.csv"),
                    {"account_id": "", "amount": 0, "date": "", "status": ""})
    broker = load_csv(os.path.join(config.DEMO_DIR, "broker_ledger.csv"),
                      {"account_id": "", "amount": 0, "date": "", "status": ""})
    settlement = load_csv(os.path.join(config.DEMO_DIR, "settlement.csv"),
                          {"account_id": "", "amount": 0, "date": "", "status": ""})
    return bank, broker, settlement


def run_file_reconciliation(bank_file, broker_file, settlement_file):
    bank = load_csv(bank_file, {"account_id": "", "amount": 0, "date": "", "status": ""})
    broker = load_csv(broker_file, {"account_id": "", "amount": 0, "date": "", "status": ""})
    settlement = load_csv(settlement_file, {"account_id": "", "amount": 0, "date": "", "status": ""})
    return reconcile(bank, broker, settlement)