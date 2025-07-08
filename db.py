import re
from typing import Any

import psycopg
from psycopg.rows import dict_row


class PostgreReadOnly:
    __slots__ = ("_host", "_port", "_db", "_user", "_password", "_conninfo")

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        db: str = "learning_management_system",
        user: str = "postgres",
        password: str = "postgres",
    ) -> None:
        self._host = host
        self._port = port
        self._db = db
        self._user = user
        self._password = password
        self._conninfo = f"dbname={self._db} "
        f"user={self._user} "
        f"password={self._password} "
        f"host={self._host} "
        f"port={self._port}"

    def check_connection(self) -> bool:
        try:
            with psycopg.connect(self._conninfo) as conn:
                conn.execute("SELECT 1")
                return True
        except Exception:
            return False

    async def _get_db_schema(self) -> list[dict[str, Any]]:
        """
        Get the database schema.
        """
        schema = []
        async with await psycopg.AsyncConnection.connect(self._conninfo) as conn:
            try:
                async with conn.cursor(row_factory=dict_row) as cursor:
                    query = """
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
                    """
                    await cursor.execute(query)
                    schema = await cursor.fetchall()
            except Exception as e:
                print(f"error: {e}")

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
        async with await psycopg.AsyncConnection.connect(self._conninfo) as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                try:
                    await cursor.execute(query)  # type: ignore
                    results = await cursor.fetchall()
                except Exception as e:
                    raise ValueError(f"Error executing query: {e}")

        return results

    async def get_tables(self) -> list[str]:
        """Get list of table names."""
        try:
            async with await psycopg.AsyncConnection.connect(self._conninfo) as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                            SELECT table_name
                            FROM information_schema.tables
                            WHERE table_schema = 'public'
                            AND table_name != 'alembic_version'
                            ORDER BY table_name;
                        """)
                    results = await cursor.fetchall()
                    return [row[0] for row in results]
        except Exception:
            raise
