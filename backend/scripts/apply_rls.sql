-- apply_rls.sql
-- Row-Level Security policies for multi-tenant isolation.
-- Run once after initial schema creation.
-- Tables without tenant_id (tenants) are excluded.

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT table_name
        FROM information_schema.columns
        WHERE column_name = 'tenant_id'
          AND table_schema = 'public'
          AND table_name NOT IN ('tenants')
        GROUP BY table_name
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tbl);

        -- Drop existing policy if present (idempotent)
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', tbl);

        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I FOR ALL USING (tenant_id = current_setting($q$app.current_tenant$q$)::uuid) WITH CHECK (tenant_id = current_setting($q$app.current_tenant$q$)::uuid)',
            tbl
        );

        RAISE NOTICE 'RLS applied on table %', tbl;
    END LOOP;
END
$$;
