-- MQTT Middleware Database Schema
-- Creates tables for topic mappings, key transformations, and unmapped topic tracking

-- Create schema for middleware tables
CREATE SCHEMA IF NOT EXISTS middleware;

-- Topic mappings table
CREATE TABLE IF NOT EXISTS middleware.topic_mappings (
    id SERIAL PRIMARY KEY,
    source_topic VARCHAR(1024) NOT NULL,
    target_topic VARCHAR(1024) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_source_topic UNIQUE (source_topic)
);

-- Key transformations table
CREATE TABLE IF NOT EXISTS middleware.key_transformations (
    id SERIAL PRIMARY KEY,
    topic_mapping_id INTEGER NOT NULL REFERENCES middleware.topic_mappings(id) ON DELETE CASCADE,
    source_key VARCHAR(512) NOT NULL,
    target_key VARCHAR(512) NOT NULL,
    json_path VARCHAR(1024),  -- JSONPath for nested keys, e.g., "$.data.sensors[*].temp"
    transform_order INTEGER DEFAULT 0,  -- Order of application
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_mapping_source_key UNIQUE (topic_mapping_id, source_key, json_path)
);

-- Unmapped topics tracking
CREATE TABLE IF NOT EXISTS middleware.unmapped_topics (
    id SERIAL PRIMARY KEY,
    topic VARCHAR(1024) NOT NULL UNIQUE,
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    message_count BIGINT DEFAULT 1,
    sample_payload JSONB,  -- Store a sample message for reference
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_topic_mappings_source ON middleware.topic_mappings(source_topic);
CREATE INDEX IF NOT EXISTS idx_topic_mappings_active ON middleware.topic_mappings(is_active);
CREATE INDEX IF NOT EXISTS idx_key_transforms_mapping ON middleware.key_transformations(topic_mapping_id);
CREATE INDEX IF NOT EXISTS idx_unmapped_topics_topic ON middleware.unmapped_topics(topic);
CREATE INDEX IF NOT EXISTS idx_unmapped_last_seen ON middleware.unmapped_topics(last_seen);

-- Trigger for updated_at timestamps
CREATE OR REPLACE FUNCTION middleware.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_topic_mappings_updated ON middleware.topic_mappings;
CREATE TRIGGER tr_topic_mappings_updated
    BEFORE UPDATE ON middleware.topic_mappings
    FOR EACH ROW EXECUTE FUNCTION middleware.update_timestamp();

DROP TRIGGER IF EXISTS tr_key_transformations_updated ON middleware.key_transformations;
CREATE TRIGGER tr_key_transformations_updated
    BEFORE UPDATE ON middleware.key_transformations
    FOR EACH ROW EXECUTE FUNCTION middleware.update_timestamp();

-- Notification function for real-time sync
CREATE OR REPLACE FUNCTION middleware.notify_mapping_change()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('mapping_changes', json_build_object(
        'operation', TG_OP,
        'table', TG_TABLE_NAME,
        'id', COALESCE(NEW.id, OLD.id)
    )::text);
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_topic_mappings_notify ON middleware.topic_mappings;
CREATE TRIGGER tr_topic_mappings_notify
    AFTER INSERT OR UPDATE OR DELETE ON middleware.topic_mappings
    FOR EACH ROW EXECUTE FUNCTION middleware.notify_mapping_change();

DROP TRIGGER IF EXISTS tr_key_transformations_notify ON middleware.key_transformations;
CREATE TRIGGER tr_key_transformations_notify
    AFTER INSERT OR UPDATE OR DELETE ON middleware.key_transformations
    FOR EACH ROW EXECUTE FUNCTION middleware.notify_mapping_change();
