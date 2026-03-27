"""
Task para análise de arquivos locais (sem download do MinIO).
Lê diretamente o caminho em /data/dumps, adequado para arquivos grandes (20 GB+).
"""
import os

import httpx

from ..database import SessionLocal
from ..models import Analysis
from .celery_app import celery

ANALYZER_URL = os.environ.get("ANALYZER_URL", "http://analyzer:5000")


@celery.task(bind=True, name="tasks.analyze_direct")
def analyze_direct(self, analysis_id: int, file_path: str, dump_type: str):
    db = SessionLocal()
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return

        analysis.status = "processing"
        db.commit()

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        response = httpx.post(
            f"{ANALYZER_URL}/analyze",
            json={"type": dump_type, "file": file_path},
            timeout=3600,  # 1 hora para arquivos muito grandes
        )
        response.raise_for_status()
        result_data = response.json()

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
