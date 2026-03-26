import os
import uuid

import httpx

from ..database import SessionLocal
from ..models import Analysis
from ..services.storage import storage_service
from .celery_app import celery

ANALYZER_URL = os.environ.get("ANALYZER_URL", "http://analyzer:5000")


@celery.task(bind=True, name="tasks.analyze_heap")
def analyze_heap(self, analysis_id: int, minio_key: str):
    db = SessionLocal()
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return

        analysis.status = "processing"
        db.commit()

        tmp_path = f"/tmp/dumps/{uuid.uuid4()}.hprof"
        os.makedirs("/tmp/dumps", exist_ok=True)
        storage_service.download_file(minio_key, tmp_path)

        try:
            response = httpx.post(
                f"{ANALYZER_URL}/analyze",
                json={"type": "heap", "file": tmp_path},
                timeout=600,
            )
            response.raise_for_status()
            result_data = response.json()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        analysis.result_json = result_data
        analysis.status = "done"
        db.commit()

    except Exception as exc:
        db.query(Analysis).filter(Analysis.id == analysis_id).update(
            {"status": "error", "error_message": str(exc)}
        )
        db.commit()
        raise
    finally:
        db.close()
