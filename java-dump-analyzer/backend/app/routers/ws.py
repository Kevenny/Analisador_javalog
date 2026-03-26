import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Analysis

router = APIRouter()


@router.websocket("/ws/{job_id}")
async def websocket_status(websocket: WebSocket, job_id: str):
    await websocket.accept()
    db: Session = SessionLocal()
    try:
        while True:
            analysis = db.query(Analysis).filter(Analysis.job_id == job_id).first()
            if not analysis:
                await websocket.send_text(json.dumps({"status": "error", "message": "Job not found"}))
                break

            if analysis.status == "done":
                await websocket.send_text(
                    json.dumps({"status": "done", "analysis_id": analysis.id})
                )
                break
            elif analysis.status == "error":
                await websocket.send_text(
                    json.dumps({"status": "error", "message": analysis.error_message or "Unknown error"})
                )
                break
            elif analysis.status == "processing":
                await websocket.send_text(json.dumps({"status": "processing", "progress": 50}))
            else:
                await websocket.send_text(json.dumps({"status": "queued", "progress": 0}))

            db.expire_all()
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    finally:
        db.close()
