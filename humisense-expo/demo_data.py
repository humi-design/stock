"""Deterministic synthetic data generator for the Humisense expo demo.

Generates bank_transactions.csv, broker_ledger.csv and settlement.csv with
12,842 + records and exactly 326 intentional exceptions. The data is
realistic but entirely synthetic - no real customer or financial data.

The reconciliation engine (reconciliation.py) consumes these files and must
produce exactly 326 exception cases for the demo numbers to line up:
    12,842 records processed
    12,516 matched
    326 exceptions
    247 investigated / 61 awaiting approval / 18 critical
"""
import csv
import os
import random
from datetime import date, timedelta

from config import config

GOOD_COUNT = 12_516
TOTAL_BANK = 12_842          # 326 problem transactions + 12,516 good
TOTAL_BROKER = 12_831        # 11 problem transactions missing from broker
TOTAL_SETTLEMENT = 12_796    # 46 problem transactions missing from settlement

# Featured transactions (must always exist in the demo)
FEATURED = {
    "TXN-82931": {"amount": 184500.0, "case_type": "SETTLEMENT_MISMATCH", "severity": "HIGH"},
    "TXN-82942": {"amount": 75000.0, "case_type": "DUPLICATE_TRANSACTION", "severity": "MEDIUM"},
    "TXN-82957": {"amount": 42500.0, "case_type": "MISSING_TRANSACTION", "severity": "HIGH"},
    "TXN-82961": {"amount": 128000.0, "case_type": "AMOUNT_MISMATCH", "severity": "HIGH"},
    "TXN-82978": {"amount": 96000.0, "case_type": "DATE_MISMATCH", "severity": "MEDIUM"},
}

# Problem-category budget (sum = 326). Each entry is (count, category).
PROBLEM_BUDGET = [
    (11, "missing_from_both"),      # missing from broker AND settlement
    (35, "missing_from_settlement"),# present in broker, missing from settlement
    (8, "settlement_mismatch"),     # broker shows 0/PENDING while settlement RECEIVED
    (80, "amount_mismatch"),
    (56, "date_mismatch"),
    (70, "status_mismatch"),
    (30, "account_mismatch"),
    (36, "duplicate"),              # appears twice in the broker ledger
]
assert sum(n for n, _ in PROBLEM_BUDGET) == 326

ACCOUNTS = [f"ACC-{1000 + i}" for i in range(400)]
STATUSES = ["SETTLED", "SETTLED", "SETTLED", "SETTLED", "PROCESSING", "PENDING"]
SETTLE_STATUSES = ["RECEIVED", "RECEIVED", "RECEIVED", "PAID_OUT"]


def _tdate(rng, back_days=60):
    """Random date within the last `back_days` days."""
    return date.today() - timedelta(days=rng.randint(0, back_days))


def _amount(rng):
    return round(rng.uniform(5000.0, 500000.0), 2)


def pick_problem_ids(rng):
    """Pick 326 deterministic problem transaction IDs around TXN-829xx."""
    ids = set()
    # Reserve the featured IDs + their close neighbours so they always appear.
    base = list(range(82910, 82990))
    rng.shuffle(base)
    for el in base:
        ids.add(el)
    # Fill to 326 with scattered IDs from the wider range.
    while len(ids) < 326:
        candidate = rng.randint(70000, 99999)
        if candidate not in ids and not (82910 <= candidate <= 82990):
            ids.add(candidate)
    return sorted(ids)


def _assign_categories(rng, problem_ids):
    """Assign each problem txn to exactly one category. Featured map first."""
    categories = {}
    featured_map = {
        "TXN-82931": "settlement_mismatch",
        "TXN-82942": "duplicate",
        "TXN-82957": "missing_from_both",
        "TXN-82961": "amount_mismatch",
        "TXN-82978": "date_mismatch",
    }
    remaining = []
    for pid in problem_ids:
        txn = f"TXN-{pid}"
        cat = featured_map.get(txn)
        categories[txn] = cat
        if cat is None:
            remaining.append(txn)

    # Shuffle remaining and carve out category budgets.
    rng.shuffle(remaining)
    idx = 0
    assign_map = {}
    budget = {name: count for count, name in PROBLEM_BUDGET}
    problem_ids_set = {f"TXN-{pid}" for pid in problem_ids}
    # pre-consumed featured categories
    for txn, cat in categories.items():
        if cat:
            budget[cat] -= 1
    for cat, count in budget.items():
        for k in range(count):
            assign_map[remaining[idx]] = cat
            idx += 1
    # merge
    merged = {}
    for txn in problem_ids_set:
        merged[txn] = assign_map.get(txn) or categories.get(txn)
    return merged


def generate():
    """Write the three synthetic CSV files into demo/."""
    rng = random.Random(42)
    problem_ids = pick_problem_ids(rng)
    categories = _assign_categories(rng, problem_ids)

    # Unique non-problem IDs in a generous but safe numeric range.
    problem_set = set(problem_ids)
    pool = [n for n in range(1000, 100000) if n not in problem_set]
    rng.shuffle(pool)
    good = [f"TXN-{pool[i]:05d}" for i in range(GOOD_COUNT)]
    del pool

    # Build one canonical record per good txn (identical across all systems).
    good_meta = {}
    for txn in good:
        good_meta[txn] = {
            "account": rng.choice(ACCOUNTS),
            "amount": _amount(rng),
            "date": _tdate(rng),
            "status": rng.choice(STATUSES),
        }

    # Build problem metadata per category.
    problem_meta = {}
    for txn, cat in categories.items():
        account = rng.choice(ACCOUNTS)
        amount = _amount(rng)
        base_date = _tdate(rng)
        status = rng.choice(STATUSES)
        problem_meta[txn] = {"cat": cat, "account": account, "amount": amount,
                             "date": base_date, "status": status}

    # Duplicate cases mirror a real (good) transaction's key fields so the
    # engine detects a value-based duplicate without adding extra rows.
    # Source ids are kept strictly smaller than every problem id so the
    # engine deterministically flags the duplicate (larger-id) entry.
    mirror_pool = [t for t in good if int(t.split("-")[1]) < 71000]
    rng.shuffle(mirror_pool)
    dup_idx = 0
    for txn, m in problem_meta.items():
        if m["cat"] == "duplicate":
            src = good_meta[mirror_pool[dup_idx]]
            dup_idx += 1
            if txn == "TXN-82942":
                src["amount"] = 75000.0
            m.update({"account": src["account"], "amount": src["amount"],
                      "date": src["date"], "status": src["status"]})

    # Override featured records exactly as the demo script needs.
    problem_meta["TXN-82931"] = {
        "cat": "settlement_mismatch", "account": "ACC-1822", "amount": 184500.0,
        "date": date.today() - timedelta(days=3),
        "status": "SETTLED",
    }
    problem_meta["TXN-82942"] = dict(problem_meta["TXN-82942"], amount=75000.0)
    problem_meta["TXN-82957"] = dict(problem_meta["TXN-82957"], amount=42500.0)
    problem_meta["TXN-82961"] = dict(problem_meta["TXN-82961"], amount=128000.0)
    problem_meta["TXN-82978"] = dict(problem_meta["TXN-82978"], amount=96000.0)

    # ------------------------------------------------------------------ #
    # BANK TRANSACTIONS  (12,842 rows: all good + all problem txns)
    # ------------------------------------------------------------------ #
    bank_rows = []
    for txn in good:
        m = good_meta[txn]
        bank_rows.append([txn, m["account"], f"{m['amount']:.2f}",
                          m["date"].isoformat(), m["status"]])
    for txn, m in problem_meta.items():
        bank_rows.append([txn, m["account"], f"{m['amount']:.2f}",
                          m["date"].isoformat(), m["status"]])
    # deterministic ordering with featured first
    def _sort_key(row):
        return (0 if row[0] in FEATURED else 1, row[0])
    bank_rows.sort(key=_sort_key)

    # ------------------------------------------------------------------ #
    # BROKER LEDGER  (12,831 rows)
    # Missing: the 11 missing_from_both transactions.
    # Duplicate: the duplicate-category txns appear TWICE.
    # Others mirror bank (with category-specific deviations).
    # ------------------------------------------------------------------ #
    broker_rows = []
    missing_both = {t for t, m in problem_meta.items() if m["cat"] == "missing_from_both"}
    dup_txns = {t for t, m in problem_meta.items() if m["cat"] == "duplicate"}

    for txn in good:
        m = good_meta[txn]
        broker_rows.append([txn, m["account"], f"{m['amount']:.2f}",
                            m["date"].isoformat(), m["status"]])
    for txn, m in problem_meta.items():
        if txn in missing_both:
            continue  # entirely missing from broker
        cat = m["cat"]
        if cat == "duplicate":
            # The broker ledger contains the value once (mirrored) though the
            # canonical transaction is still expected - visible in the UI as
            # an identical duplicate against the bank stream.
            broker_rows.append([txn, m["account"], f"{m['amount']:.2f}",
                                m["date"].isoformat(), m["status"]])
        elif cat == "settlement_mismatch":
            broker_rows.append([txn, m["account"], "0.00",
                                m["date"].isoformat(), "PENDING"])
        elif cat == "amount_mismatch":
            delta = rng.uniform(0.15, 0.6) * m["amount"]
            a = round(m["amount"] - delta, 2)
            if txn == "TXN-82961":
                a = 95800.00
            broker_rows.append([txn, m["account"], f"{a:.2f}",
                                m["date"].isoformat(), m["status"]])
        elif cat == "date_mismatch":
            d = m["date"] + timedelta(days=rng.randint(3, 12))
            if txn == "TXN-82978":
                d = m["date"] + timedelta(days=7)
            broker_rows.append([txn, m["account"], f"{m['amount']:.2f}",
                                d.isoformat(), m["status"]])
        elif cat == "status_mismatch":
            alt = {"SETTLED": "PENDING", "PENDING": "PROCESSING",
                   "PROCESSING": "FAILED", "FAILED": "SETTLED"}
            st = alt.get(m["status"], "PENDING")
            broker_rows.append([txn, m["account"], f"{m['amount']:.2f}",
                                m["date"].isoformat(), st])
        elif cat == "account_mismatch":
            acc = rng.choice([a for a in ACCOUNTS if a != m["account"]] or [m["account"]])
            broker_rows.append([txn, acc, f"{m['amount']:.2f}",
                                m["date"].isoformat(), m["status"]])
        else:  # missing_from_settlement - mirrors bank, fine in broker
            broker_rows.append([txn, m["account"], f"{m['amount']:.2f}",
                                m["date"].isoformat(), m["status"]])

    # ------------------------------------------------------------------ #
    # SETTLEMENT  (12,796 rows)
    # Present: good + problem txns except missing_from_both and
    # missing_from_settlement. Settlement status differs from bank status.
    # ------------------------------------------------------------------ #
    settle_rows = []
    missing_settlement = missing_both | {
        t for t, m in problem_meta.items() if m["cat"] == "missing_from_settlement"}
    settle_index = 29000

    def _settle_row(txn, m, forced_status=None):
        nonlocal settle_index
        settle_index += 1
        status = forced_status or rng.choice(SETTLE_STATUSES)
        return [f"SET-{settle_index}", txn, m["account"], f"{m['amount']:.2f}",
                m["date"].isoformat(), status]

    def _good_settle(txn):
        nonlocal settle_index
        settle_index += 1
        m = good_meta[txn]
        return [f"SET-{settle_index}", txn, m["account"], f"{m['amount']:.2f}",
                m["date"].isoformat(), rng.choice(SETTLE_STATUSES)]

    duplicate_txns = {t for t, m in problem_meta.items() if m["cat"] == "duplicate"}

    for txn in good:
        if txn in duplicate_txns:
            continue  # no settlement record for this synthetic txn id
        settle_rows.append(_good_settle(txn))

    for txn, m in problem_meta.items():
        if txn in missing_settlement:
            continue
        cat = m["cat"]
        if cat == "status_mismatch":
            settle_rows.append(_settle_row(txn, m, forced_status="RECEIVED"))
        elif cat == "date_mismatch":
            settle_rows.append(_settle_row(txn, m, forced_status="RECEIVED"))
        elif txn == "TXN-82931":
            settle_rows.append([f"SET-29182", txn, m["account"], "184500.00",
                                m["date"].isoformat(), "RECEIVED"])
        else:
            settle_rows.append(_settle_row(txn, m))

    def _write(path, header, rows):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    _write(os.path.join(config.DEMO_DIR, "bank_transactions.csv"),
           ["txn_id", "account_id", "amount", "date", "status"], bank_rows)
    _write(os.path.join(config.DEMO_DIR, "broker_ledger.csv"),
           ["txn_id", "account_id", "amount", "date", "status"], broker_rows)
    _write(os.path.join(config.DEMO_DIR, "settlement.csv"),
           ["settlement_id", "txn_id", "account_id", "amount", "date", "status"],
           settle_rows)

    return {
        "bank": len(bank_rows),
        "broker": len(broker_rows),
        "settlement": len(settle_rows),
        "good": GOOD_COUNT,
        "exceptions": len(problem_meta),
        "featured": list(FEATURED.keys()),
    }


if __name__ == "__main__":
    stats = generate()
    print("Demo data generated:", stats)