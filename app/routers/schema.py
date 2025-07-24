from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from ..db.dynamic_models import schema_cache, get_db, get_dynamic_model, engine, Base
from ..models.request_models import TableSchemaResponse, ErrorResponse

router = APIRouter(prefix="/api", tags=["schema"])
logger = logging.getLogger(__name__)

@router.get("/schema/{table_name}", response_model=TableSchemaResponse, responses={
    404: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
async def get_table_schema(
    table_name: str,
    db: Session = Depends(get_db)
):
    try:
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
        return {
            "table_name": table_name,
            "columns": schema["columns"],
            "created_at": schema.get("created_at")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving schema for table '{table_name}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve schema: {str(e)}"
        )

@router.get("/schemas", response_model=dict, responses={
    500: {"model": ErrorResponse}
})
async def list_schemas(
    db: Session = Depends(get_db)
):
    try:
        schemas = {}
        for table_name, schema in schema_cache.cache.items():
            schemas[table_name] = {
                "columns": schema["columns"],
                "created_at": schema.get("created_at", "unknown")
            }
        return schemas
    except Exception as e:
        logger.exception("Error listing schemas")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list schemas: {str(e)}"
        )

@router.delete("/schema/{table_name}", responses={
    200: {"description": "Table deleted successfully"},
    404: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
async def delete_table(
    table_name: str,
    db: Session = Depends(get_db)
):
    try:
        if not schema_cache.table_exists(table_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table '{table_name}' not found"
            )
        model = get_dynamic_model(table_name)
        if model:
            model.__table__.drop(bind=engine, checkfirst=True)
        if table_name in Base.metadata.tables:
            Base.metadata.remove(Base.metadata.tables[table_name])
        if table_name.lower() in schema_cache.cache:
            del schema_cache.cache[table_name.lower()]
            schema_cache.save_cache()
        db.commit()
        return {"success": True, "message": f"Table '{table_name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error dropping table '{table_name}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to drop table '{table_name}': {str(e)}"
        )
