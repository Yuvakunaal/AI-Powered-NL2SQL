from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
import re

from ..db.dynamic_models import schema_cache, get_db
from ..llm.openrouter_client import openrouter_client
from ..models.request_models import QueryRequest, QueryResponse, ErrorResponse
from sqlalchemy import text
from app.utils.semantic_cache import semantic_cache

router = APIRouter(prefix="/api", tags=["query"])
logger = logging.getLogger("app.routers.query")

BLOCKED_SQL_KEYWORDS = ["DROP", "DELETE", "UPDATE", "ALTER", "TRUNCATE", "CREATE", "INSERT"]

def validate_sql(sql: str):
    sql_stripped = sql.strip()
    sql_upper = sql_stripped.upper()
    if not sql_upper.startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")
    for keyword in BLOCKED_SQL_KEYWORDS:
        if f" {keyword} " in f" {sql_upper} ":
            raise ValueError(f"Query contains blocked SQL keyword: {keyword}")
import re

def extract_sql_statement(text):
    """
    Extract complete SQL statement including multi-line JOINs, WHERE clauses, etc.
    """
    if not text:
        return ""
    
    text = text.strip()
    
    # Remove markdown
    text = re.sub(r"```.*?\n", "", text)
    text = re.sub(r"```\s*$", "", text)
    
    # Split at "Explanation:" and take only SQL part
    if "Explanation:" in text:
        text = text.split("Explanation:")[0].strip()
    
    # Extract complete multi-line SQL statement
    lines = text.split('\n')
    sql_lines = []
    in_sql = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.upper().startswith('SELECT'):
            in_sql = True
            sql_lines.append(line)
        elif in_sql and line:
            sql_lines.append(line)
            # Stop when we hit semicolon
            if ';' in line:
                break
    
    if sql_lines:
        complete_sql = '\n'.join(sql_lines)
        # Clean up and ensure semicolon
        if not complete_sql.strip().endswith(';'):
            complete_sql += ';'
        return complete_sql
    
    return ""



def extract_explanation_and_sql(text):
    """
    Parse LLM output for SQL first, then Explanation
    """
    text = text.strip()
    
    # Split at "Explanation:" (case insensitive)
    if "Explanation:" in text:
        parts = text.split("Explanation:", 1)
        sql_part = parts[0].strip()
        explanation_part = parts[1].strip()
        return explanation_part, sql_part
    
    # If no explanation found, treat all as SQL
    return "", text.strip()



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
                candidate_tbl = col[:-3] + "s"
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
        for tbl in table_names:
            if not schema_cache.table_exists(tbl):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Table '{tbl}' not found"
                )

        cache_hit = semantic_cache.search(request.question)
        if cache_hit:
            logger.info("Semantic cache HIT for NL query")
            return {
                "sql": cache_hit["sql"],
                "results": cache_hit["result"],
                "explanation": cache_hit.get("explanation", "(from cache)"),
                "success": True,
            }

        schemas = {tbl: schema_cache.get_table_schema(tbl) for tbl in table_names}
        rels = infer_relationships(table_names)

        schema_str = "\n".join(
            f"{tbl}({', '.join(f'{col}({typ})' for col, typ in sch['columns'].items())})"
            for tbl, sch in schemas.items()
        )
        rels_str = "; ".join(rels) if rels else "None"

        # Always prompt for explanation + SQL
        system_prompt = (
            "You are a world-class SQLite expert. Convert the user's question to an efficient SQLite SELECT. "
            "First, explain your reasoning step-by-step for mapping their question to SQL. "
            "Then output the correct SQLite SELECT query. "
            "Format:\nExplanation:\nSQL:"
        )

        prompt = (
            f"{system_prompt}\n\n"
            f"Tables:\n{schema_str}\n"
            f"Relationships:\n{rels_str}\n"
            f"Question:\n{request.question}\n"
            "Explanation:\nSQL:"
        )

        sql_raw = openrouter_client.generate_sql(prompt)
        logger.info(f"LLM RAW RESPONSE: {repr(sql_raw)}")
        explanation, sql_section = extract_explanation_and_sql(sql_raw)
        sql = extract_sql_statement(sql_section)
        print(f"\nTO VALIDATE: {repr(sql)}")
        validate_sql(sql)
        results = execute_sql_query(db, sql)
        if explanation:
            explanation = re.sub(r"[\s\}\]\)\>]+$", "", explanation.strip())

        semantic_cache.add(request.question, sql, results, explanation)

        return {
            "sql": sql,
            "results": results or [],
            "explanation": explanation or "",
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
