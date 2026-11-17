from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Index, Float, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid
from database import Base

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False, server_default='New Chat')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    user_id = Column(Text, nullable=False, server_default='legacy_user')
    
    __table_args__ = (
        Index('idx_conversations_user_thread', 'user_id', 'id'),
    )
    
class DocumentChunk(Base):
    __tablename__ = 'document_chunks'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1024))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    page_number = Column(Integer)
    source_file = Column(Text)
    user_id = Column(Text, nullable=False, server_default='legacy_user')
    raw_topology = Column(JSONB, nullable=True) 
    
    __table_args__ = (
        Index('idx_document_chunks_lookup', 'user_id', 'conversation_id'),
        Index('idx_document_chunks_user_vector','embedding', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'}),
    )


class DiagramCorrection(Base):
    """Immutable source snapshot plus a separately reviewable correction proposal."""
    __tablename__ = "diagram_corrections"

    correction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, server_default="proposed")
    original_topology = Column(JSONB, nullable=False)
    corrected_topology = Column(JSONB, nullable=False)
    proposed_changes = Column(JSONB, nullable=False, server_default="[]")
    summary = Column(Text, nullable=False)
    validation_errors = Column(JSONB, nullable=False, server_default="[]")
    validation_warnings = Column(JSONB, nullable=False, server_default="[]")
    requirements = Column(Text, nullable=False, server_default="")
    ai_warnings = Column(JSONB, nullable=False, server_default="[]")
    ai_suggestions = Column(JSONB, nullable=False, server_default="[]")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finalized_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected')",
            name="ck_diagram_corrections_status",
        ),
        Index("idx_diagram_corrections_conversation", "conversation_id", "created_at"),
        Index("idx_diagram_corrections_source", "source_chunk_id", "created_at"),
        Index("idx_diagram_corrections_user", "user_id", "correction_id"),
    )


class DiagramVersion(Base):
    """Accepted topology snapshot; never overwrites document_chunks.raw_topology."""
    __tablename__ = "diagram_versions"

    version_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("diagram_corrections.correction_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id = Column(Text, nullable=False)
    topology = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_diagram_versions_conversation", "conversation_id", "created_at"),
        Index("idx_diagram_versions_source", "source_chunk_id", "created_at"),
        Index("idx_diagram_versions_user", "user_id", "version_id"),
    )

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False) # e.g., 'human', 'ai'
    content = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False, server_default='legacy_user')

    __table_args__ = (
        Index('idx_messages_user_thread', 'user_id', 'conversation_id'),
    )


class UserMemory(Base):
    __tablename__ = "user_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Text, nullable=False)
    memory_key = Column(Text, nullable=False)
    memory_value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # Enforces the unique constraint you specified
        Index('user_memories_user_id_memory_key', 'user_id', 'memory_key', unique=True), 
    )
    
class Expense(Base):
    __tablename__ = 'expenses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, unique=True, default='legacy_user', nullable=False)
    date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(Text, nullable=False)
    subcategory = Column(Text, server_default='')
    note = Column(Text, server_default='')
    
