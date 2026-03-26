from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    job_id: str
    analysis_id: int
    status: str


class AnalysisSummary(BaseModel):
    id: int
    filename: str
    type: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisDetail(BaseModel):
    id: int
    job_id: str
    filename: str
    type: str
    status: str
    result: Optional[Any] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
