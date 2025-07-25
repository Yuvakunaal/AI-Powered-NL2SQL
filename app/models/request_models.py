from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, Union, Dict, List, Any
from enum import Enum

class TableDefinitionType(str, Enum):
    """Types of table definitions supported."""
    NATURAL_LANGUAGE = "natural_language"
    CSV = "csv"

class CreateTableRequest(BaseModel):
    """Request model for creating a new table."""
    table_name: str = Field(..., description="Name of the table to create")
    definition_type: TableDefinitionType = Field(
        default=TableDefinitionType.NATURAL_LANGUAGE,
        description="Type of definition provided"
    )
    nl_definition: Optional[str] = Field(
        None,
        description="Natural language description of the table structure. Example: 'id(int), name(text), age(int)'"
    )
    csv_data: Optional[str] = Field(
        None,
        description="CSV data as a string. First row should be column names."
    )
    
    @validator('nl_definition', always=True)
    def validate_definition(cls, v, values):
        if values.get('definition_type') == TableDefinitionType.NATURAL_LANGUAGE and not v:
            raise ValueError("nl_definition is required when definition_type is 'natural_language'")
        return v
    
    @validator('csv_data', always=True)
    def validate_csv(cls, v, values):
        if values.get('definition_type') == TableDefinitionType.CSV and not v:
            raise ValueError("csv_data is required when definition_type is 'csv'")
        return v

class InsertDataRequest(BaseModel):
    """Request model for inserting data into a table."""
    table_name: str = Field(..., description="Name of the table to insert data into")
    data: str = Field(..., description="CSV formatted data to insert")

class QueryRequest(BaseModel):
        """Request model for querying one or more tables with natural language."""
        table_names: Optional[List[str]] = Field(None, description="Names of the tables to query")
        table_name: Optional[str] = Field(None, description="Single table (legacy, for backward compatibility)")
        question: str = Field(..., description="Natural language question to convert to SQL")

        # For backward compatibility:
        @validator('table_names', pre=True, always=True)
        def ensure_table_names(cls, v, values):
            # Automatic upgrade: if table_name provided, make table_names = [table_name]
            if v is None and 'table_name' in values and values['table_name']:
                return [values['table_name']]
            return v

        class Config:
            schema_extra = {
                "example": {
                    "table_names": ["students", "colleges"],
                    "question": "Show each student and their college name"
                }
            }
    
class QueryResponse(BaseModel):
    """Response model for query results."""
    sql: str = Field(..., description="The SQL query that was generated")
    results: List[Dict[str, Any]] = Field(..., description="Query results as a list of dictionaries")
    success: bool = Field(True, description="Whether the query was successful")
    error: Optional[str] = Field(None, description="Error message if the query failed")

class TableSchemaResponse(BaseModel):
    """Response model for table schema."""
    table_name: str = Field(..., description="Name of the table")
    columns: Dict[str, str] = Field(..., description="Dictionary of column names to their types")
    created_at: Optional[str] = Field(None, description="When the table was created")

class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = Field(False, description="Always false for error responses")
    error: str = Field(..., description="Error message")
    
    @classmethod
    def from_exception(cls, e: Exception):
        """Create an error response from an exception."""
        return cls(error=str(e))
