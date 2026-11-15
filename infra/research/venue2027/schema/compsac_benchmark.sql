-- COMPSAC-X03_pg_schema (P04, venue compsac)
-- Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes (RQ1)
--
-- Purpose
-- -------
-- Isolated benchmark DDL for the dependency-complete scope-local OCC study:
-- partitioned/versioned clinical entities, governance and consent epochs, and
-- an append-only operation ledger, used to run concurrent-write schedules and
-- export histories to an independent serializability checker.
--
-- Isolation contract
-- ------------------
-- * EVERY object lives in the dedicated `research_schema` namespace. The DDL
--   never references, alters or drops any production table, and it must only
--   be applied to the disposable research cluster provisioned by
--   infra/research/venue2027/docker-compose.pg.yaml (db `clara_research`).
--   Connection URLs are guarded by research/venue2027/_shared/tools/pg_guard.py.
-- * Experiment-only data: per-synthetic-tenant keys are explicitly unique so
--   benchmark arms cannot cross-contaminate; no patient identifiers exist.
-- * No production migrations: this file is never wired into the API service's
--   versioned migration directory or any application migration path.
-- * Rollback: DROP SCHEMA research_schema CASCADE (idempotent form below,
--   COMPSAC-X03_ROLLBACK). Every CREATE here is idempotent (IF NOT EXISTS).
--
-- Failure semantics
-- -----------------
-- Applying this DDL to a database where any target object already exists with
-- an incompatible definition fails at the conflicting statement (fail closed);
-- it never silently reshapes an existing object. Epoch transitions and CAS
-- semantics are enforced by table constraints (CHECK) and unique indexes, so
-- a forbidden write is rejected by the engine, not by application hope.
--
-- Version: COMPSAC_X03_SCHEMA_VERSION = "1.0.0"

-- ---------------------------------------------------------------------------
-- 0. Namespace
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS research_schema;

COMMENT ON SCHEMA research_schema IS
    'COMPSAC-X03 experiment-only benchmark namespace; never production data.';

-- ---------------------------------------------------------------------------
-- 1. benchmark_tenants: explicit per-synthetic-tenant registry
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS research_schema.benchmark_tenants (
    tenant_id        text PRIMARY KEY,
    label            text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT benchmark_tenants_label_chk CHECK (length(label) > 0)
);

-- ---------------------------------------------------------------------------
-- 2. entities: clinical entities under benchmark versioning
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS research_schema.entities (
    tenant_id        text NOT NULL REFERENCES research_schema.benchmark_tenants (tenant_id),
    entity_id        text NOT NULL,
    entity_kind      text NOT NULL
                     CHECK (entity_kind IN
                         ('medication_order', 'allergy', 'history', 'purpose_grant')),
    version          bigint NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    -- Explicit per-synthetic-tenant unique key: two benchmark tenants never
    -- collide on the same entity_id.
    CONSTRAINT entities_tenant_entity_pk PRIMARY KEY (tenant_id, entity_id),
    CONSTRAINT entities_kind_tenant_chk CHECK (length(tenant_id) > 0 AND length(entity_id) > 0)
);

-- Hot path for version lookups (commit-time validation reads current versions).
CREATE INDEX IF NOT EXISTS entities_tenant_version_idx
    ON research_schema.entities (tenant_id, entity_id, version);

-- ---------------------------------------------------------------------------
-- 3. entity_version_partitions: append-only per-entity version history
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS research_schema.entity_version_partitions (
    tenant_id        text NOT NULL,
    entity_id        text NOT NULL,
    version          bigint NOT NULL CHECK (version >= 0),
    payload_sha256   text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    written_by_op    text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT entity_version_partitions_pk
        PRIMARY KEY (tenant_id, entity_id, version),
    CONSTRAINT entity_version_partitions_entity_fk
        FOREIGN KEY (tenant_id, entity_id)
        REFERENCES research_schema.entities (tenant_id, entity_id)
        ON DELETE CASCADE
);

-- Range-partition-ready lookup index (per-entity ordered history).
CREATE INDEX IF NOT EXISTS entity_version_partitions_history_idx
    ON research_schema.entity_version_partitions (tenant_id, entity_id, version);

-- ---------------------------------------------------------------------------
-- 4. governance_epochs: monotone policy epochs for CAS admission
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS research_schema.governance_epochs (
    tenant_id        text NOT NULL,
    epoch_id         text NOT NULL,
    policy_version   text NOT NULL,
    active           boolean NOT NULL DEFAULT TRUE,
    created_at       timestamptz NOT NULL DEFAULT now(),
    -- At most one active policy epoch per synthetic tenant.
    CONSTRAINT governance_epochs_active_uq
        UNIQUE (tenant_id, active),
    CONSTRAINT governance_epochs_pk
        PRIMARY KEY (tenant_id, epoch_id),
    CONSTRAINT governance_epochs_policy_chk CHECK (length(policy_version) > 0)
);

CREATE INDEX IF NOT EXISTS governance_epochs_tenant_idx
    ON research_schema.governance_epochs (tenant_id, active, created_at);

-- ---------------------------------------------------------------------------
-- 5. consent_epochs: per-patient synthetic consent epochs
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS research_schema.consent_epochs (
    tenant_id        text NOT NULL,
    subject_id       text NOT NULL,
    epoch_id         text NOT NULL,
    consent_state    text NOT NULL
                     CHECK (consent_state IN ('granted', 'revoked', 'withdrawn')),
    active           boolean NOT NULL DEFAULT TRUE,
    created_at       timestamptz NOT NULL DEFAULT now(),
    -- At most one active consent epoch per (tenant, subject).
    CONSTRAINT consent_epochs_active_uq
        UNIQUE (tenant_id, subject_id, active),
    CONSTRAINT consent_epochs_pk
        PRIMARY KEY (tenant_id, subject_id, epoch_id)
);

CREATE INDEX IF NOT EXISTS consent_epochs_subject_idx
    ON research_schema.consent_epochs (tenant_id, subject_id, active, created_at);

-- ---------------------------------------------------------------------------
-- 6. op_log: append-only operation ledger (schedule replay + Elle export)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS research_schema.op_log (
    tenant_id        text NOT NULL,
    op_id            text NOT NULL,
    op_kind          text NOT NULL
                     CHECK (op_kind IN ('read', 'write', 'commit', 'abort', 'epoch_bump')),
    entity_id        text,
    -- CAS admission column: the version the writer believed it was building on.
    base_version     bigint CHECK (base_version IS NULL OR base_version >= 0),
    observed_version bigint CHECK (observed_version IS NULL OR observed_version >= 0),
    governance_epoch text,
    consent_epoch    text,
    status           text NOT NULL
                     CHECK (status IN ('pending', 'committed', 'aborted')),
    attempt          integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT op_log_pk PRIMARY KEY (tenant_id, op_id, attempt),
    CONSTRAINT op_log_outcome_chk CHECK (
        (status = 'pending')
        OR (status IN ('committed', 'aborted') AND attempt > 0)
    )
);

-- Schedule-replay lookups: per-tenant ledger scan and per-entity writes.
CREATE INDEX IF NOT EXISTS op_log_tenant_status_idx
    ON research_schema.op_log (tenant_id, status, created_at);
CREATE INDEX IF NOT EXISTS op_log_entity_idx
    ON research_schema.op_log (tenant_id, entity_id, attempt);

-- ---------------------------------------------------------------------------
-- 7. Dependency-complete scope edges (versioned read/write links)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS research_schema.op_dependency_edges (
    tenant_id        text NOT NULL,
    op_id            text NOT NULL,
    attempt          integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    edge_kind        text NOT NULL CHECK (edge_kind IN ('required_read', 'write')),
    dep_tenant_id    text NOT NULL,
    dep_entity_id    text NOT NULL,
    dep_version      bigint NOT NULL CHECK (dep_version >= 0),
    CONSTRAINT op_dependency_edges_pk
        PRIMARY KEY (tenant_id, op_id, attempt, edge_kind, dep_tenant_id, dep_entity_id),
    CONSTRAINT op_dependency_edges_op_fk
        FOREIGN KEY (tenant_id, op_id, attempt)
        REFERENCES research_schema.op_log (tenant_id, op_id, attempt)
        ON DELETE CASCADE,
    -- Dependency closure must resolve to a real benchmark entity version.
    CONSTRAINT op_dependency_edges_entity_fk
        FOREIGN KEY (dep_tenant_id, dep_entity_id)
        REFERENCES research_schema.entities (tenant_id, entity_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS op_dependency_edges_entity_idx
    ON research_schema.op_dependency_edges (dep_tenant_id, dep_entity_id, dep_version);

-- ---------------------------------------------------------------------------
-- 8. Rollback helper (research-only; never touches anything outside the
--    research_schema namespace).
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'research_schema' AND p.proname = 'compsac_x03_rollback'
    ) THEN
        EXECUTE $fn$
CREATE FUNCTION research_schema.compsac_x03_rollback() RETURNS void
LANGUAGE plpgsql AS $body$
BEGIN
    DROP TABLE IF EXISTS research_schema.op_dependency_edges;
    DROP TABLE IF EXISTS research_schema.op_log;
    DROP TABLE IF EXISTS research_schema.consent_epochs;
    DROP TABLE IF EXISTS research_schema.governance_epochs;
    DROP TABLE IF EXISTS research_schema.entity_version_partitions;
    DROP TABLE IF EXISTS research_schema.entities;
    DROP TABLE IF EXISTS research_schema.benchmark_tenants;
END;
$body$;
        $fn$;
    END IF;
END $$;

COMMENT ON FUNCTION research_schema.compsac_x03_rollback() IS
    'COMPSAC-X03 rollback: drops only research_schema benchmark objects.';
