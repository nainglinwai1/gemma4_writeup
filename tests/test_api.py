"""
Basic integration tests for MediScribe Rural API.
Run with: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # Patch settings to use a temp ChromaDB dir so tests don't pollute real KB
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["CHROMA_PERSIST_DIR"] = tmpdir
        from backend.main import app
        yield TestClient(app)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "guideline_chunks" in data
    assert isinstance(data["guideline_chunks"], int)


def test_empty_note_rejected(client):
    resp = client.post("/encounter", json={"note": "  "})
    assert resp.status_code == 422


def test_guidelines_endpoint(client):
    resp = client.get("/guidelines")
    assert resp.status_code == 200
    data = resp.json()
    assert "files" in data
    assert "total_chunks" in data


def test_ingest_txt(client, tmp_path):
    txt_file = tmp_path / "test_guideline.txt"
    txt_file.write_text("Patient with fever and cough. Treat with amoxicillin 500mg TDS for 5 days.")
    with open(txt_file, "rb") as f:
        resp = client.post("/ingest", files={"file": ("test_guideline.txt", f, "text/plain")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["chunks_added"] >= 1
    assert data["filename"] == "test_guideline.txt"


def test_ingest_unsupported_type(client, tmp_path):
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("col1,col2\nval1,val2")
    with open(csv_file, "rb") as f:
        resp = client.post("/ingest", files={"file": ("bad.csv", f, "text/csv")})
    assert resp.status_code == 415
