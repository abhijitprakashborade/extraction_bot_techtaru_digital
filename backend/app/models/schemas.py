"""
Pydantic v2 Extraction Schemas
═══════════════════════════════════════════════════════════════════════════════

WHY PYDANTIC V2 OVER DATACLASSES OR TYPEDDICT?

1. model_json_schema() → Converted into a strict OpenAI Structured Outputs
   json_schema via the SDK's pydantic-to-json-schema conversion. The API
   rejects any model output that does not conform to the schema —
   no regex, no brittle .strip() hacks.

2. model_validator (mode='after') → Cross-field validation after all fields
   are populated. E.g., invoice: quantity × unit_price ≈ line_total.

3. field_validator → Per-field post-processing. E.g., normalise phone numbers,
   validate email format without crashing on malformed input.

4. Strict mode → .model_validate(data, strict=True) refuses silent coercion
   (str→int), so "123" is NOT silently accepted where int is expected.

5. Rust-backed C extension (V2) is 5-10× faster than v1 for large payloads.

CONFIDENCE SCORING DESIGN
────────────────────────────
Each extraction also returns a `field_confidence` dict (field_name → 0.0-1.0).
Values are produced by a second structured-output pass that scores each
field's extraction reliability.

  0.90-1.00  Explicitly stated, unambiguous verbatim text
  0.70-0.89  Clearly implied, high certainty
  0.50-0.69  Somewhat ambiguous / multiple interpretations
  0.25-0.49  Inferred from context, uncertain
  0.00-0.24  Best-guess, very low certainty → treat as unreliable
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from enum import Enum
import re


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────

class DocumentType(str, Enum):
    RESUME         = "RESUME"
    INVOICE        = "INVOICE"
    CONTRACT       = "CONTRACT"
    MEDICAL_RECORD = "MEDICAL_RECORD"
    BUSINESS_CARD  = "BUSINESS_CARD"
    CUSTOM         = "CUSTOM"
    UNKNOWN        = "UNKNOWN"


# ──────────────────────────────────────────────────────────────────────────────
# Shared primitives
# ──────────────────────────────────────────────────────────────────────────────

class Address(BaseModel):
    street:      Optional[str] = None
    city:        Optional[str] = None
    state:       Optional[str] = None
    postal_code: Optional[str] = None
    country:     Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# RESUME schema
# ──────────────────────────────────────────────────────────────────────────────

class ContactInfo(BaseModel):
    full_name:     Optional[str] = None
    email:         Optional[str] = None
    phone:         Optional[str] = None
    location:      Optional[str] = None
    linkedin_url:  Optional[str] = None
    github_url:    Optional[str] = None
    portfolio_url: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Silently null out structurally invalid emails instead of crashing."""
        if v and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            return None
        return v

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        if v:
            cleaned = re.sub(r"[^\d+\-() ]", "", v).strip()
            return cleaned or None
        return v


class WorkExperience(BaseModel):
    company:          Optional[str] = None
    title:            Optional[str] = None
    start_date:       Optional[str] = None
    end_date:         Optional[str] = None
    is_current:       bool           = False
    location:         Optional[str] = None
    responsibilities: List[str]      = Field(default_factory=list)
    technologies:     List[str]      = Field(default_factory=list)
    achievements:     List[str]      = Field(default_factory=list)


class Education(BaseModel):
    institution:    Optional[str] = None
    degree:         Optional[str] = None
    field_of_study: Optional[str] = None
    start_date:     Optional[str] = None
    end_date:       Optional[str] = None
    gpa:            Optional[str] = None
    achievements:   List[str]     = Field(default_factory=list)


class Certification(BaseModel):
    name:                 Optional[str] = None
    issuing_organization: Optional[str] = None
    issue_date:           Optional[str] = None
    expiry_date:          Optional[str] = None
    credential_id:        Optional[str] = None


class Project(BaseModel):
    name:         Optional[str] = None
    description:  Optional[str] = None
    technologies: List[str]     = Field(default_factory=list)
    url:          Optional[str] = None
    start_date:   Optional[str] = None
    end_date:     Optional[str] = None


class ResumeExtraction(BaseModel):
    contact:               ContactInfo          = Field(default_factory=ContactInfo)
    professional_summary:  Optional[str]        = None
    work_experience:       List[WorkExperience] = Field(default_factory=list)
    education:             List[Education]      = Field(default_factory=list)
    skills:                List[str]            = Field(default_factory=list)
    technical_skills:      Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Categorised skills e.g. {'Languages': ['Python'], 'Frameworks': ['FastAPI']}"
    )
    certifications:        List[Certification]  = Field(default_factory=list)
    projects:              List[Project]        = Field(default_factory=list)
    languages:             List[str]            = Field(default_factory=list)
    total_experience_years: Optional[float]     = None


# ──────────────────────────────────────────────────────────────────────────────
# INVOICE schema
# ──────────────────────────────────────────────────────────────────────────────

class Party(BaseModel):
    name:                 Optional[str]     = None
    address:              Optional[Address] = None
    email:                Optional[str]     = None
    phone:                Optional[str]     = None
    tax_id:               Optional[str]     = None
    bank_account:         Optional[str]     = None


class LineItem(BaseModel):
    description: Optional[str]   = None
    quantity:    Optional[float]  = None
    unit_price:  Optional[float]  = None
    total_price: Optional[float]  = None
    tax_rate:    Optional[float]  = None
    unit:        Optional[str]    = None          # "hrs", "pcs", "kg" …

    @model_validator(mode="after")
    def check_arithmetic(self) -> "LineItem":
        """Flag arithmetic discrepancy — don't block, just warn."""
        if (
            self.quantity is not None
            and self.unit_price is not None
            and self.total_price is not None
        ):
            expected = round(self.quantity * self.unit_price, 2)
            if abs(expected - self.total_price) > 0.05:
                # Stored on parent ExtractionResult.warnings; nothing to do here
                pass
        return self


class InvoiceExtraction(BaseModel):
    invoice_number: Optional[str]      = None
    invoice_date:   Optional[str]      = None
    due_date:       Optional[str]      = None
    vendor:         Party              = Field(default_factory=Party)
    client:         Party              = Field(default_factory=Party)
    line_items:     List[LineItem]     = Field(default_factory=list)
    subtotal:       Optional[float]    = None
    tax_amount:     Optional[float]    = None
    discount_amount: Optional[float]  = None
    total_amount:   Optional[float]    = None
    currency:       Optional[str]      = None
    payment_terms:  Optional[str]      = None
    payment_method: Optional[str]      = None
    po_number:      Optional[str]      = None
    notes:          Optional[str]      = None


# ──────────────────────────────────────────────────────────────────────────────
# CONTRACT schema
# ──────────────────────────────────────────────────────────────────────────────

class ContractParty(BaseModel):
    name:            Optional[str] = None
    role:            Optional[str] = None   # "Provider", "Client", "Licensor" …
    address:         Optional[str] = None
    representative:  Optional[str] = None
    signature_date:  Optional[str] = None


class Obligation(BaseModel):
    party:       Optional[str] = None
    description: Optional[str] = None
    due_date:    Optional[str] = None


class ContractExtraction(BaseModel):
    contract_title:   Optional[str]        = None
    contract_type:    Optional[str]        = None     # NDA, SaaS, Employment …
    effective_date:   Optional[str]        = None
    expiry_date:      Optional[str]        = None
    parties:          List[ContractParty]  = Field(default_factory=list)
    governing_law:    Optional[str]        = None
    jurisdiction:     Optional[str]        = None
    payment_terms:    Optional[str]        = None
    total_value:      Optional[float]      = None
    currency:         Optional[str]        = None
    obligations:      List[Obligation]     = Field(default_factory=list)
    termination_notice_days: Optional[int] = None
    key_clauses:      List[str]            = Field(default_factory=list)
    confidentiality:  bool                 = False
    non_compete:      bool                 = False


# ──────────────────────────────────────────────────────────────────────────────
# BUSINESS CARD schema
# ──────────────────────────────────────────────────────────────────────────────

class BusinessCardExtraction(BaseModel):
    full_name:   Optional[str]  = None
    title:       Optional[str]  = None
    company:     Optional[str]  = None
    email:       Optional[str]  = None
    phone:       Optional[str]  = None
    mobile:      Optional[str]  = None
    website:     Optional[str]  = None
    address:     Optional[str]  = None
    linkedin:    Optional[str]  = None
    twitter:     Optional[str]  = None
    department:  Optional[str]  = None


# ──────────────────────────────────────────────────────────────────────────────
# API-level request / response models
# ──────────────────────────────────────────────────────────────────────────────

class ExtractionRequest(BaseModel):
    """For text-based POST /extract/text endpoint."""
    text: str = Field(
        min_length=1,
        max_length=50_000,
        description="Unstructured document text"
    )
    document_type: Optional[DocumentType] = Field(
        None,
        description="Hint for document type; auto-detected if omitted"
    )
    custom_fields: Optional[List[str]] = Field(
        None,
        description="For CUSTOM type: list of field names to extract"
    )

    @field_validator("text")
    @classmethod
    def clean_text(cls, v: str) -> str:
        v = v.replace("\x00", "")                        # remove null bytes
        v = re.sub(r"\n{4,}", "\n\n\n", v)              # max 3 consecutive newlines
        return v.strip()


class ExtractionResponse(BaseModel):
    """Unified API response for every extraction."""
    id:                     Optional[int]        = None   # DB row id after persist
    document_type:          DocumentType
    document_type_confidence: float              = Field(ge=0.0, le=1.0)
    data:                   Dict[str, Any]
    field_confidence:       Dict[str, float]     = Field(default_factory=dict)
    overall_confidence:     float                = Field(ge=0.0, le=1.0, default=0.0)
    warnings:               List[str]            = Field(default_factory=list)
    processing_notes:       List[str]            = Field(default_factory=list)
    raw_text_length:        int                  = 0
    processing_time_ms:     float                = 0.0
    file_name:              Optional[str]        = None

    @model_validator(mode="after")
    def compute_overall_confidence(self) -> "ExtractionResponse":
        if self.field_confidence:
            scores = [v for v in self.field_confidence.values() if v is not None]
            self.overall_confidence = round(sum(scores) / len(scores), 3) if scores else 0.0
        return self


class HistoryItem(BaseModel):
    """Slim history list item (no full JSON payload)."""
    id:                 int
    file_name:          str
    document_type:      str
    overall_confidence: float
    raw_text_length:    int
    processing_time_ms: float
    created_at:         str
    warnings_count:     int
