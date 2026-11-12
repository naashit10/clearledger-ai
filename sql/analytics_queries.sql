-- =====================================================================
-- ClearLedger AI — SQL Analytics Library
-- Reconciliation, AP aging, and financial close analytics
-- Demonstrates: CTEs, window functions, aggregations, date logic
-- Author: Syed Naashit Hashmi
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Reconciliation match-rate trend by month and entity
-- ---------------------------------------------------------------------
WITH monthly AS (
    SELECT
        entity,
        DATE_FORMAT(gl_date, '%Y-%m') AS period,
        COUNT(*)                                                  AS total_items,
        SUM(CASE WHEN status LIKE 'MATCHED%' THEN 1 ELSE 0 END)   AS matched_items
    FROM reconciliation_results
    GROUP BY entity, DATE_FORMAT(gl_date, '%Y-%m')
)
SELECT
    entity,
    period,
    total_items,
    matched_items,
    ROUND(matched_items * 100.0 / total_items, 2) AS match_rate_pct,
    ROUND(matched_items * 100.0 / total_items, 2)
        - LAG(ROUND(matched_items * 100.0 / total_items, 2))
          OVER (PARTITION BY entity ORDER BY period)  AS mom_change
FROM monthly
ORDER BY entity, period;

-- ---------------------------------------------------------------------
-- 2. Top 10 largest unresolved breaks per entity (ROW_NUMBER)
-- ---------------------------------------------------------------------
WITH ranked_breaks AS (
    SELECT
        entity,
        journal_id,
        bank_txn_id,
        COALESCE(gl_amount, bank_amount) AS break_amount,
        status,
        ROW_NUMBER() OVER (
            PARTITION BY entity
            ORDER BY COALESCE(gl_amount, bank_amount) DESC
        ) AS rn
    FROM reconciliation_results
    WHERE status LIKE 'BREAK%'
)
SELECT entity, journal_id, bank_txn_id, break_amount, status
FROM ranked_breaks
WHERE rn <= 10
ORDER BY entity, break_amount DESC;

-- ---------------------------------------------------------------------
-- 3. AP aging buckets with running totals (window SUM)
-- ---------------------------------------------------------------------
WITH aging AS (
    SELECT
        vendor,
        entity,
        invoice_id,
        invoice_amount,
        DATEDIFF(CURRENT_DATE, due_date) AS days_overdue,
        CASE
            WHEN DATEDIFF(CURRENT_DATE, due_date) <= 0  THEN 'CURRENT'
            WHEN DATEDIFF(CURRENT_DATE, due_date) <= 30 THEN '1-30'
            WHEN DATEDIFF(CURRENT_DATE, due_date) <= 60 THEN '31-60'
            WHEN DATEDIFF(CURRENT_DATE, due_date) <= 90 THEN '61-90'
            ELSE '90+'
        END AS aging_bucket
    FROM vendor_invoices
    WHERE status IN ('OPEN', 'OVERDUE')
)
SELECT
    entity,
    aging_bucket,
    COUNT(*)                AS invoice_count,
    SUM(invoice_amount)     AS bucket_amount,
    SUM(SUM(invoice_amount)) OVER (
        PARTITION BY entity
        ORDER BY FIELD(aging_bucket, 'CURRENT','1-30','31-60','61-90','90+')
    ) AS running_exposure
FROM aging
GROUP BY entity, aging_bucket
ORDER BY entity, FIELD(aging_bucket, 'CURRENT','1-30','31-60','61-90','90+');

-- ---------------------------------------------------------------------
-- 4. Vendor payment performance: avg days-to-pay + percentile rank
-- ---------------------------------------------------------------------
SELECT
    vendor,
    COUNT(*)                                            AS paid_invoices,
    ROUND(AVG(DATEDIFF(paid_date, invoice_date)), 1)    AS avg_days_to_pay,
    ROUND(PERCENT_RANK() OVER (
        ORDER BY AVG(DATEDIFF(paid_date, invoice_date))
    ) * 100, 1)                                         AS payment_speed_percentile
FROM vendor_invoices
WHERE status = 'PAID'
GROUP BY vendor
ORDER BY avg_days_to_pay;

-- ---------------------------------------------------------------------
-- 5. Intercompany mismatch detection (sender vs receiver)
-- ---------------------------------------------------------------------
SELECT
    ic_id,
    from_entity,
    to_entity,
    amount_sender,
    amount_receiver,
    ROUND(amount_sender - amount_receiver, 2) AS variance,
    nature,
    settlement_status
FROM intercompany_transactions
WHERE ABS(amount_sender - amount_receiver) > 0.01
ORDER BY ABS(amount_sender - amount_receiver) DESC;

-- ---------------------------------------------------------------------
-- 6. Month-end close dashboard: GL activity summary (NTILE quartiles)
-- ---------------------------------------------------------------------
WITH monthly_activity AS (
    SELECT
        period,
        entity,
        gl_account_name,
        SUM(CASE WHEN dr_cr = 'DR' THEN amount ELSE 0 END) AS total_dr,
        SUM(CASE WHEN dr_cr = 'CR' THEN amount ELSE 0 END) AS total_cr,
        COUNT(*) AS entry_count
    FROM general_ledger
    GROUP BY period, entity, gl_account_name
)
SELECT
    *,
    NTILE(4) OVER (PARTITION BY period ORDER BY entry_count DESC) AS activity_quartile
FROM monthly_activity
ORDER BY period DESC, entry_count DESC;

-- ---------------------------------------------------------------------
-- 7. Manual journal entries posted on weekends (audit query)
-- ---------------------------------------------------------------------
SELECT
    journal_id,
    posting_date,
    DAYNAME(posting_date) AS day_name,
    entity,
    gl_account_name,
    amount,
    posted_by
FROM general_ledger
WHERE source_system = 'MANUAL_JE'
  AND DAYOFWEEK(posting_date) IN (1, 7)
ORDER BY amount DESC;

-- ---------------------------------------------------------------------
-- 8. Duplicate payment detection (same vendor+amount+date)
-- ---------------------------------------------------------------------
SELECT
    vendor,
    invoice_date,
    invoice_amount,
    COUNT(*)                          AS occurrence_count,
    GROUP_CONCAT(invoice_id)          AS invoice_ids
FROM vendor_invoices
GROUP BY vendor, invoice_date, invoice_amount
HAVING COUNT(*) > 1
ORDER BY invoice_amount DESC;
