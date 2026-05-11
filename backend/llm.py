"""
Gemma 4 LLM client via Ollama.
Uses Gemma 4's native function-calling to extract structured data
(ICD-10 codes, vitals, medications) alongside free-form SOAP generation.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import ollama
from loguru import logger

from backend.config import settings

# ---------------------------------------------------------------------------
# Tool definitions (Gemma 4 function-calling schema)
# ---------------------------------------------------------------------------

TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "extract_clinical_entities",
            "description": (
                "Extract structured clinical entities from the patient encounter note. "
                "Call this once you have identified diagnoses, medications, vitals, and allergies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "diagnoses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "icd10_code": {"type": "string"},
                                "confidence": {
                                    "type": "string",
                                    "enum": ["high", "medium", "low"],
                                },
                            },
                            "required": ["name", "icd10_code", "confidence"],
                        },
                        "description": "List of diagnoses with ICD-10 codes.",
                    },
                    "medications": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "dose": {"type": "string"},
                                "frequency": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    },
                    "vitals": {
                        "type": "object",
                        "properties": {
                            "bp": {"type": "string"},
                            "hr": {"type": "string"},
                            "temp": {"type": "string"},
                            "rr": {"type": "string"},
                            "spo2": {"type": "string"},
                            "weight": {"type": "string"},
                            "height": {"type": "string"},
                        },
                    },
                    "allergies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["diagnoses"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_clinical_alert",
            "description": (
                "Raise a clinical alert when the encounter note contains "
                "an urgent or critical finding that requires immediate attention."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "urgent", "routine"],
                    },
                    "alert_message": {"type": "string"},
                    "recommended_action": {"type": "string"},
                },
                "required": ["severity", "alert_message", "recommended_action"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_prompt(
    encounter_note: str,
    guideline_context: str,
    language: str = "en",
) -> List[Dict[str, str]]:
    system = (
        "You are MediScribe, an expert clinical documentation assistant deployed "
        "at a rural health clinic with limited connectivity. "
        "You help healthcare workers produce accurate, structured medical records. "
        "Always ground your clinical reasoning in the provided guideline context. "
        "Do not hallucinate medications or diagnoses not supported by the note or guidelines. "
        "Respond in the same language as the encounter note unless instructed otherwise. "
        f"User's preferred language: {language}."
    )

    user_content = f"""## Patient Encounter Note
{encounter_note}

## Relevant Clinical Guidelines
{guideline_context if guideline_context else "No guidelines retrieved — use standard clinical knowledge."}

## Instructions
1. First, call `extract_clinical_entities` to extract diagnoses (with ICD-10 codes), medications, vitals, and allergies.
2. If any critical/urgent finding is present, call `flag_clinical_alert`.
3. Then generate a complete SOAP note in this exact format:

**SOAP NOTE**

**Subjective:**
<chief complaint, history of present illness, review of systems>

**Objective:**
<vitals, physical exam findings, relevant test results>

**Assessment:**
<diagnosis list with ICD-10 codes, clinical reasoning grounded in guidelines>

**Plan:**
<treatment plan, medications with doses, follow-up, patient education>

**Guideline References:**
<cite the specific guideline sections used>
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Main LLM interface
# ---------------------------------------------------------------------------


class GemmaClient:
    def __init__(self) -> None:
        self._client = ollama.Client(host=settings.ollama_host)
        logger.info(f"Gemma client → {settings.ollama_host} | model: {settings.ollama_model}")

    def process_encounter(
        self,
        encounter_note: str,
        guideline_chunks: List[dict],
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Main entry point. Sends encounter note + RAG context to Gemma 4
        and returns a structured result with SOAP note + extracted entities.
        """
        guideline_context = self._format_guidelines(guideline_chunks)
        messages = _build_prompt(encounter_note, guideline_context, language)

        extracted_entities: Dict[str, Any] = {}
        alerts: List[Dict[str, Any]] = []
        soap_note: str = ""

        # --- Agentic loop: allow model to call tools then generate final text ---
        current_messages = list(messages)
        max_rounds = 3

        for round_num in range(max_rounds):
            logger.debug(f"LLM round {round_num + 1}")
            try:
                response = self._client.chat(
                    model=settings.ollama_model,
                    messages=current_messages,
                    tools=TOOLS,
                    options={"temperature": 0.1, "num_predict": 2048},
                )
            except Exception as e:
                logger.error(f"Ollama error: {e}")
                raise

            msg = response.message

            # Process any tool calls
            tool_calls_made = False
            if msg.tool_calls:
                tool_calls_made = True
                current_messages.append(
                    {"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls}
                )
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    fn_args = tc.function.arguments if isinstance(tc.function.arguments, dict) else json.loads(tc.function.arguments)

                    if fn_name == "extract_clinical_entities":
                        extracted_entities = fn_args
                        result = {"status": "ok", "message": "Entities recorded."}
                    elif fn_name == "flag_clinical_alert":
                        alerts.append(fn_args)
                        result = {"status": "ok", "message": "Alert recorded."}
                    else:
                        result = {"status": "error", "message": f"Unknown tool: {fn_name}"}

                    current_messages.append(
                        {"role": "tool", "content": json.dumps(result)}
                    )

            # If model returned actual text content (SOAP note), we're done
            if msg.content and msg.content.strip() and not tool_calls_made:
                soap_note = msg.content.strip()
                break
            elif msg.content and msg.content.strip() and tool_calls_made:
                # Model gave text AND tool calls — capture text if it looks like SOAP
                if "**Subjective" in msg.content or "SOAP" in msg.content:
                    soap_note = msg.content.strip()
                    break

        if not soap_note:
            # Final fallback: ask model to write the SOAP note without tools
            current_messages.append(
                {"role": "user", "content": "Now write the complete SOAP note based on your analysis."}
            )
            try:
                final_resp = self._client.chat(
                    model=settings.ollama_model,
                    messages=current_messages,
                    options={"temperature": 0.1, "num_predict": 2048},
                )
                soap_note = final_resp.message.content or ""
            except Exception as e:
                logger.error(f"Final LLM call failed: {e}")
                soap_note = "Error generating SOAP note."

        return {
            "soap_note": soap_note,
            "extracted_entities": extracted_entities,
            "alerts": alerts,
            "guideline_chunks_used": len(guideline_chunks),
            "model": settings.ollama_model,
        }

    @staticmethod
    def _format_guidelines(chunks: List[dict]) -> str:
        if not chunks:
            return ""
        parts = []
        for i, c in enumerate(chunks, 1):
            parts.append(f"[{i}] ({c['source']}, relevance={c['relevance']})\n{c['text']}")
        return "\n\n".join(parts)

    def health_check(self) -> bool:
        try:
            models = self._client.list()
            available = [m.model for m in models.models]
            if settings.ollama_model not in available:
                logger.warning(
                    f"Model '{settings.ollama_model}' not found. Available: {available}"
                )
                return False
            return True
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
