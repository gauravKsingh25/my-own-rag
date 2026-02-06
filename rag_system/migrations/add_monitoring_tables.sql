"""
Database migration script to add monitoring tables.

This migration adds:
1. chat_interactions table - tracks all chat queries and responses
2. chat_feedbacks table - stores user feedback on interactions

Run this migration after updating the models:
```
docker exec -i postgres_container psql -U your_user -d your_db < migrations/add_monitoring_tables.sql
```

Or apply using your preferred migration tool.
"""

-- Chat Interactions Table
CREATE TABLE IF NOT EXISTS chat_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    confidence_score FLOAT NOT NULL,
    citations_count INTEGER DEFAULT 0,
    latency_ms FLOAT NOT NULL,
    retrieval_latency_ms FLOAT,
    generation_latency_ms FLOAT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    model_name VARCHAR(100) NOT NULL,
    cost_estimate FLOAT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

-- Create indexes for chat_interactions
CREATE INDEX IF NOT EXISTS ix_chat_interactions_id ON chat_interactions (id);
CREATE INDEX IF NOT EXISTS ix_chat_interactions_user_id ON chat_interactions (user_id);
CREATE INDEX IF NOT EXISTS ix_chat_interactions_created_at ON chat_interactions (created_at);
CREATE INDEX IF NOT EXISTS ix_chat_interactions_user_created ON chat_interactions (user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_chat_interactions_confidence ON chat_interactions (confidence_score);

-- Chat Feedbacks Table
CREATE TABLE IF NOT EXISTS chat_feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    CONSTRAINT fk_chat_feedbacks_interaction_id 
        FOREIGN KEY (interaction_id) 
        REFERENCES chat_interactions (id) 
        ON DELETE CASCADE
);

-- Create indexes for chat_feedbacks
CREATE INDEX IF NOT EXISTS ix_chat_feedbacks_id ON chat_feedbacks (id);
CREATE INDEX IF NOT EXISTS ix_chat_feedbacks_interaction_id ON chat_feedbacks (interaction_id);
CREATE INDEX IF NOT EXISTS ix_chat_feedbacks_rating ON chat_feedbacks (rating);

-- Add comments for documentation
COMMENT ON TABLE chat_interactions IS 'Stores all chat interaction data for monitoring and analytics';
COMMENT ON TABLE chat_feedbacks IS 'Stores user feedback ratings and comments for chat interactions';

COMMENT ON COLUMN chat_interactions.confidence_score IS 'Answer confidence score from 0.0 to 1.0';
COMMENT ON COLUMN chat_interactions.cost_estimate IS 'Estimated API cost in USD';
COMMENT ON COLUMN chat_feedbacks.rating IS 'User rating from 1 (poor) to 5 (excellent)';
