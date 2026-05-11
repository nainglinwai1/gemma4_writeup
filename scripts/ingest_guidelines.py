"""
Ingest all guideline files from data/guidelines/ into ChromaDB.
Run once (or whenever new guidelines are added):

    conda activate mediscribe
    python scripts/ingest_guidelines.py
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from backend.rag import RAGPipeline

GUIDELINES_DIR = Path(__file__).parent.parent / "data" / "guidelines"


def main():
    rag = RAGPipeline()
    logger.info(f"Scanning {GUIDELINES_DIR} for guidelines...")

    files = list(GUIDELINES_DIR.glob("*.txt")) + list(GUIDELINES_DIR.glob("*.pdf"))
    if not files:
        logger.warning("No .txt or .pdf files found in data/guidelines/")
        return

    total = 0
    for f in sorted(files):
        logger.info(f"Ingesting: {f.name}")
        n = rag.ingest_file(f)
        total += n
        logger.success(f"  → {n} chunks")

    logger.success(f"Done. Total chunks in KB: {rag.collection_count()} (added {total} new)")


if __name__ == "__main__":
    main()
