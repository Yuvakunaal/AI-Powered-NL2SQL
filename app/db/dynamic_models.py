from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, Date, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Type, Union
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQLite database file path
DATABASE_URL = "sqlite:///./nl2sql.db"

# Create SQLAlchemy engine and session
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()
Base = declarative_base(metadata=metadata)

# Type mapping from string to SQLAlchemy types
TYPE_MAPPING = {
    'int': Integer,
    'integer': Integer,
    'str': String,
    'text': Text,
    'float': Float,
    'date': Date,
    'datetime': DateTime,
}

class SchemaCache:
    """Manages the schema cache for dynamic tables."""
    
    def __init__(self, cache_file: str = 'data/schema_cache.json'):
        self.cache_file = cache_file
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load the schema cache from file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Invalid cache file, starting with empty cache")
        return {}
    
    def save_cache(self) -> None:
        """Save the current schema cache to file."""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get the schema for a specific table."""
        return self.cache.get(table_name.lower())
    
    def update_table_schema(self, table_name: str, columns: Dict[str, str]) -> None:
        """Update the schema for a specific table."""
        table_name = table_name.lower()
        self.cache[table_name] = {
            'columns': columns,
            'created_at': datetime.utcnow().isoformat()
        }
        self.save_cache()
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the cache."""
        return table_name.lower() in self.cache

# Global schema cache instance
schema_cache = SchemaCache()

def get_db():
    """Dependency to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_dynamic_model(table_name: str, columns: Dict[str, str]) -> Type[Base]:
    """
    Dynamically create a SQLAlchemy model for a table.
    
    Args:
        table_name: Name of the table
        columns: Dictionary of column names to SQL types
        
    Returns:
        Dynamically generated SQLAlchemy model class
    """
    # Convert column definitions to SQLAlchemy Column objects
    table_columns = {
        'id': Column(Integer, primary_key=True, index=True),
        '__tablename__': table_name.lower(),
        '__table_args__': {'extend_existing': True}
    }
    
    for col_name, col_type in columns.items():
        if col_name.lower() == 'id':
            continue  # Skip ID as we already added it
            
        # Get the SQLAlchemy column type
        sql_type = TYPE_MAPPING.get(col_type.lower(), String)
        table_columns[col_name] = Column(sql_type)
    
    # Create the model class dynamically
    model_class = type(
        table_name.capitalize(),
        (Base,),
        table_columns
    )
    
    # Create the table in the database
    try:
        model_class.__table__.create(bind=engine, checkfirst=True)
        # Update the schema cache
        schema_cache.update_table_schema(table_name, columns)
        logger.info(f"Created table: {table_name} with columns: {columns}")
    except Exception as e:
        logger.error(f"Error creating table {table_name}: {str(e)}")
        raise
    
    return model_class

def get_dynamic_model(table_name: str) -> Optional[Type[Base]]:
    """
    Get a dynamic model for an existing table.
    
    Args:
        table_name: Name of the table
        
    Returns:
        SQLAlchemy model class or None if table doesn't exist
    """
    if not schema_cache.table_exists(table_name):
        return None
        
    # Get the schema from cache
    schema = schema_cache.get_table_schema(table_name)
    if not schema:
        return None
    
    # Create the model dynamically
    return create_dynamic_model(table_name, schema['columns'])

def init_db():
    """Initialize the database and create tables."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")

# Initialize the database when this module is imported
init_db()
