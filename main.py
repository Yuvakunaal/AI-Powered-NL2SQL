from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uvicorn
import logging
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Ensure data and logs directories exist
Path("data/user_uploads").mkdir(parents=True, exist_ok=True)
Path("logs").mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log", mode="a"),
    ]
)
logger = logging.getLogger("root")

# Create FastAPI app
app = FastAPI(
    title="NL2SQL Playground",
    description="A playground for converting natural language to SQL queries",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set more restrictive origins in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from app.routers import create_table, query, schema, insert_data

app.include_router(create_table.router)
app.include_router(query.router)
app.include_router(schema.router)
app.include_router(insert_data.router)

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"field": "->".join(str(loc) for loc in e["loc"][1:]), "msg": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"success": False, "error": "Validation error", "details": errors},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "error": "Internal server error"},
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to NL2SQL Playground!",
        "docs": "/docs",
        "openapi_schema": "/openapi.json"
    }

# App startup/shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("NL2SQL Playground API is starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    from app.llm.openrouter_client import openrouter_client
    # If your client has a close/cleanup, do it here.
    logger.info("NL2SQL Playground API is shutting down...")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
