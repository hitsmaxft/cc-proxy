import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import asyncio
import aiosqlite
from contextlib import asynccontextmanager

from src.core.logging import logger


class MessageHistoryDatabase:
    """SQLite database manager for message history storage"""

    def __init__(self, db_path: str = "proxy.db"):
        self.db_path = db_path
        self._initialized = False

    async def initialize(self):
        """Initialize the database and create tables if they don't exist"""
        if self._initialized:
            return

        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Create table with original schema
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS message_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id TEXT UNIQUE NOT NULL,
                        timestamp DATETIME NOT NULL,
                        model_name TEXT NOT NULL,
                        request_data TEXT NOT NULL,
                        response_data TEXT,
                        user_agent TEXT,
                        is_streaming BOOLEAN NOT NULL DEFAULT 0,
                        request_length INTEGER,
                        response_length INTEGER,
                        status TEXT DEFAULT 'pending'
                    )
                """)

                # Check if actual_model column exists, if not add it
                cursor = await db.execute("PRAGMA table_info(message_history)")
                columns = await cursor.fetchall()
                column_names = [column[1] for column in columns]

                if "actual_model" not in column_names:
                    logger.info("Adding actual_model column to message_history table")
                    await db.execute("""
                        ALTER TABLE message_history 
                        ADD COLUMN actual_model TEXT DEFAULT ''
                    """)
                    # Update existing records with model_name as default
                    await db.execute("""
                        UPDATE message_history 
                        SET actual_model = model_name 
                        WHERE actual_model = '' OR actual_model IS NULL
                    """)

                # Add token usage columns if they don't exist
                if "input_tokens" not in column_names:
                    logger.info("Adding input_tokens column to message_history table")
                    await db.execute("""
                        ALTER TABLE message_history 
                        ADD COLUMN input_tokens INTEGER DEFAULT 0
                    """)

                if "output_tokens" not in column_names:
                    logger.info("Adding output_tokens column to message_history table")
                    await db.execute("""
                        ALTER TABLE message_history 
                        ADD COLUMN output_tokens INTEGER DEFAULT 0
                    """)

                if "total_tokens" not in column_names:
                    logger.info("Adding total_tokens column to message_history table")
                    await db.execute("""
                        ALTER TABLE message_history 
                        ADD COLUMN total_tokens INTEGER DEFAULT 0
                    """)

                # Add openai_request column if it doesn't exist
                if "openai_request" not in column_names:
                    logger.info("Adding openai_request column to message_history table")
                    await db.execute("""
                        ALTER TABLE message_history 
                        ADD COLUMN openai_request TEXT
                    """)

                # Create index for better query performance
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON message_history(timestamp DESC)
                """)

                # Create model configuration table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS model_configuration (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT UNIQUE NOT NULL,
                        value TEXT NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                """)

                # Create index for model configuration key lookup
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_model_config_key 
                    ON model_configuration(key)
                """)

                await db.commit()
                logger.info(f"Message history database initialized at {self.db_path}")
                self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize message history database: {e}")
            raise

    async def store_request(
        self,
        request_id: str,
        model_name: str,
        actual_model: str,
        request_data: Dict[str, Any],
        user_agent: Optional[str] = None,
        is_streaming: bool = False,
        openai_request: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store a request in the database"""
        await self.initialize()

        try:
            request_json = json.dumps(request_data, ensure_ascii=False)
            request_length = len(request_json)
            openai_request_json = json.dumps(openai_request, ensure_ascii=False) if openai_request else None

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO message_history 
                    (request_id, timestamp, model_name, actual_model, request_data, user_agent, 
                     is_streaming, request_length, status, input_tokens, output_tokens, total_tokens, openai_request)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        request_id,
                        datetime.now().isoformat(),
                        model_name,
                        actual_model,
                        request_json,
                        user_agent,
                        is_streaming,
                        request_length,
                        "pending",
                        0,  # input_tokens - will be updated later
                        0,  # output_tokens - will be updated later
                        0,  # total_tokens - will be updated later
                        openai_request_json,
                    ),
                )
                await db.commit()

            logger.debug(f"Stored request {request_id} for model {model_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to store request {request_id}: {e}")
            return False

    async def update_response(
        self,
        request_id: str,
        response_data: Dict[str, Any],
        status: str = "completed",
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
    ) -> bool:
        """Update the response data for a stored request"""
        await self.initialize()

        try:
            response_json = json.dumps(response_data, ensure_ascii=False)
            response_length = len(response_json)

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    UPDATE message_history 
                    SET response_data = ?, response_length = ?, status = ?, 
                        input_tokens = ?, output_tokens = ?, total_tokens = ?
                    WHERE request_id = ?
                """,
                    (
                        response_json,
                        response_length,
                        status,
                        input_tokens,
                        output_tokens,
                        total_tokens,
                        request_id,
                    ),
                )
                await db.commit()

            logger.debug(f"Updated response for request {request_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update response for {request_id}: {e}")
            return False

    async def get_recent_messages(
        self,
        limit: int = 5,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get the most recent messages from the database with optional date filtering"""
        await self.initialize()

        try:
            query = """
                SELECT id, request_id, timestamp, model_name, actual_model, request_data, 
                       response_data, user_agent, is_streaming, request_length, 
                       response_length, status, input_tokens, output_tokens, total_tokens, openai_request
                FROM message_history 
                WHERE 1=1
            """

            params = []

            # Add date filters if provided
            if start_date:
                # Convert to ISO format for start of day
                start_datetime = f"{start_date}T00:00:00"
                query += " AND timestamp >= ? "
                params.append(start_datetime)

            if end_date:
                # Convert to ISO format for end of day
                end_datetime = f"{end_date}T23:59:59.999999"
                query += " AND timestamp <= ? "
                params.append(end_datetime)

            # Add ordering and limit
            query += " ORDER BY timestamp DESC LIMIT ? "
            params.append(limit)

            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()

                    messages = []
                    for row in rows:
                        # Parse JSON data safely
                        try:
                            request_data = (
                                json.loads(row["request_data"])
                                if row["request_data"]
                                else {}
                            )
                            response_data = (
                                json.loads(row["response_data"])
                                if row["response_data"]
                                else {}
                            )
                            openai_request = (
                                json.loads(row["openai_request"])
                                if row["openai_request"]
                                else {}
                            )
                            openai_request = (
                                json.loads(row["openai_request"])
                                if row["openai_request"]
                                else {}
                            )
                        except json.JSONDecodeError:
                            request_data = {}
                            response_data = {}
                            openai_request = {}

                        # Handle token columns that might not exist in older database schemas
                        input_tokens = 0
                        output_tokens = 0
                        total_tokens = 0

                        try:
                            input_tokens = row["input_tokens"] or 0
                        except (KeyError, IndexError):
                            pass

                        try:
                            output_tokens = row["output_tokens"] or 0
                        except (KeyError, IndexError):
                            pass

                        try:
                            total_tokens = row["total_tokens"] or 0
                        except (KeyError, IndexError):
                            pass

                        messages.append(
                            {
                                "id": row["id"],
                                "request_id": row["request_id"],
                                "timestamp": row["timestamp"],
                                "model_name": row["model_name"],
                                "actual_model": row["actual_model"],
                                "request_data": request_data,
                                "response_data": response_data,
                                "openai_request": openai_request,
                                "user_agent": row["user_agent"],
                                "is_streaming": bool(row["is_streaming"]),
                                "request_length": row["request_length"] or 0,
                                "response_length": row["response_length"] or 0,
                                "status": row["status"],
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens,
                                "total_tokens": total_tokens,
                            }
                        )

                    return messages

        except Exception as e:
            logger.error(f"Failed to retrieve recent messages: {e}")
            return []

    async def cleanup_old_messages(self, keep_days: int = 28) -> int:
        """Remove messages older than specified days"""
        await self.initialize()

        try:
            cutoff_date = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - keep_days)

            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    """
                    DELETE FROM message_history 
                    WHERE timestamp < ?
                """,
                    (cutoff_date.isoformat(),),
                )
                await db.commit()
                deleted_count = cursor.rowcount

            logger.info(f"Cleaned up {deleted_count} old messages")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old messages: {e}")
            return 0

    async def get_token_usage_summary(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get aggregated token usage summary by actual model with optional date range filtering"""
        await self.initialize()

        try:
            query = """
                SELECT 
                    actual_model,
                    COUNT(*) as request_count,
                    SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
                    SUM(COALESCE(output_tokens, 0)) as total_output_tokens,
                    SUM(COALESCE(total_tokens, 0)) as total_tokens,
                    AVG(COALESCE(input_tokens, 0)) as avg_input_tokens,
                    AVG(COALESCE(output_tokens, 0)) as avg_output_tokens,
                    MIN(timestamp) as first_request,
                    MAX(timestamp) as last_request,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_requests,
                    SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) as partial_requests,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_requests
                FROM message_history 
                WHERE actual_model IS NOT NULL AND actual_model != ''
            """

            params = []

            # Add date filters if provided
            if start_date:
                # Convert to ISO format for start of day
                start_datetime = f"{start_date}T00:00:00"
                query += " AND timestamp >= ? "
                params.append(start_datetime)

            if end_date:
                # Convert to ISO format for end of day
                end_datetime = f"{end_date}T23:59:59.999999"
                query += " AND timestamp <= ? "
                params.append(end_datetime)

            query += """
                GROUP BY actual_model
                ORDER BY total_tokens DESC
            """

            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()

                    summary = []
                    for row in rows:
                        summary.append(
                            {
                                "model": row["actual_model"],
                                "request_count": row["request_count"] or 0,
                                "total_input_tokens": row["total_input_tokens"] or 0,
                                "total_output_tokens": row["total_output_tokens"] or 0,
                                "total_tokens": row["total_tokens"] or 0,
                                "avg_input_tokens": round(
                                    row["avg_input_tokens"] or 0, 2
                                ),
                                "avg_output_tokens": round(
                                    row["avg_output_tokens"] or 0, 2
                                ),
                                "first_request": row["first_request"],
                                "last_request": row["last_request"],
                                "completed_requests": row["completed_requests"] or 0,
                                "partial_requests": row["partial_requests"] or 0,
                                "pending_requests": row["pending_requests"] or 0,
                                "success_rate": round(
                                    (row["completed_requests"] or 0)
                                    / max(row["request_count"], 1)
                                    * 100,
                                    2,
                                ),
                            }
                        )

                    return summary

        except Exception as e:
            logger.error(f"Failed to get token usage summary: {e}")
            return []

    async def save_model_config(
        self, big_model: str, middle_model: str, small_model: str
    ) -> bool:
        """Save model configuration to database"""
        await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path) as db:
                current_time = datetime.now().isoformat()

                # Insert or replace model configurations
                models = {
                    "BIG_MODEL": big_model,
                    "MIDDLE_MODEL": middle_model,
                    "SMALL_MODEL": small_model,
                }

                for key, value in models.items():
                    await db.execute(
                        """
                        INSERT OR REPLACE INTO model_configuration (key, value, updated_at)
                        VALUES (?, ?, ?)
                    """,
                        (key, value, current_time),
                    )

                await db.commit()
                logger.info(
                    f"Model configuration saved: BIG={big_model}, MIDDLE={middle_model}, SMALL={small_model}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to save model configuration: {e}")
            return False

    async def load_model_config(self) -> Dict[str, str]:
        """Load model configuration from database"""
        await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT key, value FROM model_configuration 
                    WHERE key IN ('BIG_MODEL', 'MIDDLE_MODEL', 'SMALL_MODEL')
                """) as cursor:
                    rows = await cursor.fetchall()

                    config = {}
                    for row in rows:
                        config[row["key"]] = row["value"]

                    if config:
                        logger.info(
                            f"Loaded model configuration from database: {config}"
                        )
                    else:
                        logger.info("No saved model configuration found in database")

                    return config

        except Exception as e:
            logger.error(f"Failed to load model configuration: {e}")
            return {}
