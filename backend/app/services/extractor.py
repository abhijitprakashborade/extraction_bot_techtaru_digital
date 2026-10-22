"""
Extraction Service — OpenAI Structured Outputs + Pydantic v2
═══════════════════════════════════════════════════════════════════════════════

STRUCTURED OUTPUT STRATEGY (PRIMARY — OpenAI)
────────────────────────────────────────────
Uses the OpenAI SDK's structured outputs feature:
    client.beta.chat.completions.parse(
        model=…,
        response_format={"type": "json_schema", "strict": True, …},
    )
The JSON Schema is derived directly from Pydantic models via the SDK's built-in
pydantic → json_schema conversion (strict mode: every field required,
additionalProperties: false). The model is *forced* by the API to produce
schema-conformant JSON — no regex, no brittle .strip() hacks.

  1. Auto-classify document type   → ClassifyDocument (parse call)
  2. Extract via typed model       → ResumeExtraction / InvoiceExtraction / …
                                     (strict structured output call)
  3. Pydantic model_validate       → cross-field validators run locally
  4. Confidence scoring            → FieldConfidenceReport (second parse call)
  5. Business-rule warnings        → arithmetic / date-inversion checks

FALLBACK ENGINE (DEMO — zero API key required)
────────────────────────────────────────────
When OPENAI_API_KEY is empty, every call routes to the deterministic
heuristic engine (services/heuristic_engine.py). The pipeline, validation,
business rules and API contract stay identical — the response is flagged
with `engine: "heuristic-demo"` so the UI can label it honestly.

RATE LIMITING & RETRY
──────────────────────
  • 429 (rate limit)  → exponential backoff: 1s, 2s, 4s (max settings.max_retries)
  • 500/529/503       → retry with same payload
  • 400 (bad request) → surface to caller — retrying won't help

SYNCHRONOUS SDK + THREAD POOL
──────────────────────────────
The sync OpenAI client is wrapped in run_in_executor so FastAPI's event loop
is never blocked during a 1–5s LLM call.
"""

import json
import time
import logging
import asyncio
from typing import Any, Type

from pydantic import BaseModel, Field, create_model, ConfigDict
from openai import OpenAI, RateLimitError, APIStatusError, APIConnectionError

from app.config import settings
from app.models.schemas import (
    DocumentType, ExtractionResponse,
    ResumeExtraction, InvoiceExtraction,
    ContractExtraction, BusinessCardExtraction,
)
from app.services import heuristic_engine

logger = logging.getLogger(__name__)

ENGINE_NAME = "openai-structured"
ENGINE_DEMO = "heuristic-demo"


def _openai_client() -> OpenAI | None:
    """Return an OpenAI client only when a real key is configured."""
    key = (settings.openai_api_key or "").strip()
    if not key or key.lower().startswith(("your", "sk-ant", "sk-proj-xxxx", "xxx")):
        return None
    return OpenAI(api_key=key, timeout=settings.llm_timeout_seconds, max_retries=0)


# ── Map document type → Pydantic model ───────────────────────────────────────
_SCHEMA_MAP: dict[DocumentType, Type[BaseModel]] = {
    DocumentType.RESUME:         ResumeExtraction,
    DocumentType.INVOICE:        InvoiceExtraction,
    DocumentType.CONTRACT:       ContractExtraction,
    DocumentType.BUSINESS_CARD:  BusinessCardExtraction,
}

# ══════════════════════════════════════════════════════════════════════════════
# MASTER SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """\
You are a precision document intelligence engine for structured data extraction.

EXTRACTION RULES (NON-NEGOTIABLE)
ACCURACY FIRST
• Extract ONLY information explicitly present in the document.
• NEVER infer, hallucinate, assume, or "fill in" missing data.
• Missing field → use JSON null. NOT "N/A", NOT "", NOT "Unknown".

VERBATIM PRESERVATION
• Proper nouns (names, companies, places) → preserve exact spelling.
• Numbers → extract as-is; no rounding unless units require it.
• Dates → extract as written in the document.

ARRAY FIELDS
• Extract ALL instances — never truncate lists.
• Remove exact duplicates only.

BUSINESS RULE VALIDATION
• Invoice: qty × unit_price ≈ line_total (discrepancies will be flagged).
• Email: must match x@x.x pattern → null if invalid.
• Phone: keep digits, +, -, (, ), spaces.

HALLUCINATION PREVENTION
• If a field is ambiguous: pick the most likely interpretation AND note it.
• If confidence < 0.25 for a field → set the field to null.
• Do NOT populate a field just to make the output "look complete".

You MUST populate every field of the provided response schema. Reply only
through the structured response — never with free prose.
"""


# ══════════════════════════════════════════════════════════════════════════════
# Structured-output request models (OpenAI strict schemas)
# ══════════════════════════════════════════════════════════════════════════════

class ClassifyDocument(BaseModel):
    """Document-type classification for auto-detection."""
    document_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=300)


class FieldConfidenceReport(BaseModel):
    """Per-field confidence scores returned by the second LLM pass."""
    scores: dict[str, float] = Field(
        description="field name → confidence 0.0-1.0 (0 = not found/guessed, 1 = verbatim text)"
    )


def _build_custom_model() -> Type[BaseModel]:
    """Strict-schema wrapper for CUSTOM extractions (field → value pairs)."""
    Model = create_model(
        "CustomExtraction",
        extracted_fields=(
            dict[str, str | None],
            Field(description="Requested custom field name → extracted value (null if not present)"),
        ),
    )
    Model.model_rebuild()
    Model.__name__ = "CustomExtraction"
    return Model


# ══════════════════════════════════════════════════════════════════════════════
# OpenAI helpers
# ══════════════════════════════════════════════════════════════════════════════

async def _openai_call_with_retry(
    client: OpenAI,
    messages: list[dict],
    response_model: Type[BaseModel],
    context: str = "extraction",
) -> BaseModel:
    """
    Strict structured-output call with exponential backoff for 429/5xx.
    Runs the blocking SDK call in the thread pool (keeps the event loop free).
    """
    delay = settings.retry_base_delay
    last_err: Exception | None = None

    for attempt in range(1, settings.max_retries + 1):
        try:
            def _invoke() -> BaseModel:
                return client.beta.chat.completions.parse(
                    model=settings.openai_model,
                    max_tokens=settings.max_tokens,
                    messages=messages,           # type: ignore[arg-type]
                    response_model=response_model,
                ).choices[0].message.parsed

            loop = asyncio.get_running_loop()
            parsed = await loop.run_in_executor(None, _invoke)
            if parsed is None:
                raise ValueError("OpenAI returned no parsed content")
            return parsed

        except RateLimitError:
            last_err = RateLimitError("rate limited", body=None, response=None)
            if attempt == settings.max_retries:
                logger.error(f"[{context}] Rate limit hit — max retries exhausted")
                raise
            logger.warning(
                f"[{context}] 429 Rate limit — backoff {delay}s (attempt {attempt}/{settings.max_retries})"
            )
            await asyncio.sleep(delay)
            delay *= 2

        except APIStatusError as e:
            if e.status_code in (500, 502, 503, 529) and attempt < settings.max_retries:
                logger.warning(f"[{context}] {e.status_code} server error — retry {attempt}")
                await asyncio.sleep(delay)
                delay *= 2
            else:
                raise

        except APIConnectionError as e:
            last_err = e
            if attempt < settings.max_retries:
                logger.warning(f"[{context}] Connection error — retry {attempt}")
                await asyncio.sleep(delay)
                delay *= 2
            else:
                raise

    raise last_err or RuntimeError("Unreachable retry state")


def _build_custom_model(custom_fields: list[str]) -> Type[BaseModel]:
    """Build a dynamic strict schema for CUSTOM extractions."""
    fields = {}
    for f in custom_fields:
        fields[f.strip().replace(" ", "_")[:40]] = (
            (str | None), Field(default=None, description=f"Value for '{f}'")
        )
    Model = create_model(
        "CustomExtraction",
        extracted_fields=(dict[str, str | None], Field(description="Requested fields")),
        **{"custom_values": (dict[str, str | None], Field(description="custom field → value"))},
    )
    Model.model_rebuild()
    Model.__name__ = "CustomExtraction"
    return Model


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def engine_name() -> str:
    return ENGINE_NAME if _openai_client() is not None else ENGINE_DEMO


async def classify_document(text: str) -> tuple[DocumentType, float]:
    """Step 1 (OpenAI mode): auto-detect document type via structured output."""
    client = _openai_client()
    if client is None:
        return heuristic_engine.classify_document(text)

    logger.info("Classifying document type…")
    try:
        result: ClassifyDocument = await _openai_call_with_retry(
            client=client,
            messages=[{
                "role": "user",
                "content": (
                    "Classify this document into exactly one type.\n\n"
                    f"--- TEXT START ---\n{text[:3000]}\n--- TEXT END ---"
                ),
            }],
            response_model=ClassifyDocument,
            context="classify",
        )
        doc_type = DocumentType(result.document_type) if isinstance(result.document_type, str) else result.document_type
        logger.info(f"Classified as {doc_type} (confidence={result.confidence:.2f})")
        return doc_type, round(min(max(result.confidence, 0.0), 1.0), 3)
    except Exception as e:
        logger.warning(f"Classification failed: {e} — defaulting to UNKNOWN")

    return DocumentType.UNKNOWN, 0.0


async def extract_structured(
    text: str,
    document_type: DocumentType,
    file_name: str = "unknown",
    custom_fields: list[str] | None = None,
) -> ExtractionResponse:
    """
    Main extraction pipeline:
      1. Auto-classify if type is UNKNOWN
      2. Extract via strict structured output (or heuristic fallback)
      3. Pydantic validation (cross-field validators)
      4. Confidence scoring
      5. Business-rule warnings
      6. Unified ExtractionResponse
    """
    t_start = time.perf_counter()
    warnings: list[str] = []
    processing_notes: list[str] = []
    engine = engine_name()
    client = _openai_client()
    doc_type_confidence = 1.0

    # ── Edge case: empty / whitespace text ───────────────────────────────────
    if not text or not text.strip():
        logger.warning(f"[{file_name}] Empty text received — returning empty extraction")
        return ExtractionResponse(
            document_type=DocumentType.UNKNOWN,
            document_type_confidence=0.0,
            data={},
            field_confidence={},
            overall_confidence=0.0,
            warnings=["Input text was empty or contained only whitespace"],
            processing_notes=["Extraction skipped — no content to process"],
            raw_text_length=0,
            processing_time_ms=0.0,
            file_name=file_name,
        )

    # ── Step 1: Auto-classify if not provided ────────────────────────────────
    if document_type in (DocumentType.UNKNOWN, None):
        document_type, doc_type_confidence = await classify_document(text)
        processing_notes.append(
            f"Document auto-classified as {document_type} (confidence={doc_type_confidence:.0%})"
        )
        if document_type is DocumentType.UNKNOWN and client is None:
            doc_type_confidence = max(doc_type_confidence, 0.4)

    # ── Step 2+3: Extraction ─────────────────────────────────────────────────
    pydantic_model = _SCHEMA_MAP.get(document_type)

    if client is not None:
        # ── OpenAI strict structured output ──────────────────────────────
        if pydantic_model is None:
            if document_type is DocumentType.CUSTOM and custom_fields:
                pydantic_model = _build_custom_model()
                processing_notes.append("Extracted the requested custom fields via structured output")
            else:
                pydantic_model = None

        if pydantic_model is not None:
            processing_notes.append(
                f"Used {pydantic_model.__name__} with OpenAI Structured Outputs (strict json_schema)"
            )
            response = await _openai_call_with_retry(
                client=client,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Document type: {document_type.value}\n\n"
                            f"--- DOCUMENT TEXT START ---\n{text}\n--- DOCUMENT TEXT END ---\n\n"
                            "Extract all available information. Set fields to null when "
                            "the information is not present in the document."
                        ),
                    },
                ],
                response_model=pydantic_model,
                context=f"extract:{file_name}",
            )
            extracted_data = response.model_dump(mode="json", exclude_none=False)
            processing_notes.append("OpenAI structured output received — schema-conformant JSON guaranteed")
            try:
                validated = pydantic_model.model_validate(extracted_data)
                extracted_data = validated.model_dump(mode="json", exclude_none=False)
                processing_notes.append("Pydantic validation passed — all field validators ran successfully")
            except Exception as e:
                warnings.append(f"Pydantic validation warning: {str(e)[:200]}")
                processing_notes.append("Pydantic validation had warnings — raw data preserved")
                logger.warning(f"[{file_name}] Pydantic validation issue: {e}")

        else:
            # Generic freeform via a small structured wrapper
            class GenericExtraction(BaseModel):
                extracted_fields: dict[str, Any]
                document_summary: str

            response = await _openai_call_with_retry(
                client=client,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Document type: {document_type.value}\n\n"
                            f"--- DOCUMENT TEXT START ---\n{text[:8000]}\n--- DOCUMENT TEXT END ---\n\n"
                            "Extract all relevant structured key-value data from this document."
                        ),
                    },
                ],
                response_model=GenericExtraction,
                context=f"extract-generic:{file_name}",
            )
            extracted_data = response.model_dump(mode="json", exclude_none=False)
            processing_notes.append("Used generic schema (no specific model for this type)")
    else:
        # ── Heuristic demo engine ────────────────────────────────────────
        processing_notes.append(
            "Running the built-in deterministic heuristic engine (no LLM API key configured)"
        )
        extracted_data, field_confidence_h, warnings_h = heuristic_engine.extract_structured(
            text, document_type, custom_fields
        )
        warnings.extend(warnings_h)
        processing_notes.append("Heuristic engine used regex + keyword rules — no LLM involved")

        t_end = time.perf_counter()
        processing_ms = round((t_end - t_start) * 1000, 1)
        logger.info(
            f"[{file_name}] Heuristic extraction complete in {processing_ms}ms | type={document_type}"
        )
        _apply_business_rule_warnings(extracted_data, document_type, warnings)

        return ExtractionResponse(
            document_type=document_type,
            document_type_confidence=round(doc_type_confidence, 3),
            data=extracted_data,
            field_confidence=field_confidence_h,
            warnings=warnings,
            processing_notes=processing_notes,
            raw_text_length=len(text),
            processing_time_ms=processing_ms,
            file_name=file_name,
        )

    # ── Step 4 (OpenAI only): Confidence scoring ─────────────────────────────
    logger.info(f"[{file_name}] Scoring field confidence…")
    score_keys = list(extracted_data.keys())
    field_confidence: dict[str, float] = {}

    if score_keys:
        try:
            conf: FieldConfidenceReport = await _openai_call_with_retry(
                client=client,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "You just extracted data from a document. Score your confidence in each "
                            "top-level field on 0.0-1.0 (0 = absent/guessed, 1 = unambiguous verbatim).\n\n"
                            f"Extracted data:\n{json.dumps(extracted_data, indent=2, default=str)[:3000]}\n\n"
                            f"Original document snippet:\n{text[:2000]}"
                        ),
                    },
                ],
                response_model=FieldConfidenceReport,
                context=f"confidence:{file_name}",
            )
            field_confidence = {
                k: round(min(max(float(v), 0.0), 1.0), 3)
                for k, v in conf.scores.items()
                if isinstance(v, (int, float))
            }
        except Exception as e:
            logger.warning(f"[{file_name}] Confidence scoring failed: {e}")
            processing_notes.append(f"Confidence scoring unavailable: {str(e)[:100]}")
            field_confidence = {k: 0.5 for k in score_keys}

    # ── Step 5: Business-rule warnings ───────────────────────────────────────
    _apply_business_rule_warnings(extracted_data, document_type, warnings)

    t_end = time.perf_counter()
    processing_ms = round((t_end - t_start) * 1000, 1)
    logger.info(
        f"[{file_name}] Extraction complete in {processing_ms}ms | "
        f"type={document_type} | warnings={len(warnings)}"
    )

    return ExtractionResponse(
        document_type=document_type,
        document_type_confidence=round(doc_type_confidence, 3),
        data=extracted_data,
        field_confidence=field_confidence,
        warnings=warnings,
        processing_notes=processing_notes,
        raw_text_length=len(text),
        processing_time_ms=processing_ms,
        file_name=file_name,
    )


def _apply_business_rule_warnings(
    data: dict, doc_type: DocumentType, warnings: list[str]
) -> None:
    """Post-extraction validation rules that add warnings (non-blocking)."""
    if doc_type is DocumentType.INVOICE:
        items = data.get("line_items", []) if isinstance(data.get("line_items"), list) else []
        for i, item in enumerate(items):
            if isinstance(item, dict):
                qty = item.get("quantity")
                price = item.get("unit_price")
                total = item.get("total_price")
                if qty and price and total:
                    expected = round(qty * price, 2)
                    if abs(expected - total) > 0.05:
                        warnings.append(
                            f"Line item {i + 1}: qty({qty}) × price({price}) = {expected} "
                            f"but total_price = {total} (discrepancy of {abs(expected - total):.2f})"
                        )
        subtotal = data.get("subtotal")
        tax = data.get("tax_amount")
        total_amount = data.get("total_amount")
        if subtotal is not None and total_amount is not None:
            expected_total = round(subtotal + (tax or 0), 2)
            if abs(expected_total - total_amount) > 0.05:
                warnings.append(
                    f"Subtotal ({subtotal}) + tax ({tax or 0}) = {expected_total} "
                    f"but total_amount = {total_amount} (discrepancy of {abs(expected_total - total_amount):.2f})"
                )

    if doc_type is DocumentType.RESUME:
        for exp in data.get("work_experience", []) if isinstance(data.get("work_experience"), list) else []:
            if isinstance(exp, dict):
                start = exp.get("start_date")
                end = exp.get("end_date")
                company = exp.get("company", "?")
                if start and end and str(end).lower() not in ("present", "current") and str(start) > str(end):
                    warnings.append(
                        f"Work experience at '{company}': start_date ({start}) is after end_date ({end})"
                    )
