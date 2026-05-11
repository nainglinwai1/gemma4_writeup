"""
FastAPI application — MediScribe Rural
Offline-first medical documentation assistant powered by Gemma 4 + Ollama.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel

from backend.config import settings
from backend.llm import GemmaClient
from backend.rag import RAGPipeline

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MediScribe Rural",
    description="Offline-first clinical documentation assistant powered by Gemma 4",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-loaded singletons (avoid loading at import time for tests)
_rag: RAGPipeline | None = None
_llm: GemmaClient | None = None


def get_rag() -> RAGPipeline:
    global _rag
    if _rag is None:
        _rag = RAGPipeline()
    return _rag


def get_llm() -> GemmaClient:
    global _llm
    if _llm is None:
        _llm = GemmaClient()
    return _llm


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class EncounterRequest(BaseModel):
    note: str
    language: str = "en"
    top_k: int = 4


class EncounterResponse(BaseModel):
    soap_note: str
    extracted_entities: dict
    alerts: list
    guideline_chunks_used: int
    model: str


class IngestResponse(BaseModel):
    filename: str
    chunks_added: int
    total_chunks: int


class HealthResponse(BaseModel):
    status: str
    ollama_ok: bool
    model: str
    guideline_chunks: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    """System health check — used by the frontend to show offline status."""
    rag = get_rag()
    llm_ok = False
    try:
        llm = get_llm()
        llm_ok = llm.health_check()
    except Exception:
        pass
    return {
        "status": "ok" if llm_ok else "degraded",
        "ollama_ok": llm_ok,
        "model": settings.ollama_model,
        "guideline_chunks": rag.collection_count(),
    }


@app.post("/encounter", response_model=EncounterResponse, tags=["clinical"])
async def process_encounter(req: EncounterRequest):
    """
    Core endpoint: accepts a raw encounter note, retrieves relevant
    guideline context via RAG, and returns a structured SOAP note with
    extracted ICD-10 codes and clinical entities.
    """
    if not req.note.strip():
        raise HTTPException(status_code=422, detail="Encounter note cannot be empty.")

    logger.info(f"Processing encounter — {len(req.note)} chars, lang={req.language}")

    rag = get_rag()
    llm = get_llm()

    # 1. Retrieve guideline context
    chunks = rag.retrieve(req.note, top_k=req.top_k)
    logger.debug(f"Retrieved {len(chunks)} guideline chunks")

    # 2. Generate SOAP note via Gemma 4
    try:
        result = llm.process_encounter(
            encounter_note=req.note,
            guideline_chunks=chunks,
            language=req.language,
        )
    except Exception as e:
        logger.exception("LLM processing failed")
        raise HTTPException(status_code=503, detail=f"LLM error: {str(e)}")

    return result


@app.post("/ingest", response_model=IngestResponse, tags=["knowledge-base"])
async def ingest_guideline(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload a medical guideline (PDF or TXT) to be chunked, embedded,
    and stored in the local ChromaDB vector store.
    """
    allowed = {".pdf", ".txt"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. Allowed: {allowed}",
        )

    content = await file.read()
    save_path = Path(settings.chroma_persist_dir).parent / "guidelines" / file.filename
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(content)

    rag = get_rag()
    chunks_added = rag.ingest_file(save_path)

    return {
        "filename": file.filename,
        "chunks_added": chunks_added,
        "total_chunks": rag.collection_count(),
    }


@app.get("/guidelines", tags=["knowledge-base"])
async def list_guidelines():
    """List all ingested guideline files."""
    guidelines_dir = Path(settings.chroma_persist_dir).parent / "guidelines"
    if not guidelines_dir.exists():
        return {"files": [], "total_chunks": 0}
    files = [f.name for f in guidelines_dir.iterdir() if f.is_file()]
    rag = get_rag()
    return {"files": files, "total_chunks": rag.collection_count()}


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
