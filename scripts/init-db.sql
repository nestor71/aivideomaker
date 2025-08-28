-- Initialize AIVideoMaker Database
-- This script runs when the PostgreSQL container starts for the first time

-- Create database if it doesn't exist
SELECT 'CREATE DATABASE aivideomaker'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'aivideomaker');

-- Connect to the aivideomaker database
\c aivideomaker;

-- Create extensions if they don't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set timezone
SET timezone = 'UTC';

-- Create indexes for better performance (these will be created by Alembic migrations)
-- But we can add some basic ones here for immediate use

-- Note: The actual tables will be created by SQLAlchemy/Alembic migrations
-- This script just sets up the database environment