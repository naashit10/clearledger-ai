"""
ClearLedger AI — Automated Month-End Reporting
Generates the close pack: KPI summary JSON (feeds dashboard),
AP aging, entity-level metrics, and management commentary.
Author: Syed Naashit Hashmi
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime

DATA = "/home/claude/finrecon/data"
OUT = "/home/claude/finrecon/outputs"

def main():
    gl = pd.read_csv(f"{DATA}/general_ledger.csv", dtype={"gl_account": str})
    inv = pd.read_csv(f"{DATA}/vendor_invoices.csv")
    ic = pd.read_csv(f"{DATA}/intercompany_transactions.csv")
    recon = pd.read_csv(f"{OUT}/reconciliation_results.csv")
    breaks = pd.read_csv(f"{OUT}/classified_breaks.csv")
    anomalies = pd.read_csv(f"{OUT}/flagged_anomalies.csv")

    # --- KPIs ---
    matched = recon["status"].str.startswith("MATCHED").sum()
    match_rate = matched / len(recon) * 100

    open_ap = inv[inv["status"].isin(["OPEN", "OVERDUE"])]["invoice_amount"].sum()
    overdue_ap = inv[inv["status"] == "OVERDUE"]["invoice_amount"].sum()

    ic_mismatch = ic[abs(ic["amount_sender"] - ic["amount_receiver"]) > 0.01]

    paid = inv[inv["status"] == "PAID"].copy()
    paid["days_to_pay"] = (pd.to_datetime(paid["paid_date"]) -
                           pd.to_datetime(paid["invoice_date"])).dt.days
    avg_dtp = paid["days_to_pay"].mean()

    # --- Monthly trend for dashboard ---
    # Bank-only items have no GL date, so fall back to the bank date; otherwise
    # they drop out of the trend and the monthly rates overstate the true match rate.
    recon["gl_date"] = pd.to_datetime(recon["gl_date"], errors="coerce")
    recon["bank_date"] = pd.to_datetime(recon["bank_date"], errors="coerce")
    recon["period"] = recon["gl_date"].fillna(recon["bank_date"]).dt.strftime("%Y-%m")
    trend = (recon.dropna(subset=["period"])
             .groupby("period")
             .agg(total=("status", "size"),
                  matched=("status", lambda s: s.str.startswith("MATCHED").sum()))
             .reset_index())
    trend["match_rate"] = (trend["matched"] / trend["total"] * 100).round(1)

    # entity summary
    entity_summary = (recon.groupby("entity")
                      .agg(total=("status", "size"),
                           matched=("status", lambda s: s.str.startswith("MATCHED").sum()))
                      .reset_index())
    entity_summary["match_rate"] = (entity_summary["matched"] / entity_summary["total"] * 100).round(1)

    # Unmatched breaks vs. all classified exceptions (which also include
    # matched-with-note items from the timing and fuzzy tiers)
    unmatched_breaks = int(recon["status"].str.startswith("BREAK").sum())
    n_months = int(trend["period"].nunique())
    ASSUMED_MIN_PER_MATCH = 1.5   # assumption: manual minutes avoided per matched item
    hours_total = matched * ASSUMED_MIN_PER_MATCH / 60
    hours_per_month = hours_total / n_months

    # break categories
    break_dist = breaks["break_category"].value_counts().to_dict()

    # GL monthly volumes
    gl_monthly = (gl.groupby("period")
                  .agg(entries=("journal_id", "size"),
                       total_value=("amount", "sum"))
                  .reset_index())

    # AP aging
    inv["due_date"] = pd.to_datetime(inv["due_date"])
    today = pd.Timestamp("2026-06-01")
    open_inv = inv[inv["status"].isin(["OPEN", "OVERDUE"])].copy()
    open_inv["days_overdue"] = (today - open_inv["due_date"]).dt.days
    open_inv["bucket"] = pd.cut(open_inv["days_overdue"],
                                bins=[-10**6, 0, 30, 60, 90, 10**6],
                                labels=["CURRENT", "1-30", "31-60", "61-90", "90+"])
    aging = (open_inv.groupby("bucket", observed=True)["invoice_amount"]
             .agg(["count", "sum"]).reset_index())
    aging.columns = ["bucket", "invoice_count", "amount"]

    kpis = {
        "generated_at": datetime.now().isoformat(),
        "headline": {
            "auto_match_rate_pct": round(match_rate, 1),
            "total_recon_items": int(len(recon)),
            "unmatched_breaks": unmatched_breaks,
            "classified_exceptions": int(len(breaks)),
            "open_ap_value": round(float(open_ap), 2),
            "overdue_ap_value": round(float(overdue_ap), 2),
            "avg_days_to_pay": round(float(avg_dtp), 1),
            "ic_mismatches": int(len(ic_mismatch)),
            "anomalies_flagged": int(len(anomalies)),
            "gl_entries_processed": int(len(gl)),
            "assumed_minutes_per_match": ASSUMED_MIN_PER_MATCH,
            "manual_effort_saved_hours_total": round(float(hours_total), 0),
            "manual_effort_saved_hours_per_month": round(float(hours_per_month), 1),
        },
        "match_trend": trend.to_dict(orient="records"),
        "entity_summary": entity_summary.to_dict(orient="records"),
        "break_distribution": break_dist,
        "gl_monthly": gl_monthly.to_dict(orient="records"),
        "ap_aging": aging.to_dict(orient="records"),
    }

    with open(f"{OUT}/close_pack_kpis.json", "w") as f:
        json.dump(kpis, f, indent=2, default=str)

    # --- Management commentary (template-based; LLM hook available) ---
    dominant_break = max(break_dist, key=break_dist.get)
    commentary = (
        f"Auto-reconciliation matched {match_rate:.1f}% of {len(recon):,} items this cycle, "
        f"avoiding an estimated {hours_total:.0f} analyst-hours over {n_months} months "
        f"(~{hours_per_month:.0f}/month, assuming {ASSUMED_MIN_PER_MATCH} min per matched item). "
        f"The dominant break category is {dominant_break.replace('_', ' ').title()} "
        f"({break_dist[dominant_break]:,} items; {unmatched_breaks:,} items remain unmatched in total); recommend prioritizing automated write-off rules "
        f"for sub-threshold bank charges and a T+1 timing-difference auto-clear policy. "
        f"{len(ic_mismatch):,} intercompany mismatches require entity-pair follow-up before close sign-off."
    )
    with open(f"{OUT}/management_commentary.txt", "w") as f:
        f.write(commentary)

    print("=== CLOSE PACK GENERATED ===")
    print(json.dumps(kpis["headline"], indent=2))
    print(f"\nCommentary:\n{commentary}")

if __name__ == "__main__":
    main()
