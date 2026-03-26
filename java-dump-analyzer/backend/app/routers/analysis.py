from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Analysis
from ..schemas import AnalysisDetail, AnalysisSummary

router = APIRouter()


@router.get("/analysis/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisDetail(
        id=analysis.id,
        job_id=analysis.job_id,
        filename=analysis.filename,
        type=analysis.type,
        status=analysis.status,
        result=analysis.result_json,
        error_message=analysis.error_message,
        created_at=analysis.created_at,
    )


@router.get("/analyses", response_model=List[AnalysisSummary])
def list_analyses(
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    per_page = 20
    offset = (page - 1) * per_page
    rows = (
        db.query(Analysis)
        .order_by(Analysis.created_at.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )
    return [
        AnalysisSummary(
            id=r.id,
            filename=r.filename,
            type=r.type,
            status=r.status,
            created_at=r.created_at,
        )
        for r in rows
    ]
