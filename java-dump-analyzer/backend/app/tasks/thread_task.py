import os
import uuid

from ..database import SessionLocal
from ..models import Analysis
from ..services.storage import storage_service
from .celery_app import celery


@celery.task(bind=True, name="tasks.analyze_thread")
def analyze_thread(self, analysis_id: int, minio_key: str):
    db = SessionLocal()
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return

        analysis.status = "processing"
        db.commit()

        tmp_path = f"/tmp/{uuid.uuid4()}.txt"
        storage_service.download_file(minio_key, tmp_path)

        try:
            import subprocess, json
            result = subprocess.run(
                ["python3", "/analyzer/run_analysis.py", "--type", "thread", "--file", tmp_path],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr)
            result_data = json.loads(result.stdout)
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
