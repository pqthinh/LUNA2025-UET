from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..deps import get_current_user, require_admin
from ..evaluate import evaluate_predictions
import os, shutil

router = APIRouter(prefix="/submissions", tags=["submissions"])

SUB_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "submissions")
os.makedirs(SUB_DIR, exist_ok=True)

@router.get("/")
def list_submissions(
    page: int = 1, page_size: int = 50,
    dataset_id: int | None = None,
    db: Session = Depends(get_db), user = Depends(get_current_user)
):
    q = db.query(models.Submission).order_by(models.Submission.created_at.desc())
    if user.role != "admin":
        q = q.filter(models.Submission.user_id == user.id)
    if dataset_id:
        q = q.filter(models.Submission.dataset_id == dataset_id)
    total = q.count()
    items = q.offset((page-1)*page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@router.post("/")
async def upload_submission(
    dataset_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    ds = db.query(models.Dataset).get(dataset_id)
    if not ds: raise HTTPException(status_code=404, detail="Dataset not found")
    path = os.path.join(SUB_DIR, file.filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    sub = models.Submission(user_id=user.id, dataset_id=dataset_id, file_path=path)
    db.add(sub); db.commit(); db.refresh(sub)
    return sub

@router.get("/{sub_id}")
def get_submission(sub_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    sub = db.query(models.Submission).get(sub_id)
    if not sub: raise HTTPException(status_code=404, detail="Submission not found")
    if user.role != "admin" and user.id != sub.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return sub

@router.post("/{sub_id}/evaluate", dependencies=[Depends(require_admin)])
def evaluate_submission(sub_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    sub = db.query(models.Submission).get(sub_id)
    if not sub: raise HTTPException(status_code=404, detail="Submission not found")
    ds = db.query(models.Dataset).get(sub.dataset_id)
    if not ds or not ds.groundtruth_path:
        raise HTTPException(status_code=400, detail="Dataset ground truth missing")
    if not os.path.exists(sub.file_path):
        raise HTTPException(status_code=404, detail="Submission file missing")

    result = evaluate_predictions(ds.groundtruth_path, sub.file_path)
    sub.score_json = result
    sub.evaluated = True
    db.commit()
    db.refresh(sub)
    return sub
