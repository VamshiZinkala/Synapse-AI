from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Index, Float
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
    
