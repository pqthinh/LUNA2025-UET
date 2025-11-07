from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..deps import get_current_user, require_admin
from ..evaluate import analyze_groundtruth
import os, shutil
from typing import Optional

router = APIRouter(prefix="/datasets", tags=["datasets"])

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "datasets")
os.makedirs(DATA_DIR, exist_ok=True)

@router.get("/")
def list_datasets(page: int = 1, page_size: int = 50, db: Session = Depends(get_db)):
    q = db.query(models.Dataset).order_by(models.Dataset.created_at.desc())
    total = q.count()
    items = q.offset((page-1)*page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@router.post("/", dependencies=[Depends(require_admin)])
async def upload_dataset(
    name: str = Form(...),
    description: str = Form(""),
    data_file: Optional[UploadFile] = File(None),
    groundtruth_csv: UploadFile = File(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    data_path = None
    if data_file is not None:
        data_path = os.path.join(DATA_DIR, data_file.filename)
        with open(data_path, "wb") as f:
            shutil.copyfileobj(data_file.file, f)
    gt_path = os.path.join(DATA_DIR, groundtruth_csv.filename)
    with open(gt_path, "wb") as f:
        shutil.copyfileobj(groundtruth_csv.file, f)

    ds = models.Dataset(
        name=name, description=description,
        data_file_path=data_path, groundtruth_path=gt_path,
        uploader_id=user.id
    )
    db.add(ds); db.commit(); db.refresh(ds)
    return ds

@router.post("/{id}/mark_official", dependencies=[Depends(require_admin)])
def mark_official(id: int, db: Session = Depends(get_db)):
    ds = db.query(models.Dataset).get(id)
    if not ds: raise HTTPException(status_code=404, detail="Dataset not found")
    db.query(models.Dataset).update({models.Dataset.is_official: False})
    ds.is_official = True
    db.commit()
    return {"ok": True, "official_dataset_id": ds.id}

@router.get("/{id}")
def get_dataset(id: int, db: Session = Depends(get_db)):
    ds = db.query(models.Dataset).get(id)
    if not ds: raise HTTPException(status_code=404, detail="Dataset not found")
    return ds

@router.get("/{id}/groundtruth")
def download_groundtruth(id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    ds = db.query(models.Dataset).get(id)
    if not ds: raise HTTPException(status_code=404, detail="Dataset not found")
    if not ds.groundtruth_path or not os.path.exists(ds.groundtruth_path):
        raise HTTPException(status_code=404, detail="Ground truth not found")
    fn = os.path.basename(ds.groundtruth_path)
    return FileResponse(ds.groundtruth_path, media_type="text/csv", filename=fn)

@router.post("/{id}/analyze", dependencies=[Depends(require_admin)])
def analyze_dataset(id: int, db: Session = Depends(get_db)):
    ds = db.query(models.Dataset).get(id)
    if not ds: raise HTTPException(status_code=404, detail="Dataset not found")
    if not ds.groundtruth_path or not os.path.exists(ds.groundtruth_path):
        raise HTTPException(status_code=404, detail="Ground truth not found")
    stats = analyze_groundtruth(ds.groundtruth_path)
    ds.stats_json = stats
    db.commit()
    db.refresh(ds)
    return ds
