-- PostgreSQL Initial Setup Script for Autonomous Claims System

-- Ensure claims_db database extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log database initialization
DO $$
BEGIN
    RAISE NOTICE 'Database claims_db initialized successfully with extension uuid-ossp.';
END $$;
