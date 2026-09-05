import pytest
import pandas as pd
from src.evaluation.ring_holdout_eval import split_data_ring_holdout

def create_mock_data():
    X = pd.DataFrame({
        "account_id": [f"A{i}" for i in range(100)],
        "feature1": range(100)
    })
    
    types = ["abuse_ring"] * 60 + ["normal"] * 20 + ["legitimate_shared"] * 20
    
    # Give rings 1-20 (3 accounts each)
    ring_ids = []
    for i in range(20):
        ring_ids.extend([f"R{i}"] * 3)
    ring_ids.extend([None] * 40)
    
    df_gt = pd.DataFrame({
        "account_id": [f"A{i}" for i in range(100)],
        "account_type": types,
        "ring_id": ring_ids
    })
    y = (df_gt["account_type"] == "abuse_ring").astype(int)
    return X, y, df_gt

def test_no_ring_overlap_between_train_and_test():
    X, y, df_gt = create_mock_data()
    splits = split_data_ring_holdout(X, y, df_gt, random_state=42)
    
    train_accs = splits["X_train"]["account_id"].tolist()
    test_accs = splits["X_test"]["account_id"].tolist()
    
    train_rings = df_gt[df_gt["account_id"].isin(train_accs)]["ring_id"].dropna().unique()
    test_rings = df_gt[df_gt["account_id"].isin(test_accs)]["ring_id"].dropna().unique()
    
    overlap = set(train_rings).intersection(set(test_rings))
    assert len(overlap) == 0, f"Rings overlap between train and test: {overlap}"

def test_deterministic_split():
    X, y, df_gt = create_mock_data()
    splits1 = split_data_ring_holdout(X, y, df_gt, random_state=42)
    splits2 = split_data_ring_holdout(X, y, df_gt, random_state=42)
    
    assert splits1["X_train"]["account_id"].tolist() == splits2["X_train"]["account_id"].tolist()
    assert splits1["X_test"]["account_id"].tolist() == splits2["X_test"]["account_id"].tolist()

def test_no_label_leakage():
    X, y, df_gt = create_mock_data()
    splits = split_data_ring_holdout(X, y, df_gt, random_state=42)
    
    for df in [splits["X_train"], splits["X_val"], splits["X_test"]]:
        assert "account_type" not in df.columns
        assert "ring_id" not in df.columns
        assert "target" not in df.columns

def test_valid_predictions_and_metrics():
    X, y, df_gt = create_mock_data()
    splits = split_data_ring_holdout(X, y, df_gt, random_state=42)
    
    assert len(splits["X_train"]) == len(splits["y_train"])
    assert len(splits["X_test"]) == len(splits["y_test"])
    
    assert set(splits["y_train"].unique()).issubset({0, 1})
    assert set(splits["y_test"].unique()).issubset({0, 1})

