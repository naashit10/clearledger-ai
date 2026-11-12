"""
ClearLedger AI — Synthetic Financial Data Generator
Generates realistic enterprise financial datasets for reconciliation:
- General Ledger (GL) entries
- Bank statement transactions
- Vendor invoices
- Intercompany transactions
Author: Syed Naashit Hashmi
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

np.random.seed(42)
random.seed(42)

OUT = "/home/claude/finrecon/data"

# ---------------- Config ----------------
N_GL = 60000          # GL entries
START = datetime(2025, 1, 1)
END = datetime(2026, 5, 31)
DAYS = (END - START).days

ENTITIES = ["AMX-IN-01", "AMX-IN-02", "AMX-SG-01", "AMX-UK-01", "AMX-US-01"]
COST_CENTERS = [f"CC{c}" for c in range(1001, 1021)]
GL_ACCOUNTS = {
    "1000": "Cash & Bank",
    "1100": "Accounts Receivable",
    "1200": "Prepaid Expenses",
    "2000": "Accounts Payable",
    "2100": "Accrued Liabilities",
    "4000": "Card Fee Revenue",
    "4100": "Interest Income",
    "4200": "FX Gain/Loss",
    "5000": "Vendor Expenses",
    "5100": "Employee Costs",
    "5200": "Technology Costs",
    "5300": "Marketing Spend",
}
VENDORS = [
    "TechServe Solutions", "Global Facilities Mgmt", "DataStream Analytics",
    "CloudNine Infra", "Meridian Consulting", "Apex Marketing Group",
    "SecureNet Systems", "OfficeWorks Supplies", "TransGlobal Logistics",
    "Quantum HR Services", "BlueRiver Media", "CoreBanking Tech",
    "Stellar Events Co", "PrimeLegal Advisors", "EcoClean Services",
]
CURRENCIES = {"AMX-IN-01": "INR", "AMX-IN-02": "INR", "AMX-SG-01": "SGD",
              "AMX-UK-01": "GBP", "AMX-US-01": "USD"}
PAYMENT_METHODS = ["NEFT", "RTGS", "WIRE", "ACH", "CHEQUE", "INTERNAL"]

def rand_date():
    return START + timedelta(days=int(np.random.uniform(0, DAYS)),
                             hours=int(np.random.uniform(8, 20)),
                             minutes=int(np.random.uniform(0, 60)))

def doc_no(prefix, i):
    return f"{prefix}-{2025}-{i:07d}"

# ---------------- 1. General Ledger ----------------
print("Generating GL entries...")
rows = []
for i in range(N_GL):
    entity = random.choice(ENTITIES)
    acct = random.choice(list(GL_ACCOUNTS.keys()))
    dt = rand_date()
    base = abs(np.random.lognormal(10.2, 1.4))
    amount = round(base, 2)
    drcr = random.choice(["DR", "CR"])
    rows.append({
        "journal_id": doc_no("JE", i + 1),
        "posting_date": dt.strftime("%Y-%m-%d"),
        "period": dt.strftime("%Y-%m"),
        "entity": entity,
        "cost_center": random.choice(COST_CENTERS),
        "gl_account": acct,
        "gl_account_name": GL_ACCOUNTS[acct],
        "currency": CURRENCIES[entity],
        "amount": amount,
        "dr_cr": drcr,
        "source_system": random.choices(
            ["ORACLE_GL", "SAP_FI", "MANUAL_JE", "SUBLEDGER_AP", "SUBLEDGER_AR"],
            weights=[40, 25, 8, 15, 12])[0],
        "description": "",
        "posted_by": f"user{random.randint(100, 180)}",
    })
gl = pd.DataFrame(rows)

# Realism patch: manual journals are where round-number postings concentrate.
# Uses its own RNG so the main random streams (and downstream data) are unchanged.
_rng_round = np.random.default_rng(7)
_manual = gl.index[gl["source_system"] == "MANUAL_JE"]
_round_idx = _rng_round.choice(_manual, size=int(len(_manual) * 0.15), replace=False)
gl.loc[_round_idx, "amount"] = (gl.loc[_round_idx, "amount"] / 1000).round().clip(lower=1) * 1000

DESCRIPTIONS = {
    "1000": ["Bank transfer settlement", "Cash sweep to concentration account", "Daily settlement clearing"],
    "1100": ["Customer receipt applied", "AR invoice booked", "Credit memo adjustment"],
    "1200": ["Prepaid insurance amortization", "Annual license prepayment", "Rent prepaid recognition"],
    "2000": ["Vendor invoice booked", "AP payment run", "Vendor credit applied"],
    "2100": ["Month-end accrual", "Reversal of prior accrual", "Bonus accrual provision"],
    "4000": ["Card network fee revenue", "Merchant service fee", "Annual card fee recognition"],
    "4100": ["Interest on deposits", "Investment income accrual", "Interest income recognition"],
    "4200": ["FX revaluation gain", "FX translation adjustment", "Realized FX loss on settlement"],
    "5000": ["Vendor service invoice", "Contractor payment", "Facility maintenance expense"],
    "5100": ["Payroll posting", "Employee reimbursement", "Benefits expense allocation"],
    "5200": ["Cloud infrastructure invoice", "Software license renewal", "IT support services"],
    "5300": ["Digital campaign spend", "Event sponsorship", "Brand media buy"],
}
gl["description"] = gl["gl_account"].apply(lambda a: random.choice(DESCRIPTIONS[a]))

gl.to_csv(f"{OUT}/general_ledger.csv", index=False)
print(f"  GL: {len(gl):,} rows")

# ---------------- 2. Bank Statements (with reconciliation breaks) ----------------
print("Generating bank statements...")
cash_gl = gl[gl["gl_account"] == "1000"].copy()
bank_rows = []
for idx, r in cash_gl.iterrows():
    roll = np.random.uniform()
    if roll < 0.86:  # clean match
        amt = r["amount"]
        dt = r["posting_date"]
        status_seed = "match"
    elif roll < 0.92:  # timing difference (1-4 days later)
        amt = r["amount"]
        dt = (datetime.strptime(r["posting_date"], "%Y-%m-%d")
              + timedelta(days=random.randint(1, 4))).strftime("%Y-%m-%d")
        status_seed = "timing"
    elif roll < 0.96:  # amount mismatch (bank charges/partial)
        amt = round(r["amount"] - abs(np.random.normal(150, 80)), 2)
        dt = r["posting_date"]
        status_seed = "amount_break"
    else:  # missing in bank entirely
        continue
    bank_rows.append({
        "bank_txn_id": f"BNK-{idx:08d}",
        "value_date": dt,
        "entity": r["entity"],
        "currency": r["currency"],
        "amount": amt,
        "dr_cr": r["dr_cr"],
        "counterparty": random.choice(VENDORS + ["Internal Transfer", "Card Settlement Network"]),
        "payment_method": random.choice(PAYMENT_METHODS),
        "bank_reference": f"REF{random.randint(10**9, 10**10 - 1)}",
        "gl_journal_hint": r["journal_id"],
        "_seed": status_seed,
    })

# unmatched bank-only noise (bank charges, interest)
for j in range(800):
    entity = random.choice(ENTITIES)
    dt = rand_date()
    bank_rows.append({
        "bank_txn_id": f"BNK-N{j:07d}",
        "value_date": dt.strftime("%Y-%m-%d"),
        "entity": entity,
        "currency": CURRENCIES[entity],
        "amount": round(abs(np.random.normal(400, 250)), 2),
        "dr_cr": random.choice(["DR", "CR"]),
        "counterparty": random.choice(["Bank Charges", "Interest Credit", "Govt Levy", "SWIFT Fee"]),
        "payment_method": "INTERNAL",
        "bank_reference": f"REF{random.randint(10**9, 10**10 - 1)}",
        "gl_journal_hint": "",
        "_seed": "bank_only",
    })

bank = pd.DataFrame(bank_rows)
bank_public = bank.drop(columns=["_seed", "gl_journal_hint"])
bank_public.to_csv(f"{OUT}/bank_statements.csv", index=False)
bank.to_csv(f"{OUT}/_bank_internal_seed.csv", index=False)  # internal for recon engine validation
print(f"  Bank: {len(bank):,} rows")

# ---------------- 3. Vendor Invoices ----------------
print("Generating vendor invoices...")
inv_rows = []
for i in range(9000):
    entity = random.choice(ENTITIES)
    dt = rand_date()
    due = dt + timedelta(days=random.choice([15, 30, 45, 60]))
    amount = round(abs(np.random.lognormal(10.5, 1.1)), 2)
    paid_roll = np.random.uniform()
    if paid_roll < 0.78:
        status = "PAID"
        paid_date = due + timedelta(days=int(np.random.normal(-2, 6)))
    elif paid_roll < 0.93:
        status = "OPEN"
        paid_date = None
    else:
        status = "OVERDUE"
        paid_date = None
    inv_rows.append({
        "invoice_id": doc_no("INV", i + 1),
        "vendor": random.choice(VENDORS),
        "entity": entity,
        "invoice_date": dt.strftime("%Y-%m-%d"),
        "due_date": due.strftime("%Y-%m-%d"),
        "currency": CURRENCIES[entity],
        "invoice_amount": amount,
        "tax_amount": round(amount * 0.18, 2),
        "status": status,
        "paid_date": paid_date.strftime("%Y-%m-%d") if paid_date else "",
        "po_number": f"PO-{random.randint(100000, 999999)}" if np.random.uniform() < 0.85 else "",
        "approval_status": random.choices(["APPROVED", "PENDING", "REJECTED"], weights=[88, 9, 3])[0],
    })
inv = pd.DataFrame(inv_rows)

# Realism patch: make invoice status consistent with the dates, as of period end.
# Old invoices are overwhelmingly settled; anything unpaid past its due date is OVERDUE.
# Separate RNG, so the main random streams (and the intercompany data) are unchanged.
_rng_inv = np.random.default_rng(11)
_asof = END
_due = pd.to_datetime(inv["due_date"])
_paid = pd.to_datetime(inv["paid_date"].replace("", np.nan))
_old_unpaid = (inv["status"] != "PAID") & (_due < _asof - timedelta(days=90)) & (_rng_inv.random(len(inv)) < 0.97)
_new_paid_date = _due + pd.to_timedelta(_rng_inv.normal(-2, 6, len(inv)).round(), unit="D")
inv.loc[_old_unpaid, "status"] = "PAID"
inv.loc[_old_unpaid, "paid_date"] = _new_paid_date[_old_unpaid].dt.strftime("%Y-%m-%d")
_late_paid = (inv["status"] == "PAID") & (pd.to_datetime(inv["paid_date"].replace("", np.nan)) > _asof)
inv.loc[_late_paid, "status"] = "OPEN"
inv.loc[_late_paid, "paid_date"] = ""
_unpaid = inv["status"] != "PAID"
inv.loc[_unpaid, "status"] = np.where(_due[_unpaid] < _asof, "OVERDUE", "OPEN")
inv.to_csv(f"{OUT}/vendor_invoices.csv", index=False)
print(f"  Invoices: {len(inv):,} rows")

# ---------------- 4. Intercompany Transactions ----------------
print("Generating intercompany transactions...")
ic_rows = []
for i in range(4000):
    from_e, to_e = random.sample(ENTITIES, 2)
    dt = rand_date()
    amount = round(abs(np.random.lognormal(11, 1.2)), 2)
    mismatch = np.random.uniform() < 0.07
    ic_rows.append({
        "ic_id": doc_no("IC", i + 1),
        "transaction_date": dt.strftime("%Y-%m-%d"),
        "from_entity": from_e,
        "to_entity": to_e,
        "amount_sender": amount,
        "amount_receiver": round(amount + np.random.normal(0, 500), 2) if mismatch else amount,
        "currency": "USD",
        "nature": random.choice(["Cost Allocation", "Service Fee", "Loan", "Royalty", "Shared Services"]),
        "settlement_status": random.choices(["SETTLED", "PENDING"], weights=[80, 20])[0],
    })
ic = pd.DataFrame(ic_rows)
ic.to_csv(f"{OUT}/intercompany_transactions.csv", index=False)
print(f"  Intercompany: {len(ic):,} rows")

print("\nAll datasets generated successfully!")
print(f"Total records: {len(gl) + len(bank) + len(inv) + len(ic):,}")
