"""
ClearLedger AI — ML Anomaly Detection on GL Entries
Isolation Forest to flag unusual journal entries for audit review:
weekend postings, manual JEs with round amounts, outlier values,
unusual user activity patterns.
Author: Syed Naashit Hashmi
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

DATA = "/home/claude/finrecon/data"
OUT = "/home/claude/finrecon/outputs"

def engineer_features(gl: pd.DataFrame) -> pd.DataFrame:
    gl = gl.copy()
    gl["posting_date"] = pd.to_datetime(gl["posting_date"])
    gl["log_amount"] = np.log1p(gl["amount"])
    gl["is_weekend"] = (gl["posting_date"].dt.dayofweek >= 5).astype(int)
    gl["is_month_end"] = (gl["posting_date"].dt.day >= 28).astype(int)
    gl["is_manual"] = (gl["source_system"] == "MANUAL_JE").astype(int)
    gl["is_round_amount"] = ((gl["amount"] % 1000) == 0).astype(int)
    user_freq = gl["posted_by"].value_counts()
    gl["user_posting_freq"] = gl["posted_by"].map(user_freq)
    gl["user_rare"] = (gl["user_posting_freq"] < user_freq.quantile(0.1)).astype(int)
    return gl

def detect(gl: pd.DataFrame):
    features = ["log_amount", "is_weekend", "is_month_end",
                "is_manual", "is_round_amount", "user_rare"]
    X = StandardScaler().fit_transform(gl[features])
    model = IsolationForest(n_estimators=200, contamination=0.02, random_state=42)
    gl["anomaly_score"] = model.fit_predict(X)
    gl["anomaly_raw_score"] = model.decision_function(X)
    gl["is_anomaly"] = (gl["anomaly_score"] == -1).astype(int)
    return gl

def main():
    gl = pd.read_csv(f"{DATA}/general_ledger.csv", dtype={"gl_account": str})
    gl = engineer_features(gl)
    gl = detect(gl)

    anomalies = gl[gl["is_anomaly"] == 1].sort_values("anomaly_raw_score")
    cols = ["journal_id", "posting_date", "entity", "gl_account_name", "amount",
            "source_system", "posted_by", "is_weekend", "is_manual",
            "is_round_amount", "anomaly_raw_score"]
    anomalies[cols].to_csv(f"{OUT}/flagged_anomalies.csv", index=False)

    print(f"Total GL entries analyzed : {len(gl):,}")
    print(f"Anomalies flagged         : {len(anomalies):,} ({len(anomalies)/len(gl)*100:.1f}%)")
    print(f"\nAnomaly profile:")
    print(f"  Weekend postings   : {anomalies['is_weekend'].sum():,}")
    print(f"  Manual JEs         : {anomalies['is_manual'].sum():,}")
    print(f"  Round amounts      : {anomalies['is_round_amount'].sum():,}")
    print(f"\nTop 5 highest-risk entries:")
    print(anomalies[["journal_id", "entity", "amount", "source_system"]].head().to_string(index=False))
    print(f"\nSaved -> {OUT}/flagged_anomalies.csv")

if __name__ == "__main__":
    main()
