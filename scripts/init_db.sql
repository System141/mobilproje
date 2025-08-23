-- Database initialization script for Turkish Business Integration Platform
-- This script sets up Row-Level Security and basic database structure

-- Create extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create database roles if they don't exist
DO $$
BEGIN
    -- Create admin role (full access)
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin_user') THEN
        CREATE ROLE admin_user;
        GRANT CONNECT ON DATABASE turkplatform TO admin_user;
        GRANT ALL PRIVILEGES ON DATABASE turkplatform TO admin_user;
        GRANT ALL ON SCHEMA public TO admin_user;
    END IF;
    
    -- Create tenant role (restricted access with RLS)
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tenant_user') THEN
        CREATE ROLE tenant_user;
        GRANT CONNECT ON DATABASE turkplatform TO tenant_user;
        GRANT USAGE ON SCHEMA public TO tenant_user;
    END IF;
END
$$;

-- Function to get current tenant from context
CREATE OR REPLACE FUNCTION current_tenant_id() 
RETURNS UUID AS $$
BEGIN
    RETURN COALESCE(
        current_setting('app.current_tenant', true)::UUID,
        '00000000-0000-0000-0000-000000000000'::UUID
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- Set Turkish locale settings
SET timezone = 'Europe/Istanbul';
SET datestyle = 'DMY';
SET lc_monetary = 'tr_TR.UTF-8';
SET lc_numeric = 'tr_TR.UTF-8';

-- Log successful initialization
SELECT 'Turkish Business Integration Platform database initialized successfully' as status;