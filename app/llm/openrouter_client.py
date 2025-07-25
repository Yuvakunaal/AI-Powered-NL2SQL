import os
import requests
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "mistralai/mistral-7b-instruct"

class OpenRouterClient:
    """Client for interacting with the OpenRouter API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the OpenRouter client.
        
        Args:
            api_key: OpenRouter API key. If not provided, will try to get from OPENROUTER_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key not provided and OPENROUTER_API_KEY environment variable not set")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Ensure logs directory exists
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
    
    def generate_sql(self, prompt: str, model: str = DEFAULT_MODEL) -> str:
        """Generate SQL from natural language prompt.
        
        Args:
            prompt: Natural language prompt describing the SQL to generate
            model: The model to use for generation (default: mistralai/mistral-7b-instruct)
            
        Returns:
            Generated SQL query as a string
        """
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a SQLite expert. Given any table schema and a natural language question, respond with the most accurate and efficient SQLite query. Always output SQLite-compliant SQLite — no explanation, no markdown, and no comments."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,  # Lower temperature for more deterministic SQL
            "max_tokens": 1000,
        }
        
        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            sql = result["choices"][0]["message"]["content"].strip()
            
            # Clean up the SQL (remove markdown code blocks if present)
            sql = sql.strip()
            if sql.startswith("```sql"):
                sql = sql[6:]
            if sql.endswith("```"):
                sql = sql[:-3]
            sql = sql.strip()
            
            # Log the interaction
            self._log_interaction(prompt, sql, model)
            
            return sql
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error from OpenRouter: {str(e)}")
            raise Exception(f"Failed to generate SQL: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating SQL: {str(e)}")
            raise Exception(f"Failed to generate SQL: {str(e)}")
    
    def _log_interaction(self, prompt: str, sql: str, model: str) -> None:
        """Log the prompt and generated SQL to a file."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "prompt": prompt,
            "sql": sql
        }
        
        log_file = self.logs_dir / "prompt_history.log"
        
        # Append to log file
        with open(log_file, "a") as f:
            f.write(f"[{log_entry['timestamp']}\n")
            f.write(f"Model: {model}\n")
            f.write(f"Prompt: {prompt}\n")
            f.write(f"Generated SQL: {sql}\n")
            f.write("-" * 80 + "\n\n")

# Global instance for easy import
openrouter_client = OpenRouterClient()

# Example usage:
# sql = openrouter_client.generate_sql("Schema: users(id, name, age)\nQuestion: Find all users older than 30")
# print(sql)  # Output: SELECT * FROM users WHERE age > 30
