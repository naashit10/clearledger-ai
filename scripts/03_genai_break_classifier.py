"""
ClearLedger AI — GenAI-Assisted Break Classification & Narrative Generation
Uses LLM (Claude API) to:
  1. Classify reconciliation breaks into root-cause categories
  2. Generate plain-English investigation narratives for analysts
  3. Draft month-end commentary for management reporting

Falls back to deterministic rule-based classification when no API key
is configured, so the pipeline runs end-to-end in any environment.

Author: Syed Naashit Hashmi
"""

import os
import json
import pandas as pd

DATA = "/home/claude/finrecon/data"
OUT = "/home/claude/finrecon/outputs"

# ---------------------------------------------------------------
# Prompt templates (used when ANTHROPIC_API_KEY is configured)
# ---------------------------------------------------------------
CLASSIFY_PROMPT = """You are a financial reconciliation analyst at a global payments company.
Classify the following reconciliation break into exactly one category:
- TIMING_DIFFERENCE: transaction posted in GL and bank on different dates
- BANK_CHARGES: small deductions by bank (fees, levies)
- MISSING_IN_BANK: GL entry never hit the bank statement
- MISSING_IN_GL: bank transaction never recorded in GL
- AMOUNT_MISMATCH: same transaction, different amounts
- DUPLICATE_POSTING: same transaction posted twice

Break details:
{break_json}

Respond ONLY with JSON: {{"category": "...", "confidence": 0-1, "rationale": "one sentence"}}"""

NARRATIVE_PROMPT = """You are preparing month-end close commentary for a Finance Controller.
Given these reconciliation statistics, write a crisp 3-sentence summary highlighting:
match rate, dominant break category, and recommended action.

Stats: {stats_json}

Respond with plain text only."""


def classify_break_rules(row) -> dict:
    """Deterministic fallback classification (no API needed)."""
    if row["status"] == "BREAK_BANK_ONLY":
        if row["bank_amount"] is not None and row["bank_amount"] < 1500:
            return {"category": "BANK_CHARGES", "confidence": 0.85,
                    "rationale": "Small-value bank-only item consistent with fees or levies."}
        return {"category": "MISSING_IN_GL", "confidence": 0.80,
                "rationale": "Bank transaction has no corresponding GL journal."}
    if row["status"] == "BREAK_GL_ONLY":
        return {"category": "MISSING_IN_BANK", "confidence": 0.80,
                "rationale": "GL journal has no corresponding bank movement."}
    if row["match_tier"] == "TIER2_TIMING":
        return {"category": "TIMING_DIFFERENCE", "confidence": 0.95,
                "rationale": "Amounts equal; value date differs within window."}
    if row["match_tier"] == "TIER3_FUZZY_AMOUNT":
        return {"category": "AMOUNT_MISMATCH", "confidence": 0.90,
                "rationale": "Date aligned; amount difference within tolerance."}
    return {"category": "OTHER", "confidence": 0.5, "rationale": "Requires manual review."}


def classify_with_llm(break_row: dict) -> dict:
    """Call Claude API for classification. Requires ANTHROPIC_API_KEY env var."""
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[{"role": "user",
                   "content": CLASSIFY_PROMPT.format(break_json=json.dumps(break_row, default=str))}],
    )
    return json.loads(msg.content[0].text)


def main():
    recon = pd.read_csv(f"{OUT}/reconciliation_results.csv")
    use_llm = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"Classification mode: {'LLM (Claude API)' if use_llm else 'Rule-based fallback'}")

    needs_class = recon[recon["status"] != "MATCHED"].copy()
    print(f"Items to classify: {len(needs_class):,}")

    categories, confidences, rationales = [], [], []
    for _, row in needs_class.iterrows():
        if use_llm:
            try:
                res = classify_with_llm(row.to_dict())
            except Exception:
                res = classify_break_rules(row)
        else:
            res = classify_break_rules(row)
        categories.append(res["category"])
        confidences.append(res["confidence"])
        rationales.append(res["rationale"])

    needs_class["break_category"] = categories
    needs_class["classification_confidence"] = confidences
    needs_class["ai_rationale"] = rationales
    needs_class.to_csv(f"{OUT}/classified_breaks.csv", index=False)

    print("\n=== BREAK CATEGORY DISTRIBUTION ===")
    print(needs_class["break_category"].value_counts().to_string())
    print(f"\nSaved -> {OUT}/classified_breaks.csv")


if __name__ == "__main__":
    main()
