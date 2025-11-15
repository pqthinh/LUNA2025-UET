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
    assert "auc" in res and res["auc"] is not None
    assert 0 <= res["f1"] <= 1
    assert 0 <= res["precision"] <= 1
    assert 0 <= res["recall"] <= 1
    assert 0 <= res["acc"] <= 1


def test_evaluate_predictions_with_text_labels(tmp_path):
    gt = tmp_path / "gt_text.csv"
    pd.DataFrame({"id":[1,2,3,4], "label":["cat","dog","dog","cat"]}).to_csv(gt, index=False)

    pred = tmp_path / "pred_text.csv"
    pd.DataFrame({"id":[1,2,3,4], "probability":[0.15,0.67,0.8,0.22]}).to_csv(pred, index=False)

    res = evaluate_predictions(str(gt), str(pred))
    assert "auc" in res and res["auc"] is not None
    assert 0 <= res["auc"] <= 1
