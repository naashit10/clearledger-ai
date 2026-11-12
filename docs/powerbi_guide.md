# Power BI Build Guide — ClearLedger AI Dashboard

This guide walks through rebuilding the ClearLedger AI command center in **Power BI Desktop** using the CSVs in `/data` and `/outputs`.

---

## 1. Data Model (Star Schema)

**Fact tables:**
- `reconciliation_results.csv` (fact_recon)
- `general_ledger.csv` (fact_gl)
- `vendor_invoices.csv` (fact_ap)

**Dimension tables (create in Power Query):**
- `dim_entity` — extract distinct entities
- `dim_date` — standard date table (mark as Date Table)
- `dim_break_category` — from classified_breaks.csv

**Relationships:**
```
dim_date[date]   1 ──── * fact_recon[gl_date]
dim_date[date]   1 ──── * fact_gl[posting_date]
dim_entity[code] 1 ──── * fact_recon[entity]
dim_entity[code] 1 ──── * fact_ap[entity]
```

---

## 2. Power Query Transformations

```
// Promote headers, set types
= Table.TransformColumnTypes(Source, {
    {"gl_amount", Currency.Type},
    {"gl_date", type date},
    {"match_tier", type text}
})

// Add Match Flag column
= Table.AddColumn(prev, "is_matched",
    each if Text.StartsWith([status], "MATCHED") then 1 else 0)
```

---

## 3. Core DAX Measures

```dax
Total Items = COUNTROWS(fact_recon)

Matched Items =
CALCULATE(COUNTROWS(fact_recon), fact_recon[is_matched] = 1)

Match Rate % =
DIVIDE([Matched Items], [Total Items], 0) * 100

Match Rate MoM Δ =
VAR Curr = [Match Rate %]
VAR Prev = CALCULATE([Match Rate %], DATEADD(dim_date[date], -1, MONTH))
RETURN Curr - Prev

Open Breaks =
CALCULATE(COUNTROWS(fact_recon),
    LEFT(fact_recon[status], 5) = "BREAK")

Open AP Value =
CALCULATE(SUM(fact_ap[invoice_amount]),
    fact_ap[status] IN {"OPEN", "OVERDUE"})

Overdue AP % =
DIVIDE(
    CALCULATE(SUM(fact_ap[invoice_amount]), fact_ap[status] = "OVERDUE"),
    [Open AP Value], 0) * 100

Analyst Hours Saved =
[Matched Items] * 1.5 / 60   -- 1.5 min saved per auto-matched item

Anomaly Rate % =
DIVIDE(
    CALCULATE(COUNTROWS(fact_gl), fact_gl[is_anomaly] = 1),
    COUNTROWS(fact_gl), 0) * 100
```

---

## 4. Report Pages

### Page 1 — Executive Summary
- KPI cards: Match Rate %, Open Breaks, Open AP Value, Hours Saved
- Line + column combo: Match Rate trend with item volumes
- Donut: Break category distribution

### Page 2 — Reconciliation Deep Dive
- Matrix: entity × match tier with conditional formatting
- Decomposition tree: breaks → entity → category → amount band
- Table: Top 20 unresolved breaks with drill-through

### Page 3 — AP & Anomaly Watch
- Clustered bar: AP aging buckets
- Scatter: anomaly score vs amount (flagged journals)
- Slicer panel: entity, period, source system

---

## 5. Refresh Strategy

For a production simulation, point Power Query at the `/outputs` folder and re-run the Python pipeline — Power BI refresh picks up new results automatically. Mention **Power Automate** as the orchestration trigger in interviews (schedule pipeline → refresh dataset → email close pack).
