from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..deps import get_current_user

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

def _get_metric_from_score(score_json, key):
    if not score_json:
        return None
    # try several casings
    for k in (key, key.upper(), key.lower(), key.capitalize()):
        v = score_json.get(k)
        if v is not None:
            try:
                return float(v)
            except Exception:
                return None
    return None

@router.get("/")
def leaderboard(dataset_id: int | None = None, metric: str = "AUC", db: Session = Depends(get_db), user = Depends(get_current_user)):
    """
    Return submission-level leaderboard filtered by dataset_id (if provided)
    and sorted by the chosen metric (descending). Only submissions that have
    a non-null value for the chosen metric in score_json are returned.
    Allowed metrics: AUC, F1, ACC, PRECISION (case-insensitive).
    """
    allowed = {"auc": "AUC", "f1": "F1", "acc": "ACC", "precision": "PRECISION"}
    metric_key = allowed.get(metric.lower(), "AUC")

    # use outerjoin so submissions without a linked user are still returned
    # select username too so frontend can show uploader username instead of id
    q = db.query(models.Submission, models.User.username, models.User.group_name) \
          .outerjoin(models.User, models.User.id == models.Submission.user_id)
    if dataset_id:
        q = q.filter(models.Submission.dataset_id == dataset_id)
    rows = q.all()

    out = []
    # rows contain tuples: (Submission, username, group_name)
    for sub, username, group in rows:
        # score_json might be stored as dict/JSON; guard missing
        if not sub.score_json:
            continue
        # find chosen metric in possible casings
        val = _get_metric_from_score(sub.score_json, metric_key)
        if val is None:
            continue
        # common metrics
        auc_v = _get_metric_from_score(sub.score_json, "AUC")
        f1_v = _get_metric_from_score(sub.score_json, "F1")
        prec_v = _get_metric_from_score(sub.score_json, "PRECISION")
        acc_v = _get_metric_from_score(sub.score_json, "ACC")

        out.append({
            "submission_id": sub.id,
            "group_name": group or f"user-{sub.user_id}",
            "uploader_id": sub.user_id,               # uploader id (fallback)
            "uploader_username": username,            # uploader username for frontend
            "dataset_id": sub.dataset_id,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "metric": val,
            "metric_name": metric_key,
            "auc": auc_v,
            "f1": f1_v,
            "precision": prec_v,
            "acc": acc_v,
        })

    # sort by chosen metric desc, tiebreaker by created_at desc (None -> oldest)
    out.sort(key=lambda x: (-(x["metric"] if x["metric"] is not None else -1e9),
                            x["created_at"] or ""), )
    return out

@router.get("/history")
def history(group_name: str, dataset_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    q = db.query(models.Submission, models.User.group_name)        .join(models.User, models.User.id == models.Submission.user_id)        .filter(models.User.group_name == group_name, models.Submission.dataset_id == dataset_id)        .order_by(models.Submission.created_at.asc())
    rows = q.all()
    out = []
    for sub, _ in rows:
        auc = _get_metric_from_score(sub.score_json, "AUC") if sub.score_json else None
        out.append({
            "submission_id": sub.id,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "auc": auc
        })
    return out
