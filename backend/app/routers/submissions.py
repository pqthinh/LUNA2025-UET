from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import os
import json
from app import models, schemas, database, evaluate
from app.deps import get_db, get_current_user

router = APIRouter(prefix="/submissions", tags=["submissions"])

def model_to_dict(obj):
    d = {}
    for k, v in obj.__dict__.items():
        if k == "_sa_instance_state":
            continue
        d[k] = v
    return d

@router.get("/", status_code=200)
def list_submissions(
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # join datasets to expose dataset.name (left outer join)
    q = (
        db.query(models.Submission, models.Dataset.name.label("dataset_name"))
        .outerjoin(models.Dataset, models.Dataset.id == models.Submission.dataset_id)
        .order_by(models.Submission.id.desc())
    )
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for row in rows:
        # row is tuple (Submission, dataset_name) because we selected two columns
        sub = row[0]
        dataset_name = row[1] if len(row) > 1 else None

        d = {}
        for k, v in sub.__dict__.items():
            if k == "_sa_instance_state":
                continue
            # convert datetimes to isoformat for frontend
            if hasattr(v, "isoformat"):
                try:
                    d[k] = v.isoformat()
                except Exception:
                    d[k] = v
            else:
                d[k] = v

        # attach friendly dataset name
        if dataset_name:
            d["dataset_name"] = dataset_name
        else:
            # fallback: if dataset_id present, show id as string
            if d.get("dataset_id") is not None:
                d["dataset_name"] = f"Dataset {d.get('dataset_id')}"

        # try to surface common metric fields (existing logic)
        metrics = None
        if "metrics" in d and isinstance(d["metrics"], str):
            try:
                metrics = json.loads(d["metrics"])
            except Exception:
                metrics = None
        elif "metrics" in d and isinstance(d["metrics"], dict):
            metrics = d["metrics"]

        for k in ("f1", "precision", "recall", "accuracy", "score"):
            if k in d:
                try:
                    d[k] = float(d[k]) if d[k] is not None else None
                except Exception:
                    pass

        if metrics and isinstance(metrics, dict):
            for mk in ("f1", "precision", "recall", "accuracy"):
                if mk in metrics and mk not in d:
                    try:
                        d[mk] = float(metrics[mk])
                    except Exception:
                        d[mk] = metrics[mk]
            d["metrics"] = metrics

        # If no metrics present, try to compute them on-the-fly (best-effort)
        if not any(k in d for k in ("f1", "precision", "recall", "accuracy", "metrics")):
            try:
                # locate dataset groundtruth file path (common names)
                ds = None
                if d.get("dataset_id") is not None:
                    ds = db.query(models.Dataset).filter(models.Dataset.id == int(d["dataset_id"])).first()
                gt_path_attr = None
                if ds:
                    gt_path_attr = getattr(ds, "groundtruth_path", None) or getattr(ds, "groundtruth_csv", None) or getattr(ds, "groundtruth", None)

                # locate submission file path
                sub_file_path = None
                # prefer file_path/path/storage_path
                for fld in ("file_path", "path", "storage_path"):
                    if fld in d and d[fld]:
                        sub_file_path = d[fld]
                        break
                # fallback to filename stored: join uploads dir
                if not sub_file_path and ("filename" in d and d["filename"]):
                    sub_file_path = os.path.join(os.getcwd(), "app", "uploads", "submissions", d["filename"])
                # last resort: try to see if sub has attribute file_name
                if not sub_file_path and hasattr(sub, "file_name") and getattr(sub, "file_name"):
                    sub_file_path = os.path.join(os.getcwd(), "app", "uploads", "submissions", getattr(sub, "file_name"))

                # only compute if both paths are local files
                if gt_path_attr and isinstance(gt_path_attr, str) and sub_file_path and os.path.exists(gt_path_attr) and os.path.exists(sub_file_path):
                    computed = evaluate.compute_classification_metrics(gt_path_attr, sub_file_path)
                    if computed and isinstance(computed, dict):
                        # attach computed metrics
                        d.setdefault("metrics", computed)
                        for mk in ("accuracy", "f1", "precision", "recall"):
                            if mk in computed:
                                try:
                                    d[mk] = float(computed[mk])
                                except Exception:
                                    d[mk] = computed[mk]
                        # alias score -> accuracy if not present
                        if "score" not in d and "accuracy" in d:
                            d["score"] = float(d["accuracy"])
            except Exception:
                # swallow errors — listing must not fail due to evaluation issues
                pass

        # expose created_at / uploaded_at if present (string iso or original)
        if "created_at" in d:
            d["uploaded_at"] = d["created_at"]
        elif "uploaded_at" in d:
            d["uploaded_at"] = d["uploaded_at"]
        elif "created" in d:
            d["uploaded_at"] = d["created"]

        items.append(d)

    return {"items": items, "total": total}

@router.post("/", status_code=201)
async def create_submission(
    file: UploadFile = File(...),
    dataset_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # save uploaded file
    uploads_dir = os.path.join(os.getcwd(), "app", "uploads", "submissions")
    os.makedirs(uploads_dir, exist_ok=True)
    filename = f"{current_user.id}_{file.filename}"
    path = os.path.join(uploads_dir, filename)
    with open(path, "wb") as fh:
        fh.write(await file.read())

    # create DB record robustly (don't pass unknown kwargs to SQLAlchemy constructor)
    sub = models.Submission()  # create empty instance then set attributes
    # discover model columns to avoid invalid keyword args
    try:
        cols = set(models.Submission.__table__.columns.keys())
    except Exception:
        cols = set()

    if "uploader_id" in cols:
        setattr(sub, "uploader_id", current_user.id)
    else:
        # fallback attribute name if different
        try:
            setattr(sub, "uploader", current_user.id)
        except Exception:
            pass

    # store file info in whichever column exists
    if "file_path" in cols:
        sub.file_path = path
    elif "path" in cols:
        sub.path = path
    elif "storage_path" in cols:
        sub.storage_path = path
    elif "file_name" in cols:
        sub.file_name = filename
    elif "filename" in cols:
        sub.filename = filename
    else:
        # last resort: attach as filename attribute (SQLAlchemy will ignore unknown attrs on commit)
        setattr(sub, "filename", filename)

    # dataset relation if present
    if dataset_id is not None and "dataset_id" in cols:
        try:
            sub.dataset_id = int(dataset_id)
        except Exception:
            sub.dataset_id = dataset_id

    db.add(sub)
    db.commit()
    db.refresh(sub)

    # if dataset provided try to evaluate immediately (compute metrics)
    if dataset_id:
        ds = db.query(models.Dataset).filter(models.Dataset.id == int(dataset_id)).first()
        gt_path_attr = getattr(ds, "groundtruth_path", None) or getattr(ds, "groundtruth_csv", None)
        if ds and gt_path_attr:
            # if groundtruth is a local path compute metrics; skip remote URIs
            if isinstance(gt_path_attr, str) and not gt_path_attr.startswith("minio://"):
                try:
                    metrics = evaluate.compute_classification_metrics(gt_path_attr, path)
                    # store metrics JSON if column exists
                    try:
                        cols = set(models.Submission.__table__.columns.keys())
                    except Exception:
                        cols = set()
                    if "metrics" in cols:
                        setattr(sub, "metrics", json.dumps(metrics))
                    # also try to persist common scalar columns if available
                    for key in ("accuracy", "f1", "precision", "recall", "score"):
                        if key in cols:
                            try:
                                setattr(sub, key, float(metrics.get(key, 0.0)))
                            except Exception:
                                pass
                    # keep 'score' as alias for accuracy if not present in metrics
                    if "score" in cols and not getattr(sub, "score", None):
                        try:
                            sub.score = float(metrics.get("accuracy", 0.0))
                        except Exception:
                            pass

                    db.add(sub)
                    db.commit()
                    db.refresh(sub)
                except Exception as ex:
                    print("evaluation error:", ex)

    # return best-effort summary (unchanged)
    out = {"id": getattr(sub, "id", None)}
    for key in ("filename", "file_name", "file_path", "path", "storage_path", "dataset_id", "score", "uploader_id"):
        if hasattr(sub, key):
            out[key] = getattr(sub, key)
    # attach metrics if we stored them
    if hasattr(sub, "metrics"):
        out["metrics"] = getattr(sub, "metrics")
    for k in ("accuracy", "f1", "precision", "recall"):
        if hasattr(sub, k):
            out[k] = getattr(sub, k)
    return out


@router.delete("/{submission_id}", status_code=204)
def delete_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    # allow admin or owner
    if current_user.role != "admin" and sub.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this submission")
    # remove file if exists
    try:
        path = os.path.join(os.getcwd(), "app", "uploads", "submissions", sub.filename)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
    db.delete(sub)
    db.commit()
    return {}

# helper to compute & persist metrics for one Submission instance
def _compute_and_persist_metrics(sub: "models.Submission", db: Session):
    try:
        # resolve dataset and its groundtruth attr
        ds = None
        if getattr(sub, "dataset_id", None) is not None:
            ds = db.query(models.Dataset).filter(models.Dataset.id == int(sub.dataset_id)).first()
        gt_path_attr = None
        if ds:
            gt_path_attr = getattr(ds, "groundtruth_path", None) or getattr(ds, "groundtruth_csv", None) or getattr(ds, "groundtruth", None)

        # locate submission file on disk
        sub_file_path = None
        for fld in ("file_path", "path", "storage_path", "file_name", "file_name"):
            if hasattr(sub, fld) and getattr(sub, fld):
                val = getattr(sub, fld)
                # if file_name only, construct full path
                if fld in ("file_name",) and not os.path.isabs(val):
                    sub_file_path = os.path.join(os.getcwd(), "app", "uploads", "submissions", val)
                else:
                    sub_file_path = val
                break
        # fallback to filename field
        if not sub_file_path and hasattr(sub, "filename") and getattr(sub, "filename"):
            sub_file_path = os.path.join(os.getcwd(), "app", "uploads", "submissions", getattr(sub, "filename"))

        if not gt_path_attr or not sub_file_path:
            return False, "missing paths"

        # only compute for local files (skip minio:// URIs)
        if not isinstance(gt_path_attr, str) or not os.path.exists(gt_path_attr) or not os.path.exists(sub_file_path):
            return False, "groundtruth or submission file not available locally"

        metrics = evaluate.compute_classification_metrics(gt_path_attr, sub_file_path)

        # persist metrics
        try:
            cols = set(models.Submission.__table__.columns.keys())
        except Exception:
            cols = set()

        if "metrics" in cols:
            setattr(sub, "metrics", json.dumps(metrics))
        for key in ("accuracy", "f1", "precision", "recall", "score"):
            if key in cols and metrics.get(key) is not None:
                try:
                    setattr(sub, key, float(metrics.get(key)))
                except Exception:
                    pass

        db.add(sub)
        db.commit()
        db.refresh(sub)
        return True, metrics
    except Exception as exc:
        return False, str(exc)


@router.post("/{submission_id}/recompute", status_code=200)
def recompute_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    ok, info = _compute_and_persist_metrics(sub, db)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Recompute failed: {info}")
    return {"id": submission_id, "metrics": info}


@router.post("/recompute", status_code=200)
def recompute_all_submissions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # admin only
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="admin required")

    subs = db.query(models.Submission).all()
    total = len(subs)
    updated = 0
    errors = []
    for s in subs:
        ok, info = _compute_and_persist_metrics(s, db)
        if ok:
            updated += 1
        else:
            errors.append({"id": getattr(s, "id", None), "error": info})
    return {"total": total, "updated": updated, "errors": errors}
