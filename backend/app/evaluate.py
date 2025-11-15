import logging
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    f1_score,
    accuracy_score,
    recall_score,
    precision_score,
    roc_curve,
    precision_recall_curve,
)
import csv
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)

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


def _coerce_binary_labels(label_series: pd.Series, score_series: pd.Series) -> pd.Series:
    try:
        return label_series.astype(int)
    except Exception:
        unique_labels = label_series.dropna().unique().tolist()
        if not unique_labels:
            raise ValueError("Ground truth label column is empty")
        if len(unique_labels) == 1:
            return pd.Series(0, index=label_series.index)
        if len(unique_labels) > 2:
            raise ValueError("ROC AUC requires binary ground truth labels")

        scoring = (
            pd.DataFrame({"label": label_series, "score": score_series})
            .dropna(subset=["label", "score"])
        )
        if scoring.empty:
            raise ValueError("Score column contains no numeric data for label mapping")
        label_scores = scoring.groupby("label")["score"].mean()
        label_scores = label_scores.reindex(unique_labels, fill_value=float("-inf"))
        positive_label = label_scores.idxmax()

        label_map = {positive_label: 1}
        for label in unique_labels:
            if label != positive_label:
                label_map[label] = 0
        mapped = label_series.map(label_map)
        return mapped.fillna(0).astype(int)


def evaluate_predictions(ground_truth_path, predict_path):
    df_true = pd.read_csv(ground_truth_path)
    df_pred = pd.read_csv(predict_path)
    if "id" not in df_true.columns or "label" not in df_true.columns:
        raise ValueError("Ground truth CSV must have columns: id,label")
    if "id" not in df_pred.columns:
        raise ValueError("Prediction CSV must contain an id column")

    if "label_pred" in df_pred.columns:
        score_column = "label_pred"
    else:
        preferred = ["probability", "score", "prediction", "label_score"]
        score_column = next((col for col in df_pred.columns if col.lower() in preferred), None)
        if score_column is None and "label" in df_pred.columns:
            score_column = "label"
        if score_column is None:
            raise ValueError("Prediction CSV must have a probability column (label_pred/probability/score)")

    merged = pd.merge(df_true[["id","label"]], df_pred[["id", score_column]], on="id", how="inner")
    if merged.empty:
        raise ValueError("No matching ids between ground truth and predictions")

    score_series = merged[score_column]
    y_score = pd.to_numeric(score_series, errors="raise")
    y_true = _coerce_binary_labels(merged["label"], y_score)
    try:
        auc = float(roc_auc_score(y_true, y_score))
    except Exception as exc:
        auc = None
        logger.warning("evaluate_predictions: failed to compute ROC AUC (%s)", exc)
    y_hat = (y_score >= 0.5).astype(int)
    f1 = float(f1_score(y_true, y_hat, zero_division=0))
    acc = float(accuracy_score(y_true, y_hat))
    rec = float(recall_score(y_true, y_hat, zero_division=0))
    prec_value = float(precision_score(y_true, y_hat, zero_division=0))

    fpr = tpr = prec_curve = rec_curve = []
    try:
        fpr, tpr, _ = roc_curve(y_true, y_score)
    except Exception:
        fpr, tpr = [], []
    try:
        prec_curve, rec_curve, _ = precision_recall_curve(y_true, y_score)
    except Exception:
        prec_curve, rec_curve = [], []

    metrics = {
        "auc": auc,
        "precision": prec_value,
        "recall": rec,
        "f1": f1,
        "acc": acc,
    }

    result = {
        **metrics,
        "n_samples": int(len(merged)),
    }
    if len(fpr) and len(tpr):
        result["ROC"] = {"fpr": fpr.tolist(), "tpr": tpr.tolist()}
    if len(prec_curve) and len(rec_curve):
        result["PR"] = {"precision": prec_curve.tolist(), "recall": rec_curve.tolist()}
    if auc is not None and auc <= 0:
        logger.warning("evaluate_predictions: computed ROC AUC <= 0 (value=%s)", auc)

    return result


def _read_label_map(path: str) -> Dict[str, str]:
    def _looks_like_header(row: list[str]) -> bool:
        if not row:
            return False
        first = row[0].strip().lower()
        if first != "id":
            return False
        if len(row) == 1:
            return True
        second = row[1].strip().lower()
        return second in {
            "label",
            "label_pred",
            "label_score",
            "probability",
            "score",
            "prediction",
        }

    m = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header_skipped = False
        for row in reader:
            if not row:
                continue
            if len(row) < 2:
                continue
            if not header_skipped:
                header_skipped = True
                if _looks_like_header(row):
                    continue
            _id = row[0].strip()
            _label = row[1].strip()
            if not _id:
                continue
            m[_id] = _label
    return m

def compute_classification_metrics(gt_path: str, pred_path: str) -> Dict[str, float]:
    """
    Compute basic classification metrics between two CSVs (id,label).
    Returns micro-averaged acc, precision, recall and f1.
    For single-label per-id classification micro precision/recall == acc,
    we still expose all keys for frontend display.
    """
    if not os.path.exists(gt_path):
        raise FileNotFoundError(f"Groundtruth not found: {gt_path}")
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"Submission file not found: {pred_path}")

    gt = _read_label_map(gt_path)
    pred = _read_label_map(pred_path)
    if not gt:
        return {"acc": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

    y_true = []
    y_pred = []
    for k, v in gt.items():
        if k not in pred:
            continue
        y_true.append(v)
        y_pred.append(pred[k])

    if not y_true:
        return {"acc": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

    # try to coerce to numeric labels if possible for binary problems
    def _coerce(val):
        try:
            return int(val)
        except Exception:
            try:
                return float(val)
            except Exception:
                return val

    y_true_num = [_coerce(v) for v in y_true]
    y_pred_num = [_coerce(v) for v in y_pred]
    score_candidates = []
    for raw in y_pred:
        try:
            score_candidates.append(float(raw))
        except Exception:
            score_candidates = []
            break
    if not score_candidates:
        try:
            score_candidates = [float(v) for v in y_pred_num]
        except Exception:
            score_candidates = []

    unique_labels = sorted(set(y_true_num), key=lambda x: str(x))
    average = "binary" if len(unique_labels) == 2 else "macro"
    score_kwargs = {"zero_division": 0}
    if average == "binary":
        score_kwargs["pos_label"] = unique_labels[-1]

    acc = float(accuracy_score(y_true_num, y_pred_num))
    precision = float(precision_score(y_true_num, y_pred_num, average=average, **score_kwargs))
    recall = float(recall_score(y_true_num, y_pred_num, average=average, **score_kwargs))
    f1 = float(f1_score(y_true_num, y_pred_num, average=average, **score_kwargs))
    auc = None
    logger.warning(
        "compute_classification_metrics: unique labels=%i unique scores=%i",
        len(set(y_true_num)),
        len(set(score_candidates)),
    )
    if score_candidates and len(set(score_candidates)) > 1 and len(set(y_true_num)) > 1:
        try:
            auc = float(roc_auc_score(y_true_num, score_candidates))
            logger.warning("auc: (%s)", auc)
        except Exception as exc:
            auc = None
            logger.warning("compute_classification_metrics: failed to compute ROC AUC (%s)", exc)
    else:
        if not auc:
            logger.debug("compute_classification_metrics: skip ROC AUC (scores=%s labels=%s)", 
                         score_candidates, y_true_num)
    
    return {"acc": acc, "precision": precision, "recall": recall, "f1": f1, "auc": auc}
