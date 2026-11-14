-- SH-postgres_isolation: research-only roles. Runs once on first initdb.
-- NO production credentials here: throwaway users for the disposable cluster.

-- Non-superuser application role used by studies (pg_guard requires DSNs to
-- target host `pg_research`, db `clara_research`).
CREATE ROLE research_app LOGIN PASSWORD 'research-only-throwaway'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

GRANT CONNECT ON DATABASE clara_research TO research_app;
-- Studies create their own test tables inside `research_test`; this grants
-- schema creation without superuser or createdb privileges.
GRANT CREATE ON DATABASE clara_research TO research_app;

-- A dedicated test schema; studies must not touch `public` system objects.
\connect clara_research
CREATE SCHEMA IF NOT EXISTS research_test AUTHORIZATION research_admin;
GRANT USAGE ON SCHEMA research_test TO research_app;
GRANT CREATE ON SCHEMA research_test TO research_app;
ALTER DEFAULT PRIVILEGES FOR ROLE research_admin IN SCHEMA research_test
    GRANT ALL ON TABLES TO research_app;

-- Advisory locks (task contract) are session-scoped and need no grants.
