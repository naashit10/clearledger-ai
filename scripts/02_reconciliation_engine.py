"""
ClearLedger AI — Automated Reconciliation Engine
Three-way matching engine: GL vs Bank Statements
Matching tiers:
  1. Exact match  (journal hint + amount + date)
  2. Fuzzy match  (amount within tolerance + date within window)
  3. Unmatched    (flagged for investigation with break classification)
Author: Syed Naashit Hashmi
"""

import pandas as pd
import numpy as np
from datetime import datetime

DATA = "/home/claude/finrecon/data"
OUT = "/home/claude/finrecon/outputs"

AMOUNT_TOLERANCE = 500.0   # currency units
DATE_WINDOW_DAYS = 5

def load():
    gl = pd.read_csv(f"{DATA}/general_ledger.csv")
    bank = pd.read_csv(f"{DATA}/bank_statements.csv")
    gl_cash = gl[gl["gl_account"] == 1000].copy() if gl["gl_account"].dtype != object \
        else gl[gl["gl_account"] == "1000"].copy()
    gl_cash["posting_date"] = pd.to_datetime(gl_cash["posting_date"])
    bank["value_date"] = pd.to_datetime(bank["value_date"])
    return gl_cash, bank

def reconcile(gl_cash: pd.DataFrame, bank: pd.DataFrame):
    results = []
    bank_used = set()

    # Index bank by (entity, dr_cr) for speed
    bank_idx = {}
    for i, b in bank.iterrows():
        bank_idx.setdefault((b["entity"], b["dr_cr"]), []).append(i)

    for gi, g in gl_cash.iterrows():
        candidates = bank_idx.get((g["entity"], g["dr_cr"]), [])
        best = None
        best_tier = None

        for bi in candidates:
            if bi in bank_used:
                continue
            b = bank.loc[bi]
            amt_diff = abs(g["amount"] - b["amount"])
            date_diff = abs((g["posting_date"] - b["value_date"]).days)

            if amt_diff < 0.01 and date_diff == 0:
                best, best_tier = bi, "TIER1_EXACT"
                break
            elif amt_diff < 0.01 and date_diff <= DATE_WINDOW_DAYS:
                if best_tier not in ("TIER1_EXACT",):
                    best, best_tier = bi, "TIER2_TIMING"
            elif amt_diff <= AMOUNT_TOLERANCE and date_diff <= DATE_WINDOW_DAYS:
                if best_tier is None:
                    best, best_tier = bi, "TIER3_FUZZY_AMOUNT"

        if best is not None:
            bank_used.add(best)
            b = bank.loc[best]
            results.append({
                "journal_id": g["journal_id"],
                "bank_txn_id": b["bank_txn_id"],
                "entity": g["entity"],
                "gl_amount": g["amount"],
                "bank_amount": b["amount"],
                "amount_diff": round(g["amount"] - b["amount"], 2),
                "gl_date": g["posting_date"].date(),
                "bank_date": b["value_date"].date(),
                "date_diff_days": abs((g["posting_date"] - b["value_date"]).days),
                "match_tier": best_tier,
                "status": "MATCHED" if best_tier == "TIER1_EXACT" else "MATCHED_WITH_NOTE",
            })
        else:
            results.append({
                "journal_id": g["journal_id"],
                "bank_txn_id": None,
                "entity": g["entity"],
                "gl_amount": g["amount"],
                "bank_amount": None,
                "amount_diff": None,
                "gl_date": g["posting_date"].date(),
                "bank_date": None,
                "date_diff_days": None,
                "match_tier": "UNMATCHED",
                "status": "BREAK_GL_ONLY",
            })

    recon = pd.DataFrame(results)

    # Bank-only items (in bank, not matched to any GL)
    bank_only = bank[~bank.index.isin(bank_used)].copy()
    bank_only_records = pd.DataFrame({
        "journal_id": None,
        "bank_txn_id": bank_only["bank_txn_id"],
        "entity": bank_only["entity"],
        "gl_amount": None,
        "bank_amount": bank_only["amount"],
        "amount_diff": None,
        "gl_date": None,
        "bank_date": bank_only["value_date"].dt.date,
        "date_diff_days": None,
        "match_tier": "UNMATCHED",
        "status": "BREAK_BANK_ONLY",
    })
    recon = pd.concat([recon, bank_only_records], ignore_index=True)
    return recon

def summarize(recon: pd.DataFrame):
    total = len(recon)
    matched = (recon["status"].str.startswith("MATCHED")).sum()
    rate = matched / total * 100
    print(f"\n=== RECONCILIATION SUMMARY ===")
    print(f"Total records processed : {total:,}")
    print(f"Matched                 : {matched:,} ({rate:.1f}%)")
    print(f"\nBy tier:")
    print(recon["match_tier"].value_counts().to_string())
    print(f"\nBreaks by entity:")
    breaks = recon[recon["status"].str.startswith("BREAK")]
    print(breaks.groupby("entity").size().to_string())
    return {
        "total": int(total), "matched": int(matched), "match_rate": round(rate, 2),
        "breaks": int(total - matched),
    }

if __name__ == "__main__":
    t0 = datetime.now()
    gl_cash, bank = load()
    print(f"GL cash entries: {len(gl_cash):,} | Bank txns: {len(bank):,}")
    recon = reconcile(gl_cash, bank)
    recon.to_csv(f"{OUT}/reconciliation_results.csv", index=False)
    stats = summarize(recon)
    print(f"\nRuntime: {(datetime.now() - t0).seconds}s")
    print(f"Saved -> {OUT}/reconciliation_results.csv")
