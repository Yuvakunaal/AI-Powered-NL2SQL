from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import re
import pandas as pd
import logging

from ..db.dynamic_models import create_dynamic_model, schema_cache, get_db
from ..models.request_models import CreateTableRequest, TableSchemaResponse, ErrorResponse

router = APIRouter(prefix="/api", tags=["tables"])
logger = logging.getLogger(__name__)

def parse_natural_language_definition(nl_definition: str):
    columns = {}
    parts = re.split(r',\s*(?![^()]*\))', nl_definition.strip())
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*([a-zA-Z]+)\s*\)$', part)
        if not match:
            raise ValueError(f"Invalid column definition: {part}")
        col_name, col_type = match.groups()
        columns[col_name] = col_type.lower()
    if not columns:
        raise ValueError("No valid column definitions found")
    return columns

def infer_schema_from_csv(csv_data: str):
    try:
        df = pd.read_csv(pd.compat.StringIO(csv_data), nrows=10)
        columns = {}
        for col in df.columns:
            clean_col = re.sub(r'[^a-zA-Z0-9_]', '_', str(col)).strip('_')
            if not clean_col:
                clean_col = f"column_{len(columns) + 1}"
            dtype = str(df[col].dtype)
            if 'int' in dtype:
                col_type = 'int'
            elif 'float' in dtype:
                col_type = 'float'
            elif 'datetime' in dtype:
                col_type = 'datetime'
            else:
                col_type = 'text'
            columns[clean_col] = col_type
        return columns
    except Exception as e:
        logger.error(f"Error inferring schema from CSV: {str(e)}")
        raise ValueError(f"Failed to parse CSV data: {str(e)}")

@router.post("/create_table", response_model=TableSchemaResponse, responses={
    400: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
async def create_table(
    request: CreateTableRequest,
    db: Session = Depends(get_db)
):
    try:
        if schema_cache.table_exists(request.table_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Table '{request.table_name}' already exists"
            )

        # Parse the table definition
        if request.definition_type == "natural_language":
            columns = parse_natural_language_definition(request.nl_definition)
        else:
            columns = infer_schema_from_csv(request.csv_data)
        # Create the table
        model_class = create_dynamic_model(request.table_name, columns)

        # If CSV, insert data
        if request.definition_type == "csv" and request.csv_data:
            lines = request.csv_data.strip().split('\n')[1:]
            for line in lines:
                if not line.strip():
                    continue
                values = [v.strip() for v in line.split(',')]
                if len(values) != len(columns):
                    logger.warning(f"Skipping malformed row: {line}")
                    continue
                row_data = {col: values[i] for i, col in enumerate(columns.keys())}
                db_row = model_class(**row_data)
                db.add(db_row)
            db.commit()

        schema = schema_cache.get_table_schema(request.table_name)
        return {
            "table_name": request.table_name,
            "columns": schema["columns"],
            "created_at": schema["created_at"]
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Error creating table")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create table: {str(e)}"
        )
