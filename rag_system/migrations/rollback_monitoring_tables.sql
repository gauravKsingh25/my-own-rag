"""
Rollback migration for monitoring tables.

This script removes the monitoring tables added by add_monitoring_tables.sql

Run this migration to rollback:
```
docker exec -i postgres_container psql -U your_user -d your_db < migrations/rollback_monitoring_tables.sql
```
"""

-- Drop chat_feedbacks table (child table first due to foreign key)
DROP TABLE IF EXISTS chat_feedbacks CASCADE;

-- Drop chat_interactions table
DROP TABLE IF EXISTS chat_interactions CASCADE;
