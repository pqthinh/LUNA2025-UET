from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
import os
import json
import io
import uuid
import tempfile
import logging
import shutil
import urllib.request
from urllib.parse import urlparse
from minio import Minio
from app import models, evaluate
from app.deps import get_db, get_current_user

router = APIRouter(prefix="/submissions", tags=["submissions"])

# MinIO configuration (re-use dataset env vars if available)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() in ("1", "true", "yes")
MINIO_SUBMISSIONS_BUCKET = os.getenv("MINIO_SUBMISSIONS_BUCKET", "submissions")

minio_client = Minio(
    endpoint=MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE,
)

logger = logging.getLogger(__name__)


def is_minio_ready(timeout: float = 2.0) -> bool:
    """Simple readiness probe for MinIO."""
    scheme = "https" if MINIO_SECURE else "http"
    url = f"{scheme}://{MINIO_ENDPOINT}/minio/health/ready"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def ensure_minio_bucket(bucket_name: str):
    if not is_minio_ready():
        raise RuntimeError("MinIO server not ready")
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)


def _parse_minio_uri(uri: str):
    if not uri or not uri.startswith("minio://"):
        return None, None
    parsed = urlparse(uri)
    bucket = parsed.netloc
    obj = parsed.path.lstrip("/")
    return bucket, obj


def _download_minio_object(uri: str) -> str | None:
    bucket, obj = _parse_minio_uri(uri)
    if not bucket or not obj:
        return None
    tmp_path = None
    try:
        obj_resp = minio_client.get_object(bucket, obj)
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp_path = tmp.name
        try:
            shutil.copyfileobj(obj_resp, tmp)
        finally:
            tmp.close()
            try:
                obj_resp.close()
                obj_resp.release_conn()
            except Exception:
                pass
        return tmp_path
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        return None


def _delete_submission_artifact(path_value: str | None):
    if not path_value or not isinstance(path_value, str):
        return
    if path_value.startswith("minio://"):
        bucket, obj = _parse_minio_uri(path_value)
        if bucket and obj:
            try:
                minio_client.remove_object(bucket, obj)
            except Exception:
                pass
        return

    actual_path = path_value
    if not os.path.isabs(actual_path):
        actual_path = os.path.join(os.getcwd(), "app", "uploads", "submissions", actual_path)
    if os.path.exists(actual_path):
        try:
            os.remove(actual_path)
        except Exception:
            pass


def _normalize_score_json(metrics: dict | None) -> dict:
    """Standardize metric dicts to canonical keys and uppercase variants for downstream consumers."""
    if not isinstance(metrics, dict):
        return {}
    normalized = dict(metrics)

    def _value_for(key: str):
        return normalized.get(key) or normalized.get(key.upper()) or normalized.get(key.capitalize())

    canonical_map = {
        "auc": [],
        "precision": [],
        "recall": [],
        "f1": [],
        "acc": ["accuracy"],
    }

    for base_key, extra_keys in canonical_map.items():
        candidates = [base_key] + extra_keys
        val = None
        for candidate in candidates:
            val = _value_for(candidate)
            if val is not None:
                break
        if val is None:
            continue
        for alias in candidates:
            normalized.pop(alias, None)
            normalized.pop(alias.upper(), None)
            normalized.pop(alias.capitalize(), None)
        normalized[base_key] = val
        normalized[base_key.upper()] = val
    return normalized


try:
    ensure_minio_bucket(MINIO_SUBMISSIONS_BUCKET)
except Exception:
    # best-effort – endpoints will return explicit errors if storage unavailable
    pass

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
        raw_metrics = d.get("score_json") or d.get("metrics")
        if isinstance(raw_metrics, str):
            try:
                metrics = json.loads(raw_metrics)
            except Exception:
                metrics = None
        elif isinstance(raw_metrics, dict):
            metrics = raw_metrics

        if isinstance(metrics, dict):
            metrics = _normalize_score_json(metrics)
            d["score_json"] = metrics

        for k in ("f1", "precision", "recall", "acc", "score"):
            if k in d:
                try:
                    d[k] = float(d[k]) if d[k] is not None else None
                except Exception:
                    pass

        if metrics and isinstance(metrics, dict):
            for mk in ("f1", "precision", "recall", "acc"):
                if mk in metrics and mk not in d:
                    try:
                        d[mk] = float(metrics[mk])
                    except Exception:
                        d[mk] = metrics[mk]
            d["metrics"] = metrics

        # If no metrics present, try to compute them on-the-fly (best-effort)
        if not any(k in d for k in ("f1", "precision", "recall", "acc", "metrics")):
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
                        for mk in ("acc", "f1", "precision", "recall"):
                            if mk in computed:
                                try:
                                    d[mk] = float(computed[mk])
                                except Exception:
                                    d[mk] = computed[mk]
                        # alias score -> acc if not present
                        if "score" not in d and "acc" in d:
                            d["score"] = float(d["acc"])
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
    # save uploaded file to MinIO
    try:
        if not is_minio_ready():
            raise HTTPException(status_code=503, detail="Storage unavailable (MinIO not ready)")
        ensure_minio_bucket(MINIO_SUBMISSIONS_BUCKET)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Storage unavailable (MinIO error)")

    object_name = None
    storage_path = None
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        ext = os.path.splitext(file.filename or "submission.csv")[1]
        user_prefix = f"user_{current_user.id}"
        ds_prefix = f"dataset_{dataset_id}" if dataset_id else "dataset_unknown"
        object_name = f"{user_prefix}/{ds_prefix}/{uuid.uuid4().hex}{ext}"
        data_stream = io.BytesIO(file_bytes)
        data_stream.seek(0)
        minio_client.put_object(
            MINIO_SUBMISSIONS_BUCKET,
            object_name,
            data_stream,
            length=len(file_bytes),
            content_type=file.content_type or "text/csv",
        )
        storage_path = f"minio://{MINIO_SUBMISSIONS_BUCKET}/{object_name}"

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to upload submission to MinIO")
        if object_name:
            try:
                minio_client.remove_object(MINIO_SUBMISSIONS_BUCKET, object_name)
            except Exception:
                pass
        raise HTTPException(status_code=502, detail="Failed to upload submission to storage")

    # create DB record robustly (don't pass unknown kwargs to SQLAlchemy constructor)
    sub = models.Submission()  # create empty instance then set attributes
    # discover model columns to avoid invalid keyword args
    try:
        cols = set(models.Submission.__table__.columns.keys())
    except Exception:
        cols = set()

    if "user_id" in cols:
        setattr(sub, "user_id", current_user.id)
    elif "uploader_id" in cols:
        setattr(sub, "uploader_id", current_user.id)
    else:
        # fallback attribute name if different
        try:
            setattr(sub, "uploader", current_user.id)
        except Exception:
            pass

    # store file info in whichever column exists
    if "file_path" in cols:
        sub.file_path = storage_path
    elif "path" in cols:
        sub.path = storage_path
    elif "storage_path" in cols:
        sub.storage_path = storage_path
    elif "file_name" in cols:
        sub.file_name = os.path.basename(object_name)
    elif "filename" in cols:
        sub.filename = os.path.basename(object_name)
    else:
        # last resort: attach as filename attribute (SQLAlchemy will ignore unknown attrs on commit)
        setattr(sub, "filename", os.path.basename(object_name))

    # dataset relation if present
    if dataset_id is not None and "dataset_id" in cols:
        try:
            sub.dataset_id = int(dataset_id)
        except Exception:
            sub.dataset_id = dataset_id

    try:
        db.add(sub)
        db.commit()
        db.refresh(sub)
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to create submission in DB")
        if storage_path and storage_path.startswith("minio://"):
            bucket, obj = _parse_minio_uri(storage_path)
            if bucket and obj:
                try:
                    minio_client.remove_object(bucket, obj)
                except Exception:
                    pass
        raise HTTPException(status_code=500, detail="Failed to create submission")

    # compute metrics if dataset provided (best-effort)
    metrics_payload = None
    if dataset_id:
        ok, metrics_payload = _compute_and_persist_metrics(sub, db)
        if not ok:
            logger.warning("Submission %s evaluation failed: %s", getattr(sub, "id", None), metrics_payload)

    # return best-effort summary (unchanged)
    out = {"id": getattr(sub, "id", None)}
    for key in ("filename", "file_name", "file_path", "path", "storage_path", "dataset_id", "score", "uploader_id"):
        if hasattr(sub, key):
            out[key] = getattr(sub, key)
    # attach normalized metrics for frontend/legacy clients
    if hasattr(sub, "score_json") and getattr(sub, "score_json") is not None:
        out["score_json"] = getattr(sub, "score_json")
        out.setdefault("metrics", out["score_json"])
    elif hasattr(sub, "metrics"):
        metrics_val = getattr(sub, "metrics")
        if isinstance(metrics_val, str):
            try:
                out["metrics"] = json.loads(metrics_val)
            except Exception:
                out["metrics"] = metrics_val
        else:
            out["metrics"] = metrics_val
    # include evaluation flag if present
    if hasattr(sub, "evaluated"):
        out["evaluated"] = getattr(sub, "evaluated")
    for k in ("acc", "f1", "precision", "recall"):
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
    owner_id = getattr(sub, "user_id", None)
    if owner_id is None:
        owner_id = getattr(sub, "uploader_id", None)
    if current_user.role != "admin" and owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this submission")

    # remove submission artifact (MinIO or local)
    for attr in ("file_path", "path", "storage_path", "filename", "file_name"):
        if hasattr(sub, attr) and getattr(sub, attr):
            _delete_submission_artifact(getattr(sub, attr))
            break
    db.delete(sub)
    db.commit()
    return {}

# helper to compute & persist metrics for one Submission instance
def _compute_and_persist_metrics(sub: "models.Submission", db: Session):
    cleanup_paths: list[str] = []
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
        for fld in ("file_path", "path", "storage_path", "file_name", "filename"):
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
            logger.warning("Submission %s missing dataset/submission paths (dataset=%s file=%s)", getattr(sub, "id", None), gt_path_attr, sub_file_path)
            return False, "missing paths"

        gt_local = gt_path_attr
        sub_local = sub_file_path

        if isinstance(gt_local, str) and gt_local.startswith("minio://"):
            tmp_gt = _download_minio_object(gt_local)
            if not tmp_gt:
                logger.warning("Submission %s failed to download groundtruth from %s", getattr(sub, "id", None), gt_local)
                return False, "failed to download groundtruth"
            cleanup_paths.append(tmp_gt)
            gt_local = tmp_gt

        if isinstance(sub_local, str) and sub_local.startswith("minio://"):
            tmp_sub = _download_minio_object(sub_local)
            if not tmp_sub:
                for p in cleanup_paths:
                    try:
                        os.unlink(p)
                    except Exception:
                        pass
                logger.warning("Submission %s failed to download submission file from %s", getattr(sub, "id", None), sub_local)
                return False, "failed to download submission"
            cleanup_paths.append(tmp_sub)
            sub_local = tmp_sub

        if not isinstance(gt_local, str) or not os.path.exists(gt_local) or not isinstance(sub_local, str) or not os.path.exists(sub_local):
            for p in cleanup_paths:
                try:
                    os.unlink(p)
                except Exception:
                    pass
            logger.warning("Submission %s groundtruth or submission missing locally (%s / %s)", getattr(sub, "id", None), gt_local, sub_local)
            return False, "groundtruth or submission file not available locally"

        metrics_result = None
        errors = []
        for scorer in (evaluate.evaluate_predictions, evaluate.compute_classification_metrics):
            try:
                metrics_result = scorer(gt_local, sub_local)
                break
            except Exception as exc:
                errors.append(str(exc))

        if not isinstance(metrics_result, dict):
            message = "; ".join(errors) if errors else "Metric computation produced no result"
            logger.warning("Submission %s metric computation failed with errors: %s", getattr(sub, "id", None), message)
            return False, message

        normalized_metrics = _normalize_score_json(metrics_result)

        # persist metrics
        try:
            cols = set(models.Submission.__table__.columns.keys())
        except Exception:
            cols = set()

        if "score_json" in cols:
            setattr(sub, "score_json", normalized_metrics)
        if "metrics" in cols:
            try:
                setattr(sub, "metrics", json.dumps(normalized_metrics))
            except Exception:
                setattr(sub, "metrics", normalized_metrics)
        if "evaluated" in cols:
            setattr(sub, "evaluated", True)
        for key in ("acc", "f1", "precision", "recall", "score"):
            if key in cols and normalized_metrics.get(key) is not None:
                try:
                    setattr(sub, key, float(normalized_metrics.get(key)))
                except Exception:
                    pass

        db.add(sub)
        db.commit()
        db.refresh(sub)
        return True, normalized_metrics
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            for p in cleanup_paths:
                if p and os.path.exists(p):
                    os.unlink(p)
        except Exception:
            pass


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
