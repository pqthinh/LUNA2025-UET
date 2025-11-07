from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user, require_admin
from .. import models
import os, time, httpx

router = APIRouter(prefix="/apitest", tags=["apitest"])

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "samples")
os.makedirs(SAMPLE_DIR, exist_ok=True)

# Put two tiny placeholder sample files
for i in range(1,3):
    p = os.path.join(SAMPLE_DIR, f"sample_{i}.txt")
    if not os.path.exists(p):
        with open(p, "w") as f: f.write(f"sample-{i}")

@router.get("/samples")
def list_samples():
    files = [f for f in os.listdir(SAMPLE_DIR) if os.path.isfile(os.path.join(SAMPLE_DIR,f))]
    return [{"name": fn, "path": f"/apitest/sample/{fn}"} for fn in files]

@router.get("/sample/{name}")
def download_sample(name: str):
    path = os.path.join(SAMPLE_DIR, name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Sample not found")
    return {"name": name, "size": os.path.getsize(path)}

@router.post("/call", dependencies=[Depends(require_admin)])
def call_model(url: str = Form(...), sample_name: str = Form(...), db: Session = Depends(get_db), user = Depends(get_current_user)):
    file_path = os.path.join(SAMPLE_DIR, sample_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Sample not found")

    timeout = float(os.getenv("API_TEST_TIMEOUT", "10"))
    start = time.perf_counter()
    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
            with httpx.Client(timeout=timeout) as client:
                r = client.post(url, files=files)
        elapsed = (time.perf_counter() - start) * 1000.0
        preview = r.text[:500]
        status = r.status_code
    except Exception as ex:
        elapsed = (time.perf_counter() - start) * 1000.0
        status = 0
        preview = f"ERROR: {ex}"

    log = models.ApiLog(
        request_url=url,
        status_code=int(status),
        response_time=float(elapsed),
        result_preview=preview
    )
    db.add(log); db.commit()
    return {"status_code": status, "latency_ms": elapsed, "preview": preview}
