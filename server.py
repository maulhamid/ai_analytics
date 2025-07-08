import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

from db import PostgreReadOnly

server = Server("local-postgres")


def get_postgres_config():
    """Get PostgreSQL configuration from environment variables."""
    return {
        "host": "localhost",
        "port": 5432,
        "db": "learning_management_system",
        "user": "postgres",
        "password": "postgres",
    }


@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    return [
        Resource(
            uri="postgres://schema",  # type: ignore
            name="Database Schema",
            description="Complete database schema information",
            mimeType="application/json",
        ),
        Resource(
            uri="postgres://tables",  # type: ignore
            name="Database Tables",
            description="List of all tables in the database",
            mimeType="application/json",
        ),
    ]


@server.read_resource()  # type: ignore
async def handle_read_resource(uri: str) -> str:
    """Read a specific resource."""

    config = get_postgres_config()
    db = PostgreReadOnly(**config)

    if uri == "postgres://schema":
        schema = await db._get_db_schema()
        return json.dumps(schema, indent=2, default=str)
    elif uri == "postgres://tables":
        tables = await db.get_tables()
        return json.dumps(tables, indent=2)
    else:
        raise ValueError(f"Unknown resource: {uri}")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="execute_query",
            description="Execute a read-only SQL query on the PostgreSQL database",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL SELECT query to execute",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_schema",
            description="Get the database schema information",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Optional: specific table name to get schema for",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="list_tables",
            description="List all tables in the database",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    config = get_postgres_config()
    db = PostgreReadOnly(**config)

    try:
        if name == "execute_query":
            query = arguments.get("query")
            if not query:
                raise ValueError("Query is required")

            results = await db._execute_query(query)
            return [
                TextContent(
                    type="text", text=json.dumps(results, indent=2, default=str)
                )
            ]

        elif name == "get_schema":
            table_name = arguments.get("table_name")
            schema = await db._get_db_schema()

            if table_name:
                filtered_schema = [
                    item for item in schema if item.get("table_name") == table_name
                ]
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(filtered_schema, indent=2, default=str),
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text", text=json.dumps(schema, indent=2, default=str)
                    )
                ]

        elif name == "list_tables":
            tables = await db.get_tables()
            return [TextContent(type="text", text=json.dumps(tables, indent=2))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        print(f"Error in tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Main entry point for the MCP server."""
    # Validate configuration
    config = get_postgres_config()
    print(
        f"Starting PostgreSQL MCP Server with config: {config['host']}:{config['port']}/{config['db']}"
    )

    # Test connection
    try:
        db = PostgreReadOnly(**config)
        tables = await db.get_tables()
        print(f"Successfully connected to PostgreSQL. Found {len(tables)} tables.")
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        raise

    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="postgres-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(
                        resources_changed=False,
                        tools_changed=False,
                        prompts_changed=False,
                    ),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
