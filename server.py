import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import asyncpg
from mcp.server.fastmcp import FastMCP


class PostgreReadOnly:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls):
        pool = await asyncpg.create_pool(
            user="postgres",
            password="postgres",
            database="learning_management_system",
            host="localhost",
            port=5432,
        )
        return cls(pool)

    async def disconnect(self):
        await self._pool.close()

    async def _get_db_schema(self) -> list[dict[str, Any]]:
        """
        Get the database schema.
        """
        schema = []
        async with self._pool.acquire() as conn:
            try:
                return await conn.fetch("""
                        SELECT
                            t.table_name,
                            c.column_name,
                            c.data_type,
                            c.is_nullable,
                            c.column_default,
                            (
                                SELECT
                                    CASE
                                        WHEN tc.constraint_type = 'PRIMARY KEY' THEN 'PRIMARY KEY'
                                        WHEN tc.constraint_type = 'FOREIGN KEY' THEN 'FOREIGN KEY'
                                        WHEN tc.constraint_type = 'UNIQUE' THEN 'UNIQUE'
                                        ELSE NULL
                                    END
                                FROM information_schema.table_constraints tc
                                JOIN information_schema.constraint_column_usage ccu
                                    ON tc.constraint_name = ccu.constraint_name
                                WHERE tc.table_name = t.table_name
                                AND ccu.column_name = c.column_name
                                AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
                                LIMIT 1
                            ) AS constraint_type
                        FROM information_schema.tables t
                        JOIN information_schema.columns c
                            ON t.table_name = c.table_name
                            AND t.table_schema = c.table_schema
                        WHERE t.table_schema = 'public'
                            AND t.table_name != 'alembic_version'
                        ORDER BY t.table_name, c.column_name;
                        """)
            except Exception as e:
                print(f"Error executing query: {e}")

        return schema

    def _is_read_only_query(self, query: str) -> bool:
        """
        Validate that the query is a read-only SELECT statement.

        Args:
            query (str): The SQL query to validate.

        Returns:
            bool: True if the query is read-only, False otherwise.
        """
        query = query.strip().lower()
        # Remove comments
        query = re.sub(r"--.*?\n|/\*.*?\*/", "", query, flags=re.DOTALL)

        # Check if query starts with SELECT and does not contain forbidden keywords
        forbidden = [
            "insert",
            "update",
            "delete",
            "drop",
            "create",
            "alter",
            "truncate",
        ]
        return query.startswith("select") and not any(kw in query for kw in forbidden)

    async def _execute_query(self, query: str) -> list[dict[str, Any]]:
        """
        Execute a query and return the results as a list of dictionaries.

        Args:
            query (str): The SQL query to execute.

        Returns:
            list: The results of the query as a list of dictionaries.
        """
        if not self._is_read_only_query(query):
            raise ValueError("Only SELECT queries are allowed for read-only access")

        results = []
        async with self._pool.acquire() as conn:
            try:
                results = await conn.fetch(query)
            except Exception as e:
                raise ValueError(f"Error executing query: {e}")

        return results

    async def get_tables(self) -> list[str]:
        """Get list of table names."""
        async with self._pool.acquire() as conn:
            try:
                results = await conn.fetch("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name != 'alembic_version'
                    ORDER BY table_name;
                """)
                return [row["table_name"] for row in results]
            except Exception:
                raise


@dataclass
class AppContext:
    db: PostgreReadOnly


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    db = await PostgreReadOnly.connect()
    try:
        yield AppContext(db=db)
    finally:
        await db.disconnect()


mcp = FastMCP("local-postgres", dependencies=["asyncpg"], lifespan=app_lifespan)


def get_postgres_config():
    """Get PostgreSQL configuration from environment variables."""
    return {
        "host": "localhost",
        "port": 5432,
        "db": "learning_management_system",
        "user": "postgres",
        "password": "postgres",
    }


@mcp.resource("postgres://schema")
async def get_database_schema() -> str:
    """Get complete database schema information."""
    config = get_postgres_config()
    db = PostgreReadOnly(**config)
    schema = await db._get_db_schema()
    return json.dumps(schema, indent=2, default=str)


@mcp.resource("postgres://tables")
async def get_database_tables() -> str:
    """Get list of all tables in the database."""
    config = get_postgres_config()
    db = PostgreReadOnly(**config)
    tables = await db.get_tables()
    return json.dumps(tables, indent=2)


@mcp.tool("execute_query")
async def execute_query(query: str) -> str:
    """Execute a read-only SQL query on the PostgreSQL database.

    Args:
        query: The SQL SELECT query to execute
    """
    config = get_postgres_config()
    db = PostgreReadOnly(**config)

    try:
        results = await db._execute_query(query)
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        return f"Error executing query: {str(e)}"


@mcp.tool("get_schema")
async def get_schema(table_name: str | None = None) -> str:
    """Get the database schema information.

    Args:
        table_name: Optional specific table name to get schema for
    """
    config = get_postgres_config()
    db = PostgreReadOnly(**config)

    try:
        schema = await db._get_db_schema()

        if table_name:
            filtered_schema = [
                item for item in schema if item.get("table_name") == table_name
            ]
            return json.dumps(filtered_schema, indent=2, default=str)
        else:
            return json.dumps(schema, indent=2, default=str)
    except Exception as e:
        return f"Error getting schema: {str(e)}"


@mcp.tool("list_tables")
async def list_tables() -> str:
    """List all tables in the database."""
    config = get_postgres_config()
    db = PostgreReadOnly(**config)

    try:
        tables = await db.get_tables()
        return json.dumps(tables, indent=2)
    except Exception as e:
        return f"Error listing tables: {str(e)}"


if __name__ == "__main__":
    mcp.run()
