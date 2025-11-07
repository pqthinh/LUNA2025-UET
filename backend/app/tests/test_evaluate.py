import os, pandas as pd
from app.evaluate import evaluate_predictions, analyze_groundtruth

def test_analyze_and_evaluate(tmp_path):
    gt = tmp_path / "gt.csv"
    pd.DataFrame({"id":[1,2,3,4], "label":[0,1,1,0]}).to_csv(gt, index=False)

    pred = tmp_path / "pred.csv"
    pd.DataFrame({"id":[1,2,3,4], "label_pred":[0.1,0.8,0.7,0.2]}).to_csv(pred, index=False)

    stats = analyze_groundtruth(str(gt))
    assert stats["schema_valid"]
    assert stats["label_distribution"]["0"] == 2

    res = evaluate_predictions(str(gt), str(pred))
    assert "AUC" in res and res["AUC"] is not None
    assert 0 <= res["F1"] <= 1
