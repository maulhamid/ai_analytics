from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., description="The SQL query to execute")


class SchemaRequest(BaseModel):
    table_name: str | None = Field(
        None, description="Optional table name to get schema for"
    )
