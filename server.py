import json

# from typing import Any
from mcp.server.fastmcp import FastMCP

from db import PostgreReadOnly

# server = Server("local-postgres")
mcp = FastMCP("local-postgres", dependencies=["psycopg"])


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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
async def list_tables() -> str:
    """List all tables in the database."""
    config = get_postgres_config()
    db = PostgreReadOnly(**config)

    try:
        tables = await db.get_tables()
        return json.dumps(tables, indent=2)
    except Exception as e:
        return f"Error listing tables: {str(e)}"


def main():
    """Main entry point for the FastMCP server."""
    config = get_postgres_config()
    print(
        f"Starting PostgreSQL FastMCP Server with config: {config['host']}:{config['port']}/{config['db']}"
    )

    try:
        db = PostgreReadOnly(**config)
        status = db.check_connection()
        print(f"Connection to postgre is {status}")
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        raise

    # Run the server
    mcp.run()


if __name__ == "__main__":
    main()
