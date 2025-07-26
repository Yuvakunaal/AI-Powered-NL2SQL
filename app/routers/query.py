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

def extract_sql_statement(llm_response: str) -> str:
    text_out = llm_response.strip()
    # Remove markdown code fences if present
    if text_out.startswith("```sql"):
        text_out = text_out[6:].strip()
    if text_out.startswith("```"):
        text_out = text_out[3:].strip()
    if text_out.endswith("```"):
        text_out = text_out[:-3].strip()
    text_out = text_out.strip("`").strip()
    text_out = re.sub(r'--.*?$', '', text_out, flags=re.MULTILINE)
    # Only keep up to first semicolon
    if ';' in text_out:
        first, _ = text_out.split(';', 1)
        sql_stmt = first.strip() + ';'
    else:
        sql_stmt = text_out.split('\n\n', 1)[0].strip()
    return sql_stmt

def extract_explanation_and_sql(text):
    text = text.strip()
    # Case 1: Explanation: first, then SQL:
    match = re.search(r"(?i)explanation\s*:?\s*(.*?)\s*sql\s*:?\s*(.*)", text, re.DOTALL)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    # Case 2: SQL first, then Explanation:
    if "Explanation:" in text:
        parts = text.split("Explanation:", 1)
        sql = parts[0].strip()
        explanation = parts[1].strip()
        return explanation, sql
    # If neither marker, treat all as SQL.
    return "", text


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
        # <-- SET EXPLAIN FLAG FIRST!
        explain = getattr(request, "explain", False)
        cache_hit = semantic_cache.search(request.question, explain_flag=explain)
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
        explain = getattr(request, "explain", False)
        if explain:
            system_prompt = (
                "You are a world-class SQLite expert. Convert user's question into valid, efficient SQLite SELECT statements, "
                "using only the provided schema.\n\n"
                "Instructions:\n"
                "1. First, explain your reasoning step-by-step for mapping the question to SQL.\n"
                "2. Then output only the correct SQLite SELECT query.\n"
                "3. Format:\nExplanation:<YOUR EXPLANATION>\nSQL:<YOUR SQL>"
            )
        else:
            system_prompt = (
                "You are a world-class SQLite expert. Convert the user’s question to a valid SQLite SELECT statement ONLY, "
                "using only the schema provided. Output only the final SQL statement and nothing else."
            )

        prompt = (
            f"{system_prompt}\n\n"
            f"Tables:\n{schema_str}\n"
            f"Relationships:\n{rels_str}\n"
            f"Question:\n{request.question}\n"
            + ("Explanation:\nSQL:" if explain else "SQL:")
        )

        sql_raw = openrouter_client.generate_sql(prompt)
        logger.info(f"LLM RAW RESPONSE: {repr(sql_raw)}")

        if explain:
            explanation, sql = extract_explanation_and_sql(sql_raw)
        else:
            explanation, sql = None, sql_raw.strip()

        sql = extract_sql_statement(sql)
        validate_sql(sql)
        results = execute_sql_query(db, sql)
        if explanation:
            explanation = re.sub(r"[\s\}\]\)\>]+$", "", explanation.strip())
            
        semantic_cache.add(request.question, sql, results, explanation if explain else None, explain_flag=explain)
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
