# MediScribe Rural

> **Offline-first clinical documentation assistant powered by Gemma 4 + Ollama**

Built for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon) | Health & Sciences + Ollama Special Tech tracks

---

## The Problem

Rural health clinics in LMICs serve millions of patients with:
- No reliable internet connectivity
- Overburdened healthcare workers spending 40%+ of time on documentation
- Inconsistent application of clinical guidelines
- Patient privacy constraints preventing cloud-based AI

## The Solution

MediScribe Rural converts raw encounter notes into structured **SOAP notes** with ICD-10 codes, using a 100% local AI pipeline:

```
Encounter note → RAG (local ChromaDB) → Gemma 4 (Ollama) → SOAP Note + ICD-10 codes
```

**Key features:**
- ✅ Fully offline after initial setup — no data ever leaves the device
- ✅ Gemma 4 native function calling for structured ICD-10 extraction
- ✅ RAG with WHO/local clinical guidelines (upload any PDF/TXT)
- ✅ Multilingual support (8 languages)
- ✅ Clinical alerts for urgent findings
- ✅ Progressive Web App — works on tablets/phones in the clinic
- ✅ Print-ready SOAP notes

## Architecture

```
┌──────────────────────────────────────────────────┐
│                Browser (PWA)                     │
│   - Offline-capable UI                           │
│   - Multilingual note input                      │
│   - SOAP note + entity display                   │
└────────────────────┬─────────────────────────────┘
                     │ HTTP (localhost)
┌────────────────────▼─────────────────────────────┐
│              FastAPI Backend                     │
│   /encounter  → RAG → Gemma 4 → SOAP            │
│   /ingest     → PDF/TXT → ChromaDB              │
│   /health     → system status                   │
└──────────┬────────────────────┬──────────────────┘
           │                    │
┌──────────▼──────┐  ┌──────────▼──────────────────┐
│   ChromaDB      │  │   Ollama (Gemma 4)           │
│   (local disk)  │  │   - Function calling        │
│   WHO guidelines│  │   - SOAP generation         │
│   + custom PDFs │  │   - Clinical alerts         │
└─────────────────┘  └─────────────────────────────┘
```

## Setup

### Prerequisites
- [Ollama](https://ollama.com) installed and running
- Conda (Anaconda/Miniconda)
- 8GB+ RAM, GPU optional but recommended

### 1. Create conda environment

```bash
conda env create -f environment.yml
conda activate mediscribe
```

### 2. Pull Gemma 4 model

```bash
ollama pull gemma4:e4b   # Edge 4B — fits in 8GB VRAM
# or
ollama pull gemma4:27b   # for higher quality (requires 16GB+ VRAM)
```

### 3. Start the application

```bash
chmod +x start.sh
./start.sh
```

Open http://localhost:8000 in your browser.

### 4. Upload clinical guidelines (optional)

Use the "Upload Clinical Guideline" panel in the UI to add PDF/TXT clinical protocols.
Pre-loaded guidelines: WHO CAP, Hypertension, Diabetes T2, Malaria.

## Usage

1. Paste or type an encounter note in the left panel
2. Select language (8 supported)
3. Click **Generate SOAP Note**
4. Review: SOAP note, ICD-10 codes, medications, vitals, clinical alerts
5. Copy or print the note

## Model Configuration

Edit `.env` to change the model:

```env
OLLAMA_MODEL=gemma4:e4b      # default (edge, fast)
# OLLAMA_MODEL=gemma4:27b    # higher quality
```

## Running Tests

```bash
conda activate mediscribe
pytest tests/ -v
```

## Competition Tracks

- **Health & Sciences** ($10K) — directly addresses rural healthcare documentation
- **Ollama Special Tech** ($10K) — showcases Gemma 4 running locally via Ollama
- **Main Track** — real-world impact + technical depth

## License

CC-BY 4.0
