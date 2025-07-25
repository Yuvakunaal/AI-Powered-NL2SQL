from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
import re

from ..db.dynamic_models import schema_cache, get_db
from ..llm.openrouter_client import openrouter_client
from ..models.request_models import QueryRequest, QueryResponse, ErrorResponse

from sqlalchemy import text

router = APIRouter(prefix="/api", tags=["query"])
logger = logging.getLogger("app.routers.query")

BLOCKED_SQL_KEYWORDS = ["DROP", "DELETE", "UPDATE", "ALTER", "TRUNCATE", "CREATE", "INSERT"]

def validate_sql(sql: str):
    sql_stripped = sql.strip()
    sql_upper = sql_stripped.upper()
    # Only permit SELECT as the first keyword (prevent "SELECT ...; DROP TABLE users;" etc)
    if not sql_upper.startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")
    for keyword in BLOCKED_SQL_KEYWORDS:
        if f" {keyword} " in f" {sql_upper} ":
            raise ValueError(f"Query contains blocked SQL keyword: {keyword}")

def extract_sql_statement(llm_response: str) -> str:
    """
    Extract only the SQL statement from LLM output.
    Strips markdown code blocks, explanations, and extra text.
    """
    text_out = llm_response.strip()
    # Remove markdown code fences if present
    if text_out.startswith("```sql"):
        text_out = text_out[6:].strip()
    if text_out.startswith("```"):
        text_out = text_out[3:].strip()
    if text_out.endswith("```"):
        text_out = text_out[:-3].strip()
    # Remove any leading triple backticks
    text_out = text_out.strip("`").strip()
    # Remove SQL comments (lines starting with --)
    text_out = re.sub(r'--.*?$', '', text_out, flags=re.MULTILINE)
    # Only execute up to first semicolon (ignore trailing text/explanation)
    if ';' in text_out:
        # grab up to AND INCLUDING first semicolon for complete SQL statement
        first, _ = text_out.split(';', 1)
        sql_stmt = first.strip() + ';'
    else:
        # If no semicolon, stop at first blank line or end
        sql_stmt = text_out.split('\n\n', 1).strip()
    return sql_stmt

def execute_sql_query(db: Session, sql: str, params: dict = None):
    try:
        result = db.execute(text(sql), params or {})
        columns = list(result.keys())
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logger.error(f"Error executing SQL query: {str(e)}")
        raise ValueError(f"Error executing query: {str(e)}")

def infer_relationships(table_names):
    schemas = [(tbl, schema_cache.get_table_schema(tbl)) for tbl in table_names]
    rels = []
    for src_tbl, src_schema in schemas:
        for col in src_schema['columns']:
            if col.endswith("_id"):
                candidate_tbl = col[:-3] + "s"  # plural heuristic
                for dst_tbl, dst_schema in schemas:
                    if dst_tbl != src_tbl and "id" in dst_schema['columns']:
                        if candidate_tbl.lower() == dst_tbl.lower():
                            rels.append(f"{src_tbl}.{col} → {dst_tbl}.id")
    return rels

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
        table_names = request.table_names or ([request.table_name] if request.table_name else [])
        if not table_names:
            raise HTTPException(status_code=400, detail="At least one table name must be specified")
        # Check tables exist
        for tbl in table_names:
            if not schema_cache.table_exists(tbl):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Table '{tbl}' not found"
                )

        schemas = {tbl: schema_cache.get_table_schema(tbl) for tbl in table_names}
        rels = infer_relationships(table_names)
        # Compose LLM prompt
        schema_str = "\n".join(
            f"{tbl}({', '.join(f'{col}({typ})' for col, typ in sch['columns'].items())})"
            for tbl, sch in schemas.items()
        )
        rels_str = "; ".join(rels) if rels else "None"
        system_prompt = (
            "You are a world-class expert in generating only valid SQLite SELECT statements from text questions. "
            "Always reply with a single correct SQL SELECT statement, using only the tables and fields provided. "
            "Do NOT provide any explanations, markdown formatting, comments, or additional output."
        )

        prompt = (
            f"{system_prompt}\n\n"
            f"Tables:\n{schema_str}\n"
            f"Relationships:\n{rels_str}\n"
            f"Question:\n{request.question}\n"
            f"SQL:"
        )

        sql_raw = openrouter_client.generate_sql(prompt)
        sql = extract_sql_statement(sql_raw)

        validate_sql(sql)
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
