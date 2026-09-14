-- Least-privilege PostgreSQL roles for Citrus Inventory (DCL).
--
-- Run once as a superuser on the production database, then point the
-- application at the app role (SUPABASE_DB_USER / SUPABASE_DB_PASSWORD)
-- instead of the postgres superuser. Migrations still run as the owner
-- role (`citrus_owner` below or the superuser), so `scripts/release.sh`
-- should use a separate connection from the web process.
--
-- Roles
--   citrus_owner    owns the schema; runs migrations. Not used by the web app.
--   citrus_app      the Django web and job processes. Reads and writes
--                   everything the application needs, but can never DELETE
--                   a lot or a management record: those tables are
--                   append-only history, enforced here rather than only in
--                   Python (Lot.delete raises; this makes the database agree).
--   citrus_analyst  read-only, for DBeaver, notebooks and reporting.
--
-- Replace the passwords before running.

CREATE ROLE citrus_owner   LOGIN PASSWORD 'change-me';
CREATE ROLE citrus_app     LOGIN PASSWORD 'change-me';
CREATE ROLE citrus_analyst LOGIN PASSWORD 'change-me';

-- Schema ownership for migrations. Run `ALTER TABLE ... OWNER TO citrus_owner`
-- for tables that already exist under another owner (see the loop below).
GRANT ALL ON SCHEMA public TO citrus_owner;
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO citrus_owner', r.tablename);
  END LOOP;
  FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER SEQUENCE public.%I OWNER TO citrus_owner', r.sequencename);
  END LOOP;
END $$;

-- Application role: full DML by default ...
GRANT USAGE ON SCHEMA public TO citrus_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO citrus_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO citrus_app;
ALTER DEFAULT PRIVILEGES FOR ROLE citrus_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO citrus_app;
ALTER DEFAULT PRIVILEGES FOR ROLE citrus_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO citrus_app;

-- ... except on the append-only history tables. A lot leaves the board by
-- status, samples are voided, plans are re-published and decisions are
-- add-only. REVOKE makes each of those a database rule.
REVOKE DELETE ON lots_lot,
                 lots_packout,
                 lots_lotroommove,
                 lots_lottreatment,
                 sampling_sample,
                 forecast_prediction,
                 forecast_packplan,
                 forecast_planrecommendation,
                 forecast_plandecision,
                 forecast_reportdelivery
  FROM citrus_app;

-- Analyst role: read everything, change nothing.
GRANT USAGE ON SCHEMA public TO citrus_analyst;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO citrus_analyst;
ALTER DEFAULT PRIVILEGES FOR ROLE citrus_owner IN SCHEMA public
  GRANT SELECT ON TABLES TO citrus_analyst;
-- Keep credentials and sessions out of the analyst's reach.
REVOKE SELECT ON auth_user, django_session FROM citrus_analyst;
