from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..deps import get_current_user, require_admin
from ..evaluate import analyze_groundtruth
from ..utils.pagination import Paginator
import os, shutil, uuid, io, tempfile, logging, urllib.request, urllib.error
from typing import Optional, List

# MinIO client
from minio import Minio

router = APIRouter(prefix="/datasets", tags=["datasets"])

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "datasets")
os.makedirs(DATA_DIR, exist_ok=True)

# MinIO config (override via env)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() in ("1", "true", "yes")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "datasets")

minio_client = Minio(
    endpoint=MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

logger = logging.getLogger(__name__)

def is_minio_ready(timeout: float = 2.0) -> bool:
    """Quick HTTP health check against MinIO readiness endpoint."""
    scheme = "https" if MINIO_SECURE else "http"
    url = f"{scheme}://{MINIO_ENDPOINT}/minio/health/ready"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

def ensure_minio_bucket(bucket_name: str):
    try:
        if not is_minio_ready():
            raise RuntimeError("MinIO server not ready")
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
    except Exception as e:
        logger.exception("MinIO ensure bucket failed")
        raise

# ensure bucket exists (best-effort at import time)
try:
    ensure_minio_bucket(MINIO_BUCKET)
except Exception:
    # ignore here; runtime will return proper error if storage unavailable
    pass

@router.get("/", response_model=schemas.Page[schemas.DatasetOut])
def list_datasets(
    params: schemas.DatasetFilterParams = Depends(),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """List datasets with pagination and filters. Regular users see only official
    datasets and their own uploads. Admins see all datasets."""
    # build base query
    q = db.query(models.Dataset)
    
    # apply filters from params
    if getattr(params, "is_official", None) is not None:
        q = q.filter(models.Dataset.is_official == params.is_official)
    if getattr(params, "uploader_id", None) is not None:
        q = q.filter(models.Dataset.uploader_id == params.uploader_id)
    else:
        # non-admins see only official datasets or their own uploads
        try:
            if user and getattr(user, "role", None) != "admin":
                q = q.filter((models.Dataset.is_official == True) |
                             (models.Dataset.uploader_id == user.id))
        except Exception:
            # if user info missing, default to only official datasets
            q = q.filter(models.Dataset.is_official == True)

    page = Paginator(
        query=q.order_by(models.Dataset.created_at.desc()),
        page=params.page,
        page_size=params.page_size
    ).execute()

    # attach uploader username/full_name for frontend convenience
    uploader_ids = {getattr(ds, "uploader_id", None) for ds in page.items}
    uploader_ids.discard(None)
    users_map = {}
    if uploader_ids:
        users = db.query(models.User).filter(models.User.id.in_(list(uploader_ids))).all()
        for u in users:
            users_map[getattr(u, "id")] = u

    items = []
    for ds in page.items:
        # convert SQLAlchemy model to dict-like object accepted by Pydantic
        obj = {}
        for k, v in ds.__dict__.items():
            if k == "_sa_instance_state":
                continue
            if hasattr(v, "isoformat"):
                try:
                    obj[k] = v.isoformat()
                except Exception:
                    obj[k] = v
            else:
                obj[k] = v
        u = users_map.get(obj.get("uploader_id"))
        if u:
            obj["uploader_username"] = getattr(u, "username", None)
            obj["uploader_full_name"] = getattr(u, "full_name", None)
            # also provide uploader for backward compatibility
            obj.setdefault("uploader", obj.get("uploader_username") or obj.get("uploader_id"))
        items.append(obj)

    return {"items": items, "total": page.total, "page": page.page, "page_size": page.page_size}

@router.post("/", response_model=schemas.DatasetOut, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    name: str = Form(...),
    description: str = Form(""),
    data_file: Optional[UploadFile] = File(None),
    groundtruth_csv: UploadFile = File(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Upload a new dataset. Authenticated users can create datasets.
    - data_file: Optional dataset file (e.g. images archive)
    - groundtruth_csv: Required CSV with ground truth labels (must have id,label columns)
    Files are uploaded to MinIO and DB stores minio://bucket/object paths.
    """
    data_path = None
    data_obj_name = None
    gt_obj_name = None

    # ensure storage available before starting upload
    try:
        # fast health check first
        if not is_minio_ready():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage unavailable (MinIO not ready). Check MinIO server"
            )
        ensure_minio_bucket(MINIO_BUCKET)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage unavailable (bucket check/create failed)"
        )

    # 1) upload files to MinIO
    try:
        if data_file is not None:
            ext = os.path.splitext(data_file.filename)[1]
            data_obj_name = f"{uuid.uuid4()}{ext}"
            data_bytes = await data_file.read()
            data_stream = io.BytesIO(data_bytes)
            data_stream.seek(0)
            minio_client.put_object(
                MINIO_BUCKET,
                data_obj_name,
                data_stream,
                length=len(data_bytes),
                content_type=(data_file.content_type or "application/octet-stream")
            )
            data_path = f"minio://{MINIO_BUCKET}/{data_obj_name}"

        gt_ext = os.path.splitext(groundtruth_csv.filename)[1]
        if gt_ext.lower() != '.csv':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ground truth file must be a CSV"
            )

        gt_obj_name = f"{uuid.uuid4()}.csv"
        gt_bytes = await groundtruth_csv.read()
        gt_stream = io.BytesIO(gt_bytes)
        gt_stream.seek(0)
        minio_client.put_object(
            MINIO_BUCKET,
            gt_obj_name,
            gt_stream,
            length=len(gt_bytes),
            content_type="text/csv"
        )
        gt_path = f"minio://{MINIO_BUCKET}/{gt_obj_name}"
    except HTTPException:
        # validation errors - propagate
        raise
    except Exception as e:
        logger.exception("MinIO upload failed")
        # cleanup any partial uploads (best-effort, ignore failures)
        try:
            if data_obj_name:
                try:
                    minio_client.remove_object(MINIO_BUCKET, data_obj_name)
                except Exception:
                    logger.debug("remove_object data_obj_name failed (ignored)", exc_info=True)
        except Exception:
            logger.debug("cleanup data_obj failed (ignored)", exc_info=True)
        try:
            if gt_obj_name:
                try:
                    minio_client.remove_object(MINIO_BUCKET, gt_obj_name)
                except Exception:
                    logger.debug("remove_object gt_obj_name failed (ignored)", exc_info=True)
        except Exception:
            logger.debug("cleanup gt_obj failed (ignored)", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to upload files to storage (MinIO error). Check MinIO logs"
        )

    # 2) store metadata in DB
    try:
        ds = models.Dataset(
            name=name, description=description,
            data_file_path=data_path, groundtruth_path=gt_path,
            uploader_id=user.id
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)
        return ds
    except Exception as e:
        logger.exception("DB commit failed, removing uploaded objects")
        # best-effort cleanup, but don't raise low-level client errors
        try:
            if data_obj_name:
                try:
                    minio_client.remove_object(MINIO_BUCKET, data_obj_name)
                except Exception:
                    logger.debug("remove_object during DB rollback failed (ignored)", exc_info=True)
        except Exception:
            pass
        try:
            if gt_obj_name:
                try:
                    minio_client.remove_object(MINIO_BUCKET, gt_obj_name)
                except Exception:
                    logger.debug("remove_object during DB rollback failed (ignored)", exc_info=True)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create dataset (database). Uploaded objects removed (if possible)"
        )

@router.post("/{id}/mark_official", dependencies=[Depends(require_admin)],
           response_model=schemas.DatasetOut)
def mark_official(id: int, db: Session = Depends(get_db)):
    """Mark a dataset as official (only one can be official at a time). Admin only."""
    ds = db.query(models.Dataset).get(id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Clear official flag from all datasets and set this one
    db.query(models.Dataset).update({"is_official": False})
    ds.is_official = True
    db.commit()
    db.refresh(ds)
    return ds

@router.get("/{id}", response_model=schemas.DatasetOut)
def get_dataset(
    id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Get dataset details. Users can only see official datasets or their own uploads."""
    ds = db.query(models.Dataset).get(id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    if user.role != "admin" and not ds.is_official and ds.uploader_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    # attach uploader username/full_name for frontend convenience
    try:
        if ds.uploader_id is not None:
            u = db.query(models.User).filter(models.User.id == ds.uploader_id).first()
            if u:
                setattr(ds, "uploader_username", getattr(u, "username", None))
                setattr(ds, "uploader_full_name", getattr(u, "full_name", None))
                # backward compat
                if not getattr(ds, "uploader", None):
                    setattr(ds, "uploader", getattr(u, "username", None))
    except Exception:
        pass
    return ds

@router.get("/{id}/groundtruth")
def download_groundtruth(
    id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Download dataset ground truth CSV.
    Access policy: admins or the dataset uploader can download the groundtruth CSV.
    """
    ds = db.query(models.Dataset).get(id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    if not ds.groundtruth_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ground truth file not found"
        )

    # authorization: allow admin or original uploader
    try:
        if user.role != "admin" and ds.uploader_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    safe_name = "".join(c for c in ds.name if c.isalnum() or c in "-_").lower()
    filename = f"{safe_name}_groundtruth.csv"

    if ds.groundtruth_path.startswith("minio://"):
        _, _, path = ds.groundtruth_path.partition("://")
        bucket, _, obj = path.partition("/")
        try:
            obj_resp = minio_client.get_object(bucket, obj)
            headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
            return StreamingResponse(obj_resp, media_type="text/csv", headers=headers)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ground truth file not found in storage"
            )
    else:
        # fallback to local filesystem
        if not os.path.exists(ds.groundtruth_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ground truth file not found"
            )
        return FileResponse(
            ds.groundtruth_path,
            media_type="text/csv",
            filename=filename
        )

@router.get("/{id}/data")
def download_dataset_file(
    id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Download the dataset's main data file (if any).
    Access policy: admins can download any; non-admins can download official datasets
    or their own uploads."""
    ds = db.query(models.Dataset).get(id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )

    if user.role != "admin" and not ds.is_official and ds.uploader_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    if not ds.data_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset file not found"
        )

    safe_name = "".join(c for c in ds.name if c.isalnum() or c in "-_").lower()
    # Try to preserve original extension if present in object name
    filename = f"{safe_name}_data"

    if ds.data_file_path.startswith("minio://"):
        _, _, path = ds.data_file_path.partition("://")
        bucket, _, obj = path.partition("/")
        # infer extension from object key
        _, ext = os.path.splitext(obj)
        if ext:
            filename = f"{filename}{ext}"
        try:
            obj_resp = minio_client.get_object(bucket, obj)
            headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
            # content type best-effort
            media_type = "application/octet-stream"
            return StreamingResponse(obj_resp, media_type=media_type, headers=headers)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset file not found in storage"
            )
    else:
        # local filesystem path
        if not os.path.exists(ds.data_file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset file not found"
            )
        _, ext = os.path.splitext(ds.data_file_path)
        if ext:
            filename = f"{filename}{ext}"
        return FileResponse(
            ds.data_file_path,
            media_type="application/octet-stream",
            filename=filename
        )

@router.delete("/{id}", response_model=schemas.DatasetOut)
def delete_dataset(
    id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Delete a dataset. Only admin or the original uploader can delete.
    Performs best-effort cleanup of stored files in MinIO or local filesystem."""
    ds = db.query(models.Dataset).get(id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )

    if user.role != "admin" and ds.uploader_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Attempt to remove storage objects
    def remove_path(p: Optional[str]):
        if not p:
            return
        try:
            if p.startswith("minio://"):
                _, _, path = p.partition("://")
                bucket, _, obj = path.partition("/")
                try:
                    minio_client.remove_object(bucket, obj)
                except Exception:
                    # ignore failures but log
                    logger.debug("MinIO remove_object failed", exc_info=True)
            else:
                if os.path.exists(p):
                    try:
                        os.unlink(p)
                    except Exception:
                        logger.debug("Filesystem unlink failed", exc_info=True)
        except Exception:
            logger.debug("remove_path unexpected failure", exc_info=True)

    try:
        # Store copy for response after deletion
        deleted_ds = schemas.DatasetOut.from_orm(ds)
        # Delete DB row
        db.delete(ds)
        db.commit()
        # Cleanup storage after DB commit (best-effort)
        remove_path(getattr(deleted_ds, "data_file_path", None))
        remove_path(getattr(deleted_ds, "groundtruth_path", None))
        return deleted_ds
    except Exception as e:
        logger.exception("Failed to delete dataset")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete dataset"
        )

@router.post("/{id}/analyze", response_model=schemas.DatasetOut)
def analyze_dataset(id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    """Analyze dataset ground truth to compute statistics.
    Allowed for admins or the original uploader."""
    ds = db.query(models.Dataset).get(id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    # authorization: admins or uploader only
    try:
        if user.role != "admin" and ds.uploader_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    except Exception:
        # if user info missing or attribute access fails, deny
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    if not ds.groundtruth_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ground truth file not found"
        )

    temp_file = None
    try:
        if ds.groundtruth_path.startswith("minio://"):
            _, _, path = ds.groundtruth_path.partition("://")
            bucket, _, obj = path.partition("/")
            obj_resp = minio_client.get_object(bucket, obj)
            temp_f = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            temp_file = temp_f.name
            try:
                for chunk in obj_resp.stream(32*1024):
                    temp_f.write(chunk)
            finally:
                temp_f.close()
                try:
                    obj_resp.close()
                    obj_resp.release_conn()
                except Exception:
                    pass
            stats = analyze_groundtruth(temp_file)
        else:
            if not os.path.exists(ds.groundtruth_path):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Ground truth file not found"
                )
            stats = analyze_groundtruth(ds.groundtruth_path)

        ds.stats_json = stats
        db.commit()
        db.refresh(ds)
        return ds
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to analyze dataset: {str(e)}"
        )
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception:
                pass
