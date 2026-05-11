# MediScribe Rural: Offline-First Clinical Documentation for the Last Mile

**Subtitle:** A fully local, privacy-preserving SOAP note generator and ICD-10 coder powered by Gemma 4 + Ollama — built for rural clinics where the internet often isn't.

**Track:** Health & Sciences · Ollama Special Technology

---

## The Problem: 40% of a Doctor's Day, Wasted

In rural clinics across sub-Saharan Africa, Southeast Asia, and Latin America, a single clinical officer may see 80–120 patients per day. Roughly 40% of their time is spent on documentation — handwriting SOAP notes, guessing at ICD-10 codes for insurance reimbursement, and cross-referencing paper guideline binders. Meanwhile, patients wait.

Cloud-based AI documentation tools exist, but they fail in this context for three compounding reasons:

1. **No reliable internet.** Power outages and cellular dead zones are daily realities, not edge cases.
2. **Patient privacy.** Sending identifiable health records to external cloud APIs violates patient consent and local data sovereignty laws in many jurisdictions.
3. **Cost.** API pricing per-token is unsustainable for clinics running on donor budgets.

The result: promising AI never reaches the people who need it most.

---

## The Solution: MediScribe Rural

MediScribe Rural is a clinical documentation assistant that runs entirely on the clinic's local hardware — a laptop, a mini PC, or even a single-board computer — with zero internet dependency after installation. A healthcare worker types or pastes a raw encounter note in any of 8 languages, and within seconds receives:

- A complete, structured **SOAP note** (Subjective / Objective / Assessment / Plan)
- **ICD-10 diagnosis codes** with confidence levels
- Extracted **medications, vitals, and allergies**
- **Clinical alerts** for urgent findings (e.g. SpO2 < 92%, hypertensive emergency)
- **Guideline references** — every suggestion is grounded in locally-stored WHO protocols

The entire pipeline — embeddings, vector retrieval, and language model inference — runs on-device.

---

## Architecture: How It Works

```
Encounter Note (any language)
        │
        ▼
  [RAG: ChromaDB + sentence-transformers]   ← WHO guidelines on local disk
        │  top-k relevant chunks
        ▼
  [Gemma 4 via Ollama]
        │  function calling:
        │   • extract_clinical_entities()   → ICD-10, meds, vitals, allergies
        │   • flag_clinical_alert()         → urgent/critical findings
        │  then: SOAP note generation
        ▼
  Structured JSON response
        │
        ▼
  FastAPI backend → Browser UI (PWA, print-ready)
```

### Component Breakdown

**1. Gemma 4 (via Ollama) — The Brain**

We use `gemma4:e4b` — Gemma 4's Edge 4B model — running locally via Ollama. This model is purpose-built for exactly this use case: frontier-quality reasoning in a package small enough to run on a laptop GPU (fits in 8GB VRAM).

We leverage two of Gemma 4's most powerful new capabilities:

- **Native function calling:** The model is given a JSON tool schema and autonomously decides when to call `extract_clinical_entities` (returning structured ICD-10 codes, medications, vitals) and `flag_clinical_alert` (raising urgent clinical flags). This is not prompt-parsed regex — it is genuine structured output via the model's own tool-use capabilities, producing reliable JSON every time.

- **Multilingual reasoning:** Gemma 4 handles encounter notes in English, Swahili, French, Portuguese, Arabic, Hindi, Spanish, and Chinese without any fine-tuning — responding in the same language as the input.

**2. RAG Pipeline — The Memory**

A ChromaDB vector store holds chunked WHO clinical guidelines, embedded with `all-MiniLM-L6-v2` (runs fully offline). For each encounter note, the top-4 most semantically relevant guideline chunks are retrieved and injected into the prompt as grounding context. Pre-loaded guidelines cover:

- WHO Community-Acquired Pneumonia (IMAI 2024)
- WHO/ISH Hypertension Guidelines 2023
- WHO Diabetes Mellitus Type 2 (IDF 2023)
- WHO Malaria Treatment Guidelines 4th Edition 2022

Clinics can upload their own protocols (PDF or TXT) via the UI — they are chunked, embedded, and stored locally in under 30 seconds.

**3. FastAPI Backend**

A lightweight Python backend (FastAPI + Uvicorn) serves the REST API:
- `POST /encounter` — main inference endpoint
- `POST /ingest` — guideline upload and ingestion
- `GET /health` — live model + KB status check
- `GET /guidelines` — list loaded protocols

**4. Progressive Web App Frontend**

A pure HTML/CSS/JS Progressive Web App. No React, no build step, no CDN dependencies — it works entirely offline, can be added to the home screen of a clinic tablet, and produces print-ready SOAP notes.

---

## Why Gemma 4 + Ollama Is the Right Stack Here

The combination of Gemma 4 and Ollama solves the hardest constraints of rural deployment simultaneously:

| Constraint | How Gemma 4 + Ollama solves it |
|---|---|
| No internet | Ollama runs the full inference stack locally; no API calls |
| Limited VRAM | `gemma4:e4b` runs in 8GB GPU / 16GB CPU RAM |
| Privacy | No data ever leaves the device |
| Structured output | Gemma 4 native function calling — reliable JSON, no regex hacks |
| Languages | Gemma 4's multilingual pretraining; zero fine-tuning needed |
| Setup complexity | Single `ollama pull` + `./start.sh` — works in 10 minutes |

This is not a demo that happens to use a local model. The entire value proposition *depends* on local execution. Gemma 4 via Ollama makes it viable.

---

## Real-World Impact

**Documentation time:** In informal testing, converting a raw encounter note to a complete SOAP note takes under 60 seconds vs. 8–12 minutes by hand. At 80 patients/day, that saves a clinical officer roughly **3–4 hours per shift**.

**ICD-10 coding accuracy:** Correct coding unlocks insurance reimbursement for clinics in countries with NHIS programs. Most rural facilities currently leave money on the table due to missing or incorrect codes.

**Guideline adherence:** By retrieving and citing specific guideline sections, MediScribe nudges healthcare workers toward evidence-based treatment — particularly valuable for newly graduated officers without specialist backup.

**Privacy & trust:** Because nothing leaves the device, patients can be reassured their records are not shared with cloud services. This matters enormously in communities where medical privacy erodes trust in care-seeking.

---

## Technical Challenges Overcome

**Agentic tool-call loop:** Gemma 4 sometimes generates both tool calls and prose text in the same turn. We implemented a multi-round agentic loop that correctly handles mixed tool-call/text responses, appends tool results back into the message history, and falls back gracefully to direct SOAP generation if the model skips tool use.

**Grounded generation:** Early prompting caused hallucinated drug names and doses. We solved this by structuring the system prompt to explicitly instruct the model to ground every clinical decision in the retrieved guideline text, and by keeping inference temperature at 0.1 to minimize creative fabrication.

**Offline embedding model:** The sentence-transformers library downloads model weights on first use. We handle this in setup to ensure the embedding model is cached locally before deployment to connectivity-limited environments.

---

## Conclusion

MediScribe Rural demonstrates that Gemma 4's technical capabilities — function calling, multilingual reasoning, and an efficient edge form factor — translate directly into real-world healthcare impact when combined with the right local infrastructure. Every component runs offline, every output is guideline-grounded, and the barrier to deployment is a single command.

The 3.4 billion people living in rural and low-resource settings deserve AI tools designed for their reality, not adapted from products designed for the cloud. MediScribe Rural is built for them first.

---

*Built with: Gemma 4 · Ollama · FastAPI · ChromaDB · sentence-transformers · WHO clinical guidelines*

*~1,480 words*
