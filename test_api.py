#!/usr/bin/env python3
"""
Test script for the NL2SQL Playground API.

This script tests the core functionality of the API by:
1. Creating a table from natural language definition
2. Inserting data into the table
3. Querying the table using natural language
4. Retrieving the table schema

Make sure the API server is running before executing this script.
"""

import os
import sys
import json
import requests
from typing import Dict, Any, List, Optional

# Configuration
BASE_URL = "http://127.0.0.1:8000"
HEADERS = {"Content-Type": "application/json"}

def print_step(step: str) -> None:
    """Print a step header for better test output readability."""
    print(f"\n{'='*50}")
    print(f"STEP: {step}")
    print(f"{'='*50}")

def make_request(method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
    """Make an HTTP request to the API and handle the response."""
    # Add /api prefix to all endpoints
    url = f"{BASE_URL}/api/{endpoint}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=HEADERS)
        elif method.upper() == "POST":
            response = requests.post(url, headers=HEADERS, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=HEADERS)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request to {url}: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        sys.exit(1)

def test_create_table() -> str:
    """Test creating a table from natural language."""
    print_step("1. Creating a table from natural language")
    
    table_name = "students"
    
    # First, try to delete the table if it exists
    try:
        # First check if table exists
        try:
            schema = make_request("GET", f"schema/{table_name}")
            if schema:
                # Table exists, try to delete it
                try:
                    delete_result = make_request("DELETE", f"schema/{table_name}")
                    print(f"Deleted existing table: {json.dumps(delete_result, indent=2)}")
                    # Small delay to ensure cleanup completes
                    import time
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Warning: Could not delete existing table: {str(e)}")
        except Exception as e:
            # Table doesn't exist, which is fine
            pass
    except Exception as e:
        print(f"Warning: Error checking for existing table: {str(e)}")
    
    # Now create the table
    payload = {
        "table_name": table_name,
        "definition_type": "natural_language",
        "nl_definition": "id(int), name(text), age(int), gpa(float)"
    }
    
    print(f"Creating table with payload: {json.dumps(payload, indent=2)}")
    
    try:
        result = make_request("POST", "create_table", payload)
        print(f"Table created successfully: {json.dumps(result, indent=2)}")
        
        # Verify the table was created
        try:
            schema = make_request("GET", f"schema/{table_name}")
            print(f"Verified table schema: {json.dumps(schema, indent=2)}")
        except Exception as e:
            print(f"Warning: Could not verify table creation: {str(e)}")
            
        return table_name
        
    except Exception as e:
        if "already exists" in str(e):
            print(f"Table '{table_name}' already exists, continuing with existing table")
            return table_name
        print(f"Error creating table: {str(e)}")
        raise

def test_insert_data(table_name: str) -> None:
    print_step("2. Inserting data into the table")
    test_data = {
        "table_name": table_name,
        "data": "name,age,gpa\nAlice,20,3.8\nBob,22,3.5\nCharlie,21,3.9\nDiana,23,3.7\nEve,20,3.6"
    }
    payload = {
        "table_name": table_name,
        "data": test_data['data']
    }
    print(f"Inserting test data into table '{table_name}'")
    try:
        response = requests.post(
            f"{BASE_URL}/api/insert_data",
            headers=HEADERS,
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        print(f"Data inserted successfully: {json.dumps(result, indent=2)}")
    except requests.exceptions.RequestException as e:
        print(f"Error inserting data: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        sys.exit(1)


def test_query(table_name: str) -> None:
    """Test querying the table using natural language."""
    print_step("3. Querying the table with natural language")
    
    test_queries = [
        "Show all students",
        "Find students with GPA above 3.7",
        "What is the average GPA?",
        "Show students ordered by age"
    ]
    
    for query_text in test_queries:
        print(f"\nQuery: {query_text}")
        payload = {
            "table_name": table_name,
            "question": query_text
        }
        
        result = make_request("POST", "query", payload)
        print(f"Generated SQL: {result.get('sql')}")
        print(f"Results: {json.dumps(result.get('results'), indent=2)}")

def test_get_schema(table_name: str) -> None:
    """Test retrieving the table schema."""
    print_step("4. Retrieving table schema")
    
    result = make_request("GET", f"schema/{table_name}")
    print(f"Schema for table '{table_name}':")
    print(json.dumps(result, indent=2))

def test_list_schemas() -> None:
    """Test listing all table schemas."""
    print_step("5. Listing all table schemas")
    
    result = make_request("GET", "schemas")
    print("All table schemas:")
    print(json.dumps(result, indent=2))

def main():
    """Main test function."""
    print("="*50)
    print("NL2SQL Playground - Integration Test")
    print("="*50)
    
    try:
        # Test creating a table
        table_name = test_create_table()
        
        # Test inserting data
        test_insert_data(table_name)
        
        # Test querying with natural language
        test_query(table_name)
        
        # Test getting the table schema
        test_get_schema(table_name)
        
        # Test listing all schemas
        test_list_schemas()
        
        print("\n" + "="*50)
        print("✅ All tests completed successfully!")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
