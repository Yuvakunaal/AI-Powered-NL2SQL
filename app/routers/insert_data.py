from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
import csv
import io
import re
from pydantic import BaseModel
from datetime import datetime, date

from ..db.dynamic_models import get_dynamic_model, schema_cache, get_db
from ..models.request_models import ErrorResponse

router = APIRouter(prefix="/api", tags=["data"])
logger = logging.getLogger(__name__)

MAX_ROWS = 100

# New: Pydantic model
class InsertDataRequest(BaseModel):
    table_name: str
    data: str # CSV as string

def clean_column_name(name: str) -> str:
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    name = re.sub(r'^[0-9_]+', '', name)
    return name.lower()

def parse_csv_data(csv_data: str):
    try:
        csv_file = io.StringIO(csv_data)
        reader = csv.DictReader(csv_file)
        rows = [dict(row) for row in reader]
        if not rows:
            raise ValueError("CSV data is empty")
        if len(rows) > MAX_ROWS:
            raise ValueError(f"CSV contains too many rows (max {MAX_ROWS})")
        return rows
    except Exception as e:
        logger.error(f"Error parsing CSV data: {str(e)}")
        raise ValueError(f"Invalid CSV data: {str(e)}")

@router.post("/insert_data", responses={
    200: {"description": "Data inserted successfully"},
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
async def insert_data(
    request: InsertDataRequest,
    db: Session = Depends(get_db)
):
    try:
        table_name = request.table_name
        csv_data = request.data
        if not schema_cache.table_exists(table_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table '{table_name}' not found"
            )
        schema = schema_cache.get_table_schema(table_name)
        if not schema:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not retrieve schema for table '{table_name}'"
            )
        rows = parse_csv_data(csv_data)
        model_class = get_dynamic_model(table_name)
        if not model_class:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not load model for table '{table_name}'"
            )
        expected_columns = set(schema['columns'].keys())
        inserted_count = 0
        # Normalize schema keys
        normalized_columns = {clean_column_name(k): k for k in schema["columns"].keys()}

        for row in rows:
            try:
                clean_row = {}
                for col_name, value in row.items():
                    clean_col_name = clean_column_name(col_name)
                    actual_col_name = normalized_columns.get(clean_col_name)

                    if actual_col_name is None:
                        continue

                    clean_value = value.strip() if isinstance(value, str) else value
                    if clean_value == "":
                        clean_value = None

                    # Optional: Date parsing (only if actual column is datetime/date)
                    if schema["columns"][actual_col_name] in ["datetime", "date"] and clean_value:
                        try:
                            clean_value = date.fromisoformat(clean_value)
                        except Exception as e:
                            logger.warning(f"Could not parse {actual_col_name} '{clean_value}': {e}")
                            clean_value = None

                    clean_row[actual_col_name] = clean_value

                if not clean_row:
                    logger.warning(f"No matching columns found in row: {row}")
                    continue

                db_row = model_class(**clean_row)
                db.add(db_row)
                inserted_count += 1

            except Exception as e:
                logger.error(f"Error inserting row {row}: {str(e)}")
                continue

        db.commit()
        return {
            "success": True,
            "message": f"Successfully inserted {inserted_count} row(s) into '{table_name}'",
            "inserted_count": inserted_count
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Error inserting data")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to insert data: {str(e)}"
        )
