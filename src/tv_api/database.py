"""Database connection and utilities."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from tv_api.config import get_settings


class Database:
    """Database connection pool manager."""

    def __init__(self):
        self.pool: AsyncConnectionPool | None = None

    async def connect(self):
        """Create a connection pool."""
        settings = get_settings()
        self.pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=2,
            max_size=10,
            open=False,
        )
        await self.pool.open()

    async def disconnect(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[psycopg.AsyncConnection, None]:
        """Acquire a connection from the pool."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.connection() as connection:
            # Use dict_row for dictionary-like row results
            connection.row_factory = dict_row
            yield connection


# Global database instance
db = Database()


async def get_db_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Dependency for FastAPI routes to get a database connection."""
    async with db.acquire() as connection:
        yield connection
