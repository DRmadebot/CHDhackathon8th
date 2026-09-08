from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RawRecord(Base):
    __tablename__ = "raw_records"

    id: Mapped[object] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    run_id: Mapped[object | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("crawler_runs.id"),
        nullable=True,
    )

    source_id: Mapped[object | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sources.id"),
        nullable=True,
    )

    case_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Original crawler artifact
    # ------------------------------------------------------------------

    # Exact raw content returned by the collector.
    #
    # IMPORTANT:
    # This field must never be replaced by recovered/decoded content.
    # The evidence hash is calculated from this original content.
    raw_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Recovered / derived content
    # ------------------------------------------------------------------

    # Cleaned representation used by the normal crawler pipeline.
    cleaned_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Content produced by the recovery layer when an encoding or
    # obfuscation transformation was successfully recovered.
    #
    # Example:
    #   raw_text      = "SGVsbG8gV29ybGQ="
    #   recovered_text = "Hello World"
    #
    # This is DERIVED content and does not replace raw_text.
    recovered_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Structured metadata describing how recovery was performed.
    #
    # Example:
    # {
    #     "status": "recovered",
    #     "recovered": true,
    #     "confidence": 0.94,
    #     "transformations": [
    #         {
    #             "transformation": "base64",
    #             "confidence": 0.94,
    #             "reason": "Valid Base64 structure...",
    #             "input_preview": "SGVsbG8...",
    #             "output_preview": "Hello World"
    #         }
    #     ],
    #     "candidates_considered": [...]
    # }
    recovery_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Evidence integrity
    # ------------------------------------------------------------------

    # SHA-256 of the ORIGINAL raw fetched content.
    #
    # This must continue to represent raw_text, not recovered_text.
    content_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Existing analysis fields
    # ------------------------------------------------------------------

    language: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    matched_keywords: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    relevance_label: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    relevance_confidence: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    relevance_reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    extracted_candidates: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Structured output produced by the LLM.
    #
    # Example:
    # {
    #     "entities": [...],
    #     "relationships": [...]
    # }
    structured_intelligence: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending_mapping",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )