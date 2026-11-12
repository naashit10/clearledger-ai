# 💠 ClearLedger AI — Financial Reconciliation & Reporting Automation Platform

> An end-to-end **GenAI-powered financial reconciliation system** that automates GL-to-bank matching, classifies reconciliation breaks using LLMs, detects anomalous journal entries with machine learning, and auto-generates month-end close reporting.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![SQL](https://img.shields.io/badge/SQL-MySQL-orange) ![ML](https://img.shields.io/badge/ML-IsolationForest-green) ![GenAI](https://img.shields.io/badge/GenAI-Claude%20API-purple) ![PowerBI](https://img.shields.io/badge/Dashboard-Power%20BI%20%2B%20HTML-yellow)

---

## 🎯 Business Problem

Finance teams at large enterprises spend **hundreds of analyst-hours every month** manually reconciling general ledger entries against bank statements, investigating breaks, and preparing close commentary. This project automates that workflow end-to-end:

| Manual Process | ClearLedger AI |
|---|---|
| Analyst matches GL ↔ bank line by line | 3-tier matching engine (exact → timing → fuzzy) |
| Breaks investigated one by one | GenAI classifies root cause automatically |
| Suspicious entries found by sampling | Isolation Forest scans 100% of journals |
| Close commentary written manually | Auto-generated management narrative |

**Impact (simulated environment): 82.5% auto-match rate · ~120 analyst-hours avoided over 17 months (~7/month, assuming 1.5 min of manual work per match) · 100% journal population screened for anomalies**

---

## 🏗️ Architecture

```
┌─────────────┐   ┌──────────────────┐   ┌───────────────────────┐
│  Data Layer │──▶│ Reconciliation    │──▶│ GenAI Break           │
│  4 datasets │   │ Engine (3-tier)   │   │ Classification (LLM)  │
│  78,605 rows│   └──────────────────┘   └───────────────────────┘
└─────────────┘            │                        │
       │                   ▼                        ▼
       │          ┌──────────────────┐   ┌───────────────────────┐
       └─────────▶│ ML Anomaly       │──▶│ Automated Reporting    │
                  │ Detection        │   │ + Power BI Dashboard   │
                  └──────────────────┘   └───────────────────────┘
```

## 📂 Repository Structure

```
clearledger-ai/
├── data/                          # Synthetic enterprise datasets
│   ├── general_ledger.csv         # 60,000 GL journal entries
│   ├── bank_statements.csv        # 5,605 bank transactions
│   ├── vendor_invoices.csv        # 9,000 AP invoices
│   └── intercompany_transactions.csv  # 4,000 IC transactions
├── scripts/
│   ├── 01_generate_data.py        # Realistic data simulation
│   ├── 02_reconciliation_engine.py # 3-tier matching algorithm
│   ├── 03_genai_break_classifier.py # LLM-assisted classification
│   ├── 04_anomaly_detection.py    # Isolation Forest screening
│   ├── 05_reporting_automation.py # Close pack generation
│   └── 06_export_dashboard_data.py # Aggregated tables for the dashboard / BI tools
├── sql/
│   └── analytics_queries.sql      # 8 production-grade queries (CTEs, window functions)
├── dashboard/
│   ├── clearledger_dashboard.html    # Self-contained interactive dashboard (no server needed)
│   └── data/                      # Dashboard tables (CSV) for Power BI / Tableau import
├── outputs/                       # Generated reports & results
└── docs/
    └── powerbi_guide.md           # Power BI data model + DAX measures
```

---

## ⚙️ Key Components

### 1. Three-Tier Reconciliation Engine (`02_reconciliation_engine.py`)
- **Tier 1 — Exact:** journal reference + amount + value date
- **Tier 2 — Timing:** equal amounts within a ±5-day window
- **Tier 3 — Fuzzy:** amount within configurable tolerance (bank charges, partial settlements)
- Bidirectional break detection: GL-only items AND bank-only items

### 2. GenAI Break Classification (`03_genai_break_classifier.py`)
- Claude API integration with structured-JSON prompting
- Classifies breaks: `TIMING_DIFFERENCE` · `BANK_CHARGES` · `MISSING_IN_GL` · `MISSING_IN_BANK` · `AMOUNT_MISMATCH` · `DUPLICATE_POSTING`
- Generates one-line investigation rationale per break for analyst handoff
- Note: the bundled results in `outputs/` were produced by the rule-based fallback; set `ANTHROPIC_API_KEY` to use the LLM path
- **Graceful degradation:** deterministic rule-based fallback runs without an API key

### 3. ML Anomaly Surveillance (`04_anomaly_detection.py`)
- Isolation Forest over engineered features: weekend postings, manual JEs, round amounts, rare-user activity, log-scaled amounts
- Flags 2% highest-risk journal population for audit review — replaces random sampling

### 4. SQL Analytics Library (`sql/analytics_queries.sql`)
- Match-rate trend with `LAG()` month-over-month deltas
- Top-N breaks per entity via `ROW_NUMBER()`
- AP aging with running exposure (`SUM() OVER`)
- Vendor payment percentile ranking (`PERCENT_RANK()`)
- Duplicate payment detection, weekend manual-JE audit query

### 5. Automated Close Reporting (`05_reporting_automation.py`)
- One-command close pack: KPIs JSON, AP aging, entity scorecards
- Auto-drafted management commentary (LLM-ready template)

---

## 📊 Dashboard

**Interactive HTML version** (`dashboard/clearledger_dashboard.html`) — a single self-contained file: open it in any browser, or publish it with GitHub Pages. Select an entity in the scorecard to focus the charts; hover any chart for detail. Money values are USD equivalents at fixed indicative rates.

**Power BI version** — import the tables in `dashboard/data/` (Get Data → Text/CSV) and see [`docs/powerbi_guide.md`](docs/powerbi_guide.md) for the data model, DAX measures, and page layout.

Headline metrics surfaced:
- Auto-match rate trend (17 months)
- Break root-cause distribution (GenAI-classified)
- Entity-level reconciliation scorecard
- AP aging exposure with overdue alerting

---

## 🚀 Quick Start

```bash
# Clone and install
git clone https://github.com/<your-username>/clearledger-ai.git
cd clearledger-ai
pip install pandas numpy scikit-learn

# Run the full pipeline
python scripts/01_generate_data.py        # builds 78,605-record dataset
python scripts/02_reconciliation_engine.py
python scripts/03_genai_break_classifier.py
python scripts/04_anomaly_detection.py
python scripts/05_reporting_automation.py
python scripts/06_export_dashboard_data.py   # refreshes dashboard/data/*.csv

# Optional: enable live LLM classification
export ANTHROPIC_API_KEY=sk-...
python scripts/03_genai_break_classifier.py
```

---

## 🧰 Tech Stack

| Layer | Tools |
|---|---|
| Data processing | Python (pandas, NumPy) |
| Matching engine | Custom 3-tier algorithm |
| GenAI | Claude API (structured JSON prompting, fallback design) |
| Machine learning | scikit-learn Isolation Forest |
| Analytics | MySQL-dialect SQL (CTEs, window functions) |
| Visualization | Power BI (star schema + DAX) · Chart.js HTML dashboard |

---

## 📈 Results Summary

| Metric | Value |
|---|---|
| Records processed | 78,605 |
| Auto-match rate | 82.5% |
| Unmatched breaks | 1,019 (800 bank-only, 219 GL-only) |
| Exceptions classified | 1,516 (1,019 unmatched + 497 matched-with-note) |
| Journals screened by ML | 60,000 (100% population) |
| Anomalies flagged for audit | 1,199 |
| Estimated analyst-hours avoided | ~120 over 17 months (~7/month; assumes 1.5 min per matched item) |

---

## 👤 Author

**Syed Naashit Hashmi**
B.Tech CS (AI & ML) · Published GenAI researcher (ITAI 2025)
[LinkedIn](https://linkedin.com/in/naashithashmi10) · naashith63@gmail.com

> *Note: All data in this repository is synthetically generated to simulate enterprise financial systems. No real financial data is used.*
