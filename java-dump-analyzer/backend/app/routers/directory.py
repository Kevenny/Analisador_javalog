"""
Router para análise de arquivos via diretório local.
Permite analisar arquivos grandes sem upload HTTP — lidos diretamente do disco.
"""
import os
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Analysis
from ..schemas import UploadResponse
from ..tasks.direct_task import analyze_direct

router = APIRouter()

SUPPORTED_EXTENSIONS = {".hprof", ".tdump", ".nps"}

TYPE_BY_EXT = {
    ".hprof": "heap",
    ".tdump": "thread",
    ".nps": "profile",
}

EXT_LABELS = {
    ".hprof": "Heap Dump",
    ".tdump": "Thread Dump",
    ".nps": "Profile",
}


class FileEntry(BaseModel):
    name: str
    relative_path: str          # relativo a input_dumps_dir
    absolute_path: str
    size_bytes: int
    type: str                   # heap | thread | profile
    ext: str


class AnalyzeLocalRequest(BaseModel):
    absolute_path: str          # deve estar dentro de input_dumps_dir


def _is_safe_path(base: str, target: str) -> bool:
    """Garante que o caminho está dentro do diretório base (evita path traversal)."""
    try:
        Path(target).resolve().relative_to(Path(base).resolve())
        return True
    except ValueError:
        return False


@router.get("/dir/list", response_model=List[FileEntry])
def list_directory(db: Session = Depends(get_db)):
    base = settings.input_dumps_dir
    if not os.path.isdir(base):
        return []

    entries: List[FileEntry] = []
    for dirpath, _, filenames in os.walk(base):
        for fname in sorted(filenames):
            ext = Path(fname).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            abs_path = os.path.join(dirpath, fname)
            try:
                size = os.path.getsize(abs_path)
            except OSError:
                continue
            rel = os.path.relpath(abs_path, base)
            entries.append(FileEntry(
                name=fname,
                relative_path=rel,
                absolute_path=abs_path,
                size_bytes=size,
                type=TYPE_BY_EXT[ext],
                ext=ext,
            ))

    # ordena por tamanho decrescente
    entries.sort(key=lambda e: e.size_bytes, reverse=True)
    return entries


@router.post("/dir/analyze", response_model=UploadResponse)
def analyze_local_file(req: AnalyzeLocalRequest, db: Session = Depends(get_db)):
    base = settings.input_dumps_dir
    abs_path = req.absolute_path

    if not _is_safe_path(base, abs_path):
        raise HTTPException(
            status_code=400,
            detail=f"Caminho fora do diretório permitido: {base}",
        )
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado: {abs_path}")

    ext = Path(abs_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Extensão não suportada: {ext}. Use .hprof, .tdump ou .nps",
        )

    dump_type = TYPE_BY_EXT[ext]
    filename = os.path.basename(abs_path)
    job_id = str(uuid.uuid4())
    # minio_key usa prefixo "local://" para distinguir de uploads MinIO
    minio_key = f"local://{abs_path}"

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

    analyze_direct.delay(analysis.id, abs_path, dump_type)

    return UploadResponse(job_id=job_id, analysis_id=analysis.id, status="queued")
