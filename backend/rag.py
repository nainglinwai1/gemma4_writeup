"""
RAG pipeline: loads medical guidelines into ChromaDB and retrieves
relevant context for a given patient note query.
All operations are fully offline after first embedding model download.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger
from sentence_transformers import SentenceTransformer

from backend.config import settings


class RAGPipeline:
    def __init__(self) -> None:
        self._embedder = SentenceTransformer(settings.embedding_model)
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB ready — collection '{settings.chroma_collection}' "
            f"({self._collection.count()} docs)"
        )

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_text(self, text: str, source: str, chunk_size: int = 600) -> int:
        """Chunk text and upsert into ChromaDB. Returns number of new chunks."""
        chunks = self._chunk(text, chunk_size)
        ids, embeddings, documents, metadatas = [], [], [], []
        for i, chunk in enumerate(chunks):
            doc_id = hashlib.md5(f"{source}:{i}:{chunk[:40]}".encode()).hexdigest()
            ids.append(doc_id)
            embeddings.append(self._embedder.encode(chunk).tolist())
            documents.append(chunk)
            metadatas.append({"source": source, "chunk_index": i})

        if ids:
            self._collection.upsert(
                ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
            )
            logger.info(f"Ingested {len(ids)} chunks from '{source}'")
        return len(ids)

    def ingest_file(self, path: Path) -> int:
        """Ingest a .txt or .pdf file."""
        suffix = path.suffix.lower()
        if suffix == ".txt":
            text = path.read_text(encoding="utf-8", errors="ignore")
        elif suffix == ".pdf":
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        else:
            logger.warning(f"Unsupported file type: {path}")
            return 0
        return self.ingest_text(text, source=path.name)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int | None = None) -> List[dict]:
        """Return top-k most relevant guideline chunks for the query."""
        k = top_k or settings.rag_top_k
        if self._collection.count() == 0:
            return []

        query_embedding = self._embedder.encode(query).tolist()
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append(
                {
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "relevance": round(1 - dist, 3),
                }
            )
        return chunks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _chunk(text: str, size: int) -> List[str]:
        """Split text into overlapping chunks by words."""
        words = text.split()
        overlap = size // 5
        chunks, i = [], 0
        while i < len(words):
            chunk = " ".join(words[i : i + size])
            if chunk.strip():
                chunks.append(chunk)
            i += size - overlap
        return chunks

    def collection_count(self) -> int:
        return self._collection.count()
