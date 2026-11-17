-- Apply once to an existing PostgreSQL database after taking a normal backup.
-- This migration adds correction history and accepted versions only; it does
-- not update document_chunks.raw_topology or any existing table.
BEGIN;

CREATE TABLE diagram_corrections (
    correction_id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE RESTRICT,
    source_chunk_id UUID NOT NULL REFERENCES document_chunks(id) ON DELETE RESTRICT,
    user_id TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'proposed',
    original_topology JSONB NOT NULL,
    corrected_topology JSONB NOT NULL,
    proposed_changes JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary TEXT NOT NULL,
    validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    validation_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    requirements TEXT NOT NULL DEFAULT '',
    ai_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    ai_suggestions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalized_at TIMESTAMPTZ,
    CONSTRAINT ck_diagram_corrections_status
        CHECK (status IN ('proposed', 'accepted', 'rejected'))
);

CREATE INDEX idx_diagram_corrections_conversation
    ON diagram_corrections (conversation_id, created_at);
CREATE INDEX idx_diagram_corrections_source
    ON diagram_corrections (source_chunk_id, created_at);
CREATE INDEX idx_diagram_corrections_user
    ON diagram_corrections (user_id, correction_id);

CREATE TABLE diagram_versions (
    version_id UUID PRIMARY KEY,
    correction_id UUID NOT NULL UNIQUE
        REFERENCES diagram_corrections(correction_id) ON DELETE RESTRICT,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE RESTRICT,
    source_chunk_id UUID NOT NULL REFERENCES document_chunks(id) ON DELETE RESTRICT,
    user_id TEXT NOT NULL,
    topology JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_diagram_versions_conversation
    ON diagram_versions (conversation_id, created_at);
CREATE INDEX idx_diagram_versions_source
    ON diagram_versions (source_chunk_id, created_at);
CREATE INDEX idx_diagram_versions_user
    ON diagram_versions (user_id, version_id);

COMMIT;
