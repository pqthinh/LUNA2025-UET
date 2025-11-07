from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..deps import get_current_user

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

@router.get("/")
def leaderboard(dataset_id: int | None = None, db: Session = Depends(get_db), user = Depends(get_current_user)):
    q = db.query(models.Submission, models.User.group_name)        .join(models.User, models.User.id == models.Submission.user_id)
    if dataset_id:
        q = q.filter(models.Submission.dataset_id == dataset_id)
    rows = q.all()

    best = {}
    for sub, group in rows:
        auc = None
        if sub.score_json and "AUC" in sub.score_json and sub.score_json["AUC"] is not None:
            auc = sub.score_json["AUC"]
        else:
            continue
        key = (group, sub.dataset_id)
        cur = best.get(key)
        if (cur is None) or (auc > cur["auc"]):
            best[key] = {
                "group_name": group or f"user-{sub.user_id}",
                "dataset_id": sub.dataset_id,
                "auc": float(auc),
                "f1": float(sub.score_json.get("F1", 0.0)) if sub.score_json else 0.0,
                "submission_id": sub.id
            }
    return sorted(best.values(), key=lambda x: (-x["auc"], -x["f1"]))

@router.get("/history")
def history(group_name: str, dataset_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    q = db.query(models.Submission, models.User.group_name)        .join(models.User, models.User.id == models.Submission.user_id)        .filter(models.User.group_name == group_name, models.Submission.dataset_id == dataset_id)        .order_by(models.Submission.created_at.asc())
    rows = q.all()
    out = []
    for sub, _ in rows:
        auc = sub.score_json.get("AUC") if sub.score_json else None
        out.append({
            "submission_id": sub.id,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "auc": auc
        })
    return out
