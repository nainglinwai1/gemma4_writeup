from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e4b"
    ollama_timeout: int = 120

    # ChromaDB
    chroma_persist_dir: str = str(BASE_DIR / "data" / "ingested")
    chroma_collection: str = "medical_guidelines"

    # Embeddings (runs locally, no internet required)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # RAG
    rag_top_k: int = 4

    class Config:
        env_file = BASE_DIR / ".env"


settings = Settings()
