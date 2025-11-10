import pandas as pd
from sklearn.metrics import roc_auc_score, f1_score, accuracy_score, recall_score, roc_curve, precision_recall_curve
import csv
import os
from typing import Dict, Any

def analyze_groundtruth(ground_truth_path):
    df = pd.read_csv(ground_truth_path)
    stats = {}
    cols = df.columns.tolist()
    stats['columns'] = cols
    missing_id = 'id' not in cols
    missing_label = 'label' not in cols
    stats['schema_valid'] = not (missing_id or missing_label)
    if not stats['schema_valid']:
        stats['errors'] = []
        if missing_id: stats['errors'].append("Missing 'id' column")
        if missing_label: stats['errors'].append("Missing 'label' column")
        return stats
    stats['total_rows'] = int(len(df))
    stats['null_id'] = int(df['id'].isna().sum())
    stats['null_label'] = int(df['label'].isna().sum())
    stats['duplicate_id'] = int(df['id'].duplicated().sum())
    try:
        dist = df['label'].value_counts(dropna=False).to_dict()
        stats['label_distribution'] = {str(k): int(v) for k,v in dist.items()}
    except Exception:
        stats['label_distribution'] = {}
    return stats

def evaluate_predictions(ground_truth_path, predict_path):
    df_true = pd.read_csv(ground_truth_path)
    df_pred = pd.read_csv(predict_path)
    if "id" not in df_true.columns or "label" not in df_true.columns:
        raise ValueError("Ground truth CSV must have columns: id,label")
    if "id" not in df_pred.columns or "label_pred" not in df_pred.columns:
        raise ValueError("Prediction CSV must have columns: id,label_pred")

    merged = pd.merge(df_true[["id","label"]], df_pred[["id","label_pred"]], on="id", how="inner")
    if merged.empty:
        raise ValueError("No matching ids between ground truth and predictions")

    y_true = merged["label"].astype(int)
    y_score = merged["label_pred"].astype(float)
    try:
        auc = float(roc_auc_score(y_true, y_score))
    except Exception:
        auc = None
    y_hat = (y_score >= 0.5).astype(int)
    f1 = float(f1_score(y_true, y_hat))
    acc = float(accuracy_score(y_true, y_hat))
    rec = float(recall_score(y_true, y_hat))

    fpr, tpr, _ = roc_curve(y_true, y_score)
    prec, rec_curve, _ = precision_recall_curve(y_true, y_score)

    return {
        "AUC": auc,
        "F1": f1,
        "Accuracy": acc,
        "Recall": rec,
        "ROC": {"fpr": fpr.tolist(), "tpr": tpr.tolist()},
        "PR": {"precision": prec.tolist(), "recall": rec_curve.tolist()},
        "n_samples": int(len(merged))
    }

def _read_label_map(path: str) -> Dict[str, str]:
    m = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            if len(row) >= 2:
                _id = row[0].strip()
                _label = row[1].strip()
                m[_id] = _label
    return m

def compute_classification_metrics(gt_path: str, pred_path: str) -> Dict[str, float]:
    """
    Compute basic classification metrics between two CSVs (id,label).
    Returns micro-averaged accuracy, precision, recall and f1.
    For single-label per-id classification micro precision/recall == accuracy,
    we still expose all keys for frontend display.
    """
    if not os.path.exists(gt_path):
        raise FileNotFoundError(f"Groundtruth not found: {gt_path}")
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"Submission file not found: {pred_path}")

    gt = _read_label_map(gt_path)
    pred = _read_label_map(pred_path)
    if not gt:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

    total = 0
    correct = 0
    for k, v in gt.items():
        total += 1
        if k in pred and pred[k] == v:
            correct += 1

    accuracy = correct / total if total else 0.0
    # For single-label micro averaged metrics these reduce to accuracy.
    precision = accuracy
    recall = accuracy
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}

# Optionally keep backward-compat compute_accuracy_from_csvs
def compute_accuracy_from_csvs(gt_path: str, sub_path: str) -> float:
    return compute_classification_metrics(gt_path, sub_path)["accuracy"]
