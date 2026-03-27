from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers import analysis, directory, upload, ws
from .services.storage import storage_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    Base.metadata.create_all(bind=engine)
    # Ensure MinIO bucket exists
    storage_service.ensure_bucket()
    yield


app = FastAPI(
    title="Java Dump Analyzer API",
    description="API for analyzing Java Heap Dumps and Thread Dumps",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(directory.router, prefix="/api")
app.include_router(ws.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
