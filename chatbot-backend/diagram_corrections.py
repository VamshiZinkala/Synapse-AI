"""Persistence services for correction proposals and accepted diagram versions."""

from datetime import datetime, timezone
from copy import deepcopy
from typing import Any, Callable
import uuid

from sqlalchemy import select

from database import AsyncSessionLocal
from diagram_reasoning_agent import (
    CorrectedTopology,
    ProposedChange,
    validate_proposed_operations,
    validate_topology,
)
from models import Conversation, DiagramCorrection, DiagramVersion, DocumentChunk


class CorrectionNotFound(Exception):
    """The source or correction is absent or does not belong to the caller."""


class CorrectionConflict(Exception):
    """A correction has already been finalized in the opposite state."""


class CorrectionValidationFailure(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Corrected topology failed validation")


def _correction_payload(row: DiagramCorrection, source_file: str | None = None) -> dict[str, Any]:
    validation = {
        "errors": row.validation_errors,
        "warnings": row.validation_warnings,
    }
    try:
        corrected = CorrectedTopology.model_validate(row.corrected_topology).model_dump()
        report = validate_topology(corrected, "corrected_topology")
        operation_errors = validate_proposed_operations(
            row.original_topology,
            corrected,
            [ProposedChange.model_validate(item) for item in row.proposed_changes],
        )
        validation = {
            "errors": [*report.errors, *operation_errors],
            "warnings": report.warnings,
        }
    except Exception:
        # Preserve the stored report if historical proposal data cannot be parsed.
        pass

    return {
        "correction_id": str(row.correction_id),
        "status": row.status,
        "source": {
            "conversation_id": str(row.conversation_id),
            "source_chunk_id": str(row.source_chunk_id),
            "source_file": source_file,
        },
        "original_topology": row.original_topology,
        "corrected_topology": row.corrected_topology,
        "proposed_changes": row.proposed_changes,
        "summary": row.summary,
        "ai_warnings": row.ai_warnings,
        "ai_suggestions": row.ai_suggestions,
        "validation": {
            **validation,
        },
        "requirements": row.requirements,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "finalized_at": row.finalized_at.isoformat() if row.finalized_at else None,
    }


def _decision_payload(row: DiagramCorrection, version: DiagramVersion | None = None) -> dict[str, Any]:
    return {
        "correction_id": str(row.correction_id),
        "status": row.status,
        "version_id": str(version.version_id) if version else None,
        "corrected_topology": row.corrected_topology,
        "finalized_at": row.finalized_at.isoformat() if row.finalized_at else None,
    }


async def list_conversation_corrections(
    *,
    conversation_id: uuid.UUID,
    user_id: str,
    session_factory: Callable = AsyncSessionLocal,
) -> list[dict[str, Any]]:
    """Return correction history only after verifying conversation ownership."""
    async with session_factory() as db:
        owner = await db.execute(
            select(Conversation.id).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        if owner.scalar_one_or_none() is None:
            raise CorrectionNotFound("Conversation not found for this user")

        result = await db.execute(
            select(DiagramCorrection, DocumentChunk.source_file)
            .join(DocumentChunk, DiagramCorrection.source_chunk_id == DocumentChunk.id)
            .where(
                DiagramCorrection.conversation_id == conversation_id,
                DiagramCorrection.user_id == user_id,
                DocumentChunk.user_id == user_id,
                DocumentChunk.conversation_id == conversation_id,
            )
            .order_by(DiagramCorrection.created_at, DiagramCorrection.correction_id)
        )
        return [
            _correction_payload(correction, source_file)
            for correction, source_file in result.all()
        ]


async def create_correction_proposal(
    *,
    conversation_id: uuid.UUID,
    source_chunk_id: uuid.UUID,
    user_id: str,
    requirements: str = "",
    session_factory: Callable = AsyncSessionLocal,
    corrector: Callable | None = None,
) -> dict[str, Any]:
    """Generate and persist a distinct proposal tied to an owned source chunk."""
    if corrector is None:
        from diagram_reasoning_agent import correct_diagram

        corrector = correct_diagram

    async with session_factory() as db:
        conversation_result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conversation = conversation_result.scalar_one_or_none()
        if conversation is None:
            raise CorrectionNotFound("Conversation not found for this user")

        chunk_result = await db.execute(
            select(DocumentChunk).where(
                DocumentChunk.id == source_chunk_id,
                DocumentChunk.conversation_id == conversation_id,
                DocumentChunk.user_id == user_id,
            )
        )
        chunk = chunk_result.scalar_one_or_none()
        if chunk is None or not chunk.raw_topology:
            raise CorrectionNotFound("Topology source not found for this user and conversation")
        original_topology = deepcopy(chunk.raw_topology)
        source_file = chunk.source_file

    # Do not hold a database transaction/connection open during the LLM call.
    generated = await corrector(original_topology, requirements or "")
    async with session_factory() as db:
        async with db.begin():
            conversation_result = await db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                ).with_for_update()
            )
            conversation = conversation_result.scalar_one_or_none()
            chunk_result = await db.execute(
                select(DocumentChunk).where(
                    DocumentChunk.id == source_chunk_id,
                    DocumentChunk.conversation_id == conversation_id,
                    DocumentChunk.user_id == user_id,
                ).with_for_update()
            )
            chunk = chunk_result.scalar_one_or_none()
            if conversation is None or chunk is None or not chunk.raw_topology:
                raise CorrectionNotFound("Topology source ownership changed during proposal generation")
            if chunk.raw_topology != original_topology:
                raise CorrectionConflict("Source topology changed during proposal generation; retry")
            correction_id = uuid.uuid4()
            row = DiagramCorrection(
                correction_id=correction_id,
                conversation_id=conversation_id,
                source_chunk_id=source_chunk_id,
                user_id=user_id,
                status="proposed",
                original_topology=original_topology,
                corrected_topology=generated["corrected_topology"],
                proposed_changes=generated.get("proposed_changes", []),
                summary=generated.get("summary", ""),
                validation_errors=generated.get("validation", {}).get("errors", []),
                validation_warnings=generated.get("validation", {}).get("warnings", []),
                requirements=requirements or "",
                ai_warnings=generated.get("ai_warnings", []),
                ai_suggestions=generated.get("ai_suggestions", []),
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            await db.flush()
            return _correction_payload(row, source_file)


async def _load_owned_correction(db, correction_id: uuid.UUID, user_id: str) -> DiagramCorrection:
    result = await db.execute(
        select(DiagramCorrection)
        .join(Conversation, DiagramCorrection.conversation_id == Conversation.id)
        .join(DocumentChunk, DiagramCorrection.source_chunk_id == DocumentChunk.id)
        .where(
            DiagramCorrection.correction_id == correction_id,
            DiagramCorrection.user_id == user_id,
            Conversation.user_id == user_id,
            DocumentChunk.user_id == user_id,
            DocumentChunk.conversation_id == DiagramCorrection.conversation_id,
        )
        .with_for_update()
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise CorrectionNotFound("Correction proposal not found for this user")
    return row


async def accept_correction(
    *,
    correction_id: uuid.UUID,
    user_id: str,
    session_factory: Callable = AsyncSessionLocal,
) -> dict[str, Any]:
    """Revalidate and accept a proposal atomically, creating a separate version."""
    async with session_factory() as db:
        async with db.begin():
            row = await _load_owned_correction(db, correction_id, user_id)
            if row.status == "accepted":
                result = await db.execute(
                    select(DiagramVersion).where(DiagramVersion.correction_id == row.correction_id)
                )
                version = result.scalar_one_or_none()
                if version is None:
                    raise RuntimeError("Accepted correction is missing its diagram version")
                return _decision_payload(row, version)
            if row.status == "rejected":
                raise CorrectionConflict("Rejected proposal cannot be accepted")

            try:
                corrected = CorrectedTopology.model_validate(row.corrected_topology)
            except Exception as exc:
                raise CorrectionValidationFailure([f"Invalid corrected topology: {exc}"]) from exc

            corrected_topology = corrected.model_dump()
            report = validate_topology(corrected_topology, "corrected_topology")
            try:
                operation_errors = validate_proposed_operations(
                    row.original_topology,
                    corrected_topology,
                    [ProposedChange.model_validate(item) for item in row.proposed_changes],
                )
            except Exception as exc:
                raise CorrectionValidationFailure([f"Invalid proposed changes: {exc}"]) from exc
            errors = [*report.errors, *operation_errors]
            if errors:
                raise CorrectionValidationFailure(errors)

            finalized_at = datetime.now(timezone.utc)
            version = DiagramVersion(
                version_id=uuid.uuid4(),
                correction_id=row.correction_id,
                conversation_id=row.conversation_id,
                source_chunk_id=row.source_chunk_id,
                user_id=row.user_id,
                topology=corrected_topology,
            )
            db.add(version)
            row.status = "accepted"
            row.finalized_at = finalized_at
            await db.flush()
            return _decision_payload(row, version)


async def reject_correction(
    *,
    correction_id: uuid.UUID,
    user_id: str,
    session_factory: Callable = AsyncSessionLocal,
) -> dict[str, Any]:
    """Reject a pending proposal without deleting its correction history."""
    async with session_factory() as db:
        async with db.begin():
            row = await _load_owned_correction(db, correction_id, user_id)
            if row.status == "rejected":
                return _decision_payload(row)
            if row.status == "accepted":
                raise CorrectionConflict("Accepted proposal cannot be rejected")

            row.status = "rejected"
            row.finalized_at = datetime.now(timezone.utc)
            await db.flush()
            return _decision_payload(row)
