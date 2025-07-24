from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from ..db.dynamic_models import get_dynamic_model, schema_cache, get_db
from ..llm.openrouter_client import openrouter_client
from ..models.request_models import QueryRequest, QueryResponse, ErrorResponse

router = APIRouter(prefix="/api", tags=["query"])
logger = logging.getLogger(__name__)

BLOCKED_SQL_KEYWORDS = ["DROP", "DELETE", "UPDATE", "ALTER", "TRUNCATE", "CREATE", "INSERT"]

from sqlalchemy import text
def execute_sql_query(db: Session, sql: str, params: dict = None):
    try:
        result = db.execute(text(sql), params or {})
        columns = list(result.keys())
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logger.error(f"Error executing SQL query: {str(e)}")
        raise ValueError(f"Error executing query: {str(e)}")

def validate_sql(sql: str):
    sql_upper = sql.upper()
    for keyword in BLOCKED_SQL_KEYWORDS:
        if f" {keyword} " in f" {sql_upper} ":
            raise ValueError(f"Query contains blocked SQL keyword: {keyword}")

@router.post("/query", response_model=QueryResponse, responses={
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
def query_table(
    request: QueryRequest,
    db: Session = Depends(get_db)
):
    try:
        if not schema_cache.table_exists(request.table_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table '{request.table_name}' not found"
            )
        schema = schema_cache.get_table_schema(request.table_name)
        if not schema:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not retrieve schema for table '{request.table_name}'"
            )

        # Build LLM prompt
        schema_str = ", ".join(
            f"{col_name}({col_type})" for col_name, col_type in schema['columns'].items()
        )
        prompt = (
            f"Schema: {request.table_name}({schema_str})\n"
            f"Question: {request.question}\n"
            "Generate a SQL query to answer the question. Only return the SQL, no explanations or markdown formatting.\n"
            "SQL: "
        )

        # Get the SQL from the LLM (synchronous)
        sql = openrouter_client.generate_sql(prompt)
        sql = sql.strip()

        # Remove triple backticks or SQL fencing if present
        if sql.startswith("```sql"):
            sql = sql[6:].strip()
        if sql.startswith("```"):
            sql = sql[3:].strip()
        if sql.endswith("```"):
            sql = sql[:-3].strip()

        try:
            validate_sql(sql)
        except ValueError as e:
            logger.warning(f"Blocked SQL query: {sql}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Generated query is not allowed: {str(e)}"
            )

        results = execute_sql_query(db, sql)
        return {
            "sql": sql,
            "results": results,
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing query")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )
