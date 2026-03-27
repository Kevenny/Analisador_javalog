import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Analysis
from ..schemas import UploadResponse
from ..services.storage import storage_service
from ..tasks.heap_task import analyze_heap
from ..tasks.thread_task import analyze_thread
from ..tasks.profile_task import analyze_profile

router = APIRouter()

ALLOWED_EXTENSIONS = {".hprof", ".tdump", ".nps"}
HEAP_EXTENSIONS = {".hprof"}
THREAD_EXTENSIONS = {".tdump"}
PROFILE_EXTENSIONS = {".nps"}


def detect_type(filename: str, content_type: str) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in HEAP_EXTENSIONS:
        return "heap"
    if ext in PROFILE_EXTENSIONS:
        return "profile"
    return "thread"


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile, db: Session = Depends(get_db)):
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não suportado: {ext}. Use .hprof (heap dump), .tdump (thread dump) ou .nps (profile)",
        )

    job_id = str(uuid.uuid4())
    dump_type = detect_type(filename, file.content_type or "")
    minio_key = f"{job_id}/{filename}"

    # Stream upload to MinIO
    content = await file.read()
    import io
    storage_service.upload_file(
        minio_key,
        io.BytesIO(content),
        file.content_type or "application/octet-stream",
        len(content),
    )

    analysis = Analysis(
        job_id=job_id,
        filename=filename,
        type=dump_type,
        status="queued",
        minio_key=minio_key,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    if dump_type == "heap":
        analyze_heap.delay(analysis.id, minio_key)
    elif dump_type == "profile":
        analyze_profile.delay(analysis.id, minio_key)
    else:
        analyze_thread.delay(analysis.id, minio_key)

    return UploadResponse(job_id=job_id, analysis_id=analysis.id, status="queued")
