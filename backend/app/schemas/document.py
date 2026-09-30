"""Pydantic schemas for document analysis API.

Defines request/response schemas for document upload, parsing, and analysis.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class FileCategory(StrEnum):
    """Source file category for analysis routing."""

    CODE = "code"
    DOCUMENTATION = "documentation"
    UML = "uml"
    GUI = "gui"


class DocumentFormat(StrEnum):
    """Documentation file formats."""

    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "md"
    HTML = "html"
    TXT = "txt"


# --- Request Schemas ---


class DocumentUploadRequest(BaseModel):
    """Request schema for document upload."""

    file_category: FileCategory = Field(
        default=FileCategory.DOCUMENTATION,
        description="Category of the uploaded file",
    )


# --- Response Schemas ---


class DocumentSectionSchema(BaseModel):
    """Schema for document section."""

    section_id: str = Field(..., description="Unique section identifier")
    title: str = Field(..., description="Section title")
    level: int = Field(..., ge=1, le=6, description="Header level (1-6)")
    content: str = Field(..., description="Section content")
    parent_section_id: str | None = Field(None, description="Parent section ID if nested")
    page_number: int | None = Field(None, description="Page number in source document")

    class Config:
        from_attributes = True


class TableDataSchema(BaseModel):
    """Schema for table extracted from document."""

    table_id: str = Field(..., description="Unique table identifier")
    headers: list[str] = Field(default_factory=list, description="Table headers")
    rows: list[list[str]] = Field(default_factory=list, description="Table rows")
    source_section_id: str = Field(..., description="Source section ID")

    class Config:
        from_attributes = True


class ParsedDocumentSchema(BaseModel):
    """Schema for parsed document result."""

    filename: str = Field(..., description="Original filename")
    format: DocumentFormat = Field(..., description="Document format")
    raw_text: str = Field(..., description="Extracted raw text")
    sections: list[DocumentSectionSchema] = Field(default_factory=list, description="Document sections")
    tables: list[TableDataSchema] = Field(default_factory=list, description="Extracted tables")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Parsing metadata")

    class Config:
        from_attributes = True


class DocumentParseResultSchema(BaseModel):
    """Schema for document parsing operation result."""

    source_file_id: UUID = Field(..., description="Source file ID")
    parsed_document: ParsedDocumentSchema = Field(..., description="Parsed document data")
    analysis_id: UUID | None = Field(None, description="Analysis result ID if available")


class SourceFileSchema(BaseModel):
    """Schema for source file metadata."""

    id: UUID
    project_id: UUID
    filename: str
    file_size: int
    file_category: FileCategory
    doc_format: DocumentFormat | None
    page_count: int | None
    created_at: datetime
    is_cleaned_up: bool = False

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """Response schema for document upload."""

    message: str = Field(..., description="Success message")
    source_file: SourceFileSchema
    parse_status: str = Field(..., description="Parsing status")


# --- Analysis Result Schemas ---


class ClassificationResultSchema(BaseModel):
    """Schema for document classification result."""

    doc_type: str = Field(..., description="Document type")
    confidence: float = Field(..., ge=0, le=100, description="Confidence score")
    source: str = Field(..., description="Classification source (native/llm/hybrid)")
    reasoning: str | None = Field(None, description="Classification reasoning")


class ExtractedRequirementSchema(BaseModel):
    """Schema for extracted requirement."""

    req_id: str
    text: str
    type: str  # 'functional' or 'non-functional'
    priority: str | None  # 'critical', 'high', 'medium', 'low'
    source_section_id: str
    confidence: float
    extraction_method: str  # 'native', 'llm', 'hybrid_merged'


class InconsistencySchema(BaseModel):
    """Schema for detected inconsistency."""

    inconsistency_id: str
    type: str  # 'contradiction', 'terminology', 'missing_reference', 'duplicate'
    severity: str  # 'critical', 'high', 'medium', 'low'
    description: str
    affected_requirements: list[str]
    suggestion: str | None


class GapAnalysisResultSchema(BaseModel):
    """Schema for gap analysis (doc vs code) result."""

    requirement_id: str
    requirement_text: str
    status: str  # 'implemented', 'not_implemented', 'partial', 'divergent'
    mapped_entities: list[str]  # Functions/classes in code
    issue_description: str | None


class TraceabilityMatrixSchema(BaseModel):
    """Schema for traceability matrix entry."""

    requirement_id: str
    requirement_text: str
    code_entities: list[str]
    test_cases: list[str]
    coverage_status: str  # 'full', 'partial', 'none'


# --- Preprocessing Result Schemas (Story 2.2) ---


class SectionStructure(BaseModel):
    """Hierarchical section structure for preprocessing output."""

    section_id: str = Field(..., description="Unique section identifier")
    title: str = Field(..., description="Section title")
    level: int = Field(..., ge=0, le=6, description="Header level (0=unclassified paragraph, 1-6=H1-H6)")
    content: str = Field(..., description="Cleaned section content")
    parent_section_id: str | None = Field(None, description="Parent section ID if nested")
    page_number: int | None = Field(None, description="Page number in source document")
    position: int = Field(0, description="Order of appearance in the document (pre-order traversal)")
    section_type: str = Field(
        "unclassified",
        description="Section classification (functional/non_functional/instruction/unclassified)",
    )
    children: list["SectionStructure"] = Field(default_factory=list, description="Child sections")

    model_config = {"from_attributes": True}


# Enable forward reference for self-referencing model
SectionStructure.model_rebuild()


class SectionResponse(BaseModel):
    """API response for a single document section (tree node).

    Exposed by ``GET /documents/{document_id}/sections``. ``children`` is
    populated when the section is returned as part of a reconstructed tree.
    """

    section_id: str = Field(..., description="Unique section identifier")
    title: str = Field(..., description="Section title")
    level: int = Field(..., description="Header level (0=unclassified, 1-6=H1-H6)")
    content: str = Field("", description="Section content")
    page_number: int | None = Field(None, description="Page number in source document")
    position: int = Field(0, description="Order of appearance in the document")
    section_type: str = Field("unclassified", description="Section classification")
    parent_section_id: str | None = Field(None, description="Parent section ID if nested")
    children: list["SectionResponse"] = Field(default_factory=list, description="Child sections (tree)")

    model_config = {"from_attributes": True}


# Enable forward reference for self-referencing response model
SectionResponse.model_rebuild()


class TableData(BaseModel):
    """Table data extracted from document during preprocessing."""

    table_id: str = Field(..., description="Unique table identifier")
    headers: list[str] = Field(default_factory=list, description="Table column headers")
    rows: list[list[str]] = Field(default_factory=list, description="Table data rows")
    source_section_id: str | None = Field(None, description="Section ID where table was found")

    model_config = {"from_attributes": True}


class DocumentStructure(BaseModel):
    """Complete document structure after preprocessing."""

    sections: list[SectionStructure] = Field(default_factory=list, description="Hierarchical document sections")
    tables: list[TableData] = Field(default_factory=list, description="All extracted tables")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Preprocessing metadata (processing_time, artifact_count, etc.)",
    )

    model_config = {"from_attributes": True}


class PreprocessingResultSchema(BaseModel):
    """Schema for preprocessing operation result."""

    source_file_id: UUID = Field(..., description="Source file ID")
    document_structure: DocumentStructure = Field(..., description="Processed document")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    artifact_count: int = Field(default=0, description="Number of artifacts removed during cleaning")
    polish_char_issues_fixed: int = Field(default=0, description="Number of Polish character fixes applied")


# --- Classification Result Schemas (Story 2.3) ---


class DocumentType(StrEnum):
    """Document types for classification."""

    SPECIFIKACJA_WYMAGAN = "specyfikacja_wymagań"
    PODRECZNIK_UZYTKOWNIKA = "podręcznik_użytkownika"
    INSTRUKCJA_TECHNICZNA = "instrukcja_techniczna"
    OPIS_API = "opis_api"
    NOTATKI_PROJEKTOWE = "notatki_projektowe"
    INNY = "inny"


class ClassificationSource(StrEnum):
    """Classification method source."""

    NATIVE = "native"
    LLM = "llm"
    HYBRID_MERGED = "hybrid_merged"


class ClassificationResult(BaseModel):
    """Result of document classification."""

    doc_type: DocumentType = Field(..., description="Classified document type")
    confidence: float = Field(..., ge=0, le=100, description="Confidence score (0-100)")
    source: ClassificationSource = Field(..., description="Classification method source")
    reasoning: str | None = Field(None, description="Explanation of classification decision")
    native_confidence: float | None = Field(None, ge=0, le=100, description="Native classifier confidence (for hybrid)")
    llm_confidence: float | None = Field(None, ge=0, le=100, description="LLM classifier confidence (for hybrid)")

    model_config = {"from_attributes": True}


class DocumentClassificationSchema(BaseModel):
    """Schema for document classification operation result."""

    source_file_id: UUID = Field(..., description="Source file ID")
    classification: ClassificationResult = Field(..., description="Classification result")
    analysis_id: UUID | None = Field(None, description="Analysis result ID if available")
