import asyncio
import copy
import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.schema import CreateTable

from diagram_corrections import (
    CorrectionConflict,
    CorrectionNotFound,
    CorrectionValidationFailure,
    accept_correction,
    create_correction_proposal,
    list_conversation_corrections,
    reject_correction,
)
from models import Conversation, DiagramCorrection, DiagramVersion, DocumentChunk


def make_topology(edge_list=None):
    return {
        "nodes": [
            {
                "name": "Service A",
                "type": "component",
                "metadata": {},
                "attributes": [],
                "source": "visible_text",
                "confidence": "high",
            }
        ],
        "edges": edge_list or [],
    }


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def all(self):
        return self.value


class FakeTransaction:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        store = self.session.store
        self.keys = {
            "corrections": set(store["corrections"]),
            "versions": set(store["versions"]),
        }
        self.statuses = {
            key: (row.status, row.finalized_at)
            for key, row in store["corrections"].items()
        }
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        if exc_type is not None:
            store = self.session.store
            for key in set(store["corrections"]) - self.keys["corrections"]:
                del store["corrections"][key]
            for key, (status, finalized_at) in self.statuses.items():
                store["corrections"][key].status = status
                store["corrections"][key].finalized_at = finalized_at
            for key in set(store["versions"]) - self.keys["versions"]:
                del store["versions"][key]
        return False


class FakeSession:
    def __init__(self, store):
        self.store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def begin(self):
        return FakeTransaction(self)

    async def execute(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        filters = {}
        for criterion in statement._where_criteria:
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            if left is not None and hasattr(right, "value"):
                filters[left.name] = right.value

        if entity is Conversation:
            row = self.store["conversation"]
            match = row if row.id == filters.get("id") and row.user_id == filters.get("user_id") else None
            return FakeResult(match)
        if entity is DocumentChunk:
            row = self.store["chunk"]
            match = row if (
                row.id == filters.get("id")
                and row.conversation_id == filters.get("conversation_id")
                and row.user_id == filters.get("user_id")
            ) else None
            return FakeResult(match)
        if entity is DiagramCorrection:
            row = self.store["corrections"].get(filters.get("correction_id"))
            conversation = self.store["conversation"]
            chunk = self.store["chunk"]
            match = row if (
                row is not None
                and row.user_id == filters.get("user_id")
                and row.conversation_id == conversation.id
                and conversation.user_id == filters.get("user_id")
                and row.source_chunk_id == chunk.id
                and chunk.conversation_id == row.conversation_id
                and chunk.user_id == filters.get("user_id")
            ) else None
            return FakeResult(match)
        if entity is DiagramVersion:
            return FakeResult(self.store["versions"].get(filters.get("correction_id")))
        raise AssertionError(f"Unexpected ORM entity in query: {entity}")

    def add(self, row):
        if isinstance(row, DiagramCorrection):
            self.store["corrections"][row.correction_id] = row
        elif isinstance(row, DiagramVersion):
            self.store["versions"][row.correction_id] = row
        else:
            raise AssertionError(f"Unexpected ORM object: {type(row)}")

    async def flush(self):
        return None


class DiagramCorrectionPersistenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user_id = "user-1"
        self.conversation_id = uuid.uuid4()
        self.chunk_id = uuid.uuid4()
        self.original = make_topology()
        self.conversation = Conversation(id=self.conversation_id, user_id=self.user_id)
        self.chunk = DocumentChunk(
            id=self.chunk_id,
            conversation_id=self.conversation_id,
            user_id=self.user_id,
            source_file="diagram.png",
            raw_topology=copy.deepcopy(self.original),
        )
        self.store = {
            "conversation": self.conversation,
            "chunk": self.chunk,
            "corrections": {},
            "versions": {},
        }

    def test_persisted_schema_uses_postgresql_uuid_jsonb_and_foreign_keys(self):
        ddl = str(CreateTable(DiagramCorrection.__table__).compile(dialect=postgresql.dialect()))
        columns = DiagramCorrection.__table__.c

        self.assertIn("correction_id UUID", ddl)
        self.assertIn("original_topology JSONB", ddl)
        self.assertIn("source_chunk_id UUID", ddl)
        self.assertIn("REFERENCES document_chunks (id)", ddl)
        self.assertIn("status IN ('proposed', 'accepted', 'rejected')", ddl)
        for name in ("correction_id", "conversation_id", "source_chunk_id"):
            self.assertIsInstance(columns[name].type, PostgreSQLUUID)
        for name in (
            "original_topology", "corrected_topology", "proposed_changes",
            "validation_errors", "validation_warnings", "ai_warnings", "ai_suggestions",
        ):
            self.assertIsInstance(columns[name].type, JSONB)
        self.assertTrue(columns["created_at"].type.timezone)
        self.assertTrue(columns["finalized_at"].type.timezone)
        foreign_keys = {foreign_key.target_fullname for foreign_key in DiagramCorrection.__table__.foreign_keys}
        self.assertEqual(foreign_keys, {"conversations.id", "document_chunks.id"})
        indexes = {index.name for index in DiagramCorrection.__table__.indexes}
        self.assertTrue({
            "idx_diagram_corrections_conversation",
            "idx_diagram_corrections_source",
            "idx_diagram_corrections_user",
        }.issubset(indexes))

    def session_factory(self):
        return FakeSession(self.store)

    @staticmethod
    async def corrector(topology, requirements):
        return {
            "summary": "No justified structural changes.",
            "corrected_topology": copy.deepcopy(topology),
            "proposed_changes": [],
            "ai_warnings": ["Source image is unavailable to this correction pass."],
            "ai_suggestions": [],
            "validation": {"errors": [], "warnings": []},
        }

    async def create(self, user_id=None):
        return await create_correction_proposal(
            conversation_id=self.conversation_id,
            source_chunk_id=self.chunk_id,
            user_id=user_id or self.user_id,
            requirements="Keep this conservative.",
            session_factory=self.session_factory,
            corrector=self.corrector,
        )

    async def test_each_proposal_is_persisted_with_a_unique_id_and_source_snapshot(self):
        first = await self.create()
        second = await self.create()

        self.assertNotEqual(first["correction_id"], second["correction_id"])
        self.assertEqual(len(self.store["corrections"]), 2)
        for proposal in (first, second):
            row = self.store["corrections"][uuid.UUID(proposal["correction_id"])]
            self.assertEqual(row.status, "proposed")
            self.assertEqual(row.original_topology, self.original)
            self.assertEqual(row.requirements, "Keep this conservative.")
            self.assertEqual(proposal["source"]["source_chunk_id"], str(self.chunk_id))
            self.assertEqual(proposal["ai_warnings"], ["Source image is unavailable to this correction pass."])

    async def test_proposal_creation_rejects_wrong_conversation_user(self):
        with self.assertRaises(CorrectionNotFound):
            await self.create(user_id="another-user")

        self.assertEqual(self.store["corrections"], {})

    async def test_proposal_creation_rejects_wrong_source_chunk_user(self):
        self.store["chunk"].user_id = "another-user"

        with self.assertRaises(CorrectionNotFound):
            await self.create()

        self.assertEqual(self.store["corrections"], {})

    async def test_acceptance_creates_separate_version_and_preserves_source(self):
        proposal = await self.create()
        correction_id = uuid.UUID(proposal["correction_id"])

        accepted = await accept_correction(
            correction_id=correction_id,
            user_id=self.user_id,
            session_factory=self.session_factory,
        )

        self.assertEqual(accepted["status"], "accepted")
        self.assertIsNotNone(accepted["version_id"])
        self.assertEqual(len(self.store["versions"]), 1)
        self.assertEqual(self.store["chunk"].raw_topology, self.original)
        self.assertEqual(self.store["versions"][correction_id].topology, self.original)

    async def test_rejection_preserves_proposal_and_does_not_create_version(self):
        proposal = await self.create()
        correction_id = uuid.UUID(proposal["correction_id"])

        rejected = await reject_correction(
            correction_id=correction_id,
            user_id=self.user_id,
            session_factory=self.session_factory,
        )

        self.assertEqual(rejected["status"], "rejected")
        self.assertIn(correction_id, self.store["corrections"])
        self.assertEqual(self.store["chunk"].raw_topology, self.original)
        self.assertEqual(self.store["versions"], {})

    async def test_accept_and_reject_are_idempotent_for_same_decision(self):
        accept_proposal = await self.create()
        correction_id = uuid.UUID(accept_proposal["correction_id"])
        accepted_once = await accept_correction(
            correction_id=correction_id, user_id=self.user_id, session_factory=self.session_factory
        )
        accepted_twice = await accept_correction(
            correction_id=correction_id, user_id=self.user_id, session_factory=self.session_factory
        )
        self.assertEqual(accepted_once["version_id"], accepted_twice["version_id"])
        self.assertEqual(len(self.store["versions"]), 1)

        reject_proposal = await self.create()
        rejected_once = await reject_correction(
            correction_id=uuid.UUID(reject_proposal["correction_id"]),
            user_id=self.user_id,
            session_factory=self.session_factory,
        )
        rejected_twice = await reject_correction(
            correction_id=uuid.UUID(reject_proposal["correction_id"]),
            user_id=self.user_id,
            session_factory=self.session_factory,
        )
        self.assertEqual(rejected_once["status"], rejected_twice["status"])

    async def test_opposite_final_decision_conflicts(self):
        proposal = await self.create()
        correction_id = uuid.UUID(proposal["correction_id"])
        await reject_correction(
            correction_id=correction_id, user_id=self.user_id, session_factory=self.session_factory
        )

        with self.assertRaises(CorrectionConflict):
            await accept_correction(
                correction_id=correction_id, user_id=self.user_id, session_factory=self.session_factory
            )

    async def test_acceptance_revalidates_and_rolls_back_invalid_topology(self):
        async def invalid_corrector(topology, requirements):
            invalid = copy.deepcopy(topology)
            invalid["edges"] = [{
                "source": "Service A", "target": "Missing", "relationship": "connects",
                "cardinality_or_type": None,
            }]
            return {
                "summary": "Invalid proposal",
                "corrected_topology": invalid,
                "proposed_changes": [{
                    "operation": "add_edge",
                    "target": {"source": "Service A", "target": "Missing"},
                    "before": None,
                    "after": invalid["edges"][0],
                    "reason": "Invalid test edge.",
                    "confidence": "high",
                    "uncertainty": None,
                }],
                "validation": {"errors": [], "warnings": []},
            }

        proposal = await create_correction_proposal(
            conversation_id=self.conversation_id,
            source_chunk_id=self.chunk_id,
            user_id=self.user_id,
            session_factory=self.session_factory,
            corrector=invalid_corrector,
        )
        correction_id = uuid.UUID(proposal["correction_id"])

        with self.assertRaises(CorrectionValidationFailure):
            await accept_correction(
                correction_id=correction_id, user_id=self.user_id, session_factory=self.session_factory
            )

        self.assertEqual(self.store["corrections"][correction_id].status, "proposed")
        self.assertEqual(self.store["versions"], {})

    async def test_accept_and_reject_verify_user_ownership(self):
        proposal = await self.create()
        correction_id = uuid.UUID(proposal["correction_id"])

        with self.assertRaises(CorrectionNotFound):
            await accept_correction(
                correction_id=correction_id, user_id="another-user", session_factory=self.session_factory
            )
        with self.assertRaises(CorrectionNotFound):
            await reject_correction(
                correction_id=correction_id, user_id="another-user", session_factory=self.session_factory
            )

        self.assertEqual(self.store["corrections"][correction_id].status, "proposed")

    async def test_acceptance_rechecks_source_chunk_ownership(self):
        proposal = await self.create()
        correction_id = uuid.UUID(proposal["correction_id"])
        self.store["chunk"].user_id = "another-user"

        with self.assertRaises(CorrectionNotFound):
            await accept_correction(
                correction_id=correction_id, user_id=self.user_id, session_factory=self.session_factory
            )

        self.assertEqual(self.store["corrections"][correction_id].status, "proposed")

    async def test_history_returns_all_statuses_only_for_conversation_owner(self):
        base = await self.create()
        first = self.store["corrections"][uuid.UUID(base["correction_id"])]
        first.status = "rejected"
        first.created_at = datetime.now(timezone.utc)
        second = copy.copy(first)
        second.correction_id = uuid.uuid4()
        second.status = "accepted"
        second.created_at = datetime.now(timezone.utc)
        third = copy.copy(first)
        third.correction_id = uuid.uuid4()
        third.status = "proposed"
        third.created_at = datetime.now(timezone.utc)
        rows = [(first, self.chunk.source_file), (second, self.chunk.source_file), (third, self.chunk.source_file)]

        class HistorySession:
            def __init__(self, allowed):
                self.calls = 0
                self.allowed = allowed

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def execute(self, _statement):
                self.calls += 1
                if self.calls == 1:
                    return FakeResult(self.conversation_id if self.allowed else None)
                return FakeResult(rows)

        class Factory:
            def __init__(self, allowed):
                self.allowed = allowed
            def __call__(self):
                session = HistorySession(self.allowed)
                session.conversation_id = self_id
                return session

        self_id = self.conversation_id
        history = await list_conversation_corrections(
            conversation_id=self.conversation_id,
            user_id=self.user_id,
            session_factory=Factory(True),
        )
        self.assertEqual([item["status"] for item in history], ["rejected", "accepted", "proposed"])
        self.assertEqual(history[0]["source"]["source_file"], "diagram.png")
        with self.assertRaises(CorrectionNotFound):
            await list_conversation_corrections(
                conversation_id=self.conversation_id,
                user_id="another-user",
                session_factory=Factory(False),
            )


if __name__ == "__main__":
    unittest.main()
