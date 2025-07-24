#!/usr/bin/env python3

import requests
import sys
import json
from tabulate import tabulate 
from colorama import init, Fore, Style

init(autoreset=True)

BASE_URL = "http://127.0.0.1:8000/api"
HEADERS = {"Content-Type": "application/json"}

BLUE = Fore.BLUE + Style.BRIGHT
YELLOW = Fore.YELLOW + Style.BRIGHT
GREEN = Fore.GREEN + Style.BRIGHT
RED = Fore.RED + Style.BRIGHT
CYAN = Fore.CYAN + Style.BRIGHT
MAGENTA = Fore.MAGENTA + Style.BRIGHT
RESET = Style.RESET_ALL

def print_jolly(msg, symbol="✨"):
    print(f"{MAGENTA}{symbol} {msg}{RESET}")

def input_colored(prompt):
    return input(f"{BLUE}{prompt}{RESET} ").strip()

def section(title):
    print()
    print(f"{CYAN}{'='*8} {title} {'='*8}{RESET}")

def get_table_names():
    resp = requests.get(f"{BASE_URL}/schemas", headers=HEADERS)
    resp.raise_for_status()
    return list(resp.json().keys())

def get_table_schema(table_name):
    resp = requests.get(f"{BASE_URL}/schema/{table_name}", headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()
    return None

def delete_table(table_name):
    resp = requests.delete(f"{BASE_URL}/schema/{table_name}", headers=HEADERS)
    # Ignore error if not found

def create_table():
    section("CREATE TABLE")
    print_jolly("Let's create a shiny new table! 🥳")
    print(YELLOW + "Enter table name:")
    table_name = input_colored(">>>")
    if table_name == "":
        print(RED + "Cancelled.")
        return
    # Check if exists
    schema = get_table_schema(table_name)
    if schema:
        print_jolly(f"Table '{table_name}' already exists. Deleting and recreating... ♻️")
        delete_table(table_name)
    print(YELLOW + "Enter fields as: name(type) (e.g. id(int), name(text), age(int))")
    nl_definition = input_colored(">>>")
    payload = {
        "table_name": table_name,
        "definition_type": "natural_language",
        "nl_definition": nl_definition
    }
    resp = requests.post(f"{BASE_URL}/create_table", headers=HEADERS, json=payload)
    if resp.status_code == 200:
        print_jolly(f"Table '{table_name}' created! 🎉", "✅")
    else:
        print(RED + f"Error: {resp.text}")

def insert_row():
    section("INSERT DATA")
    tables = get_table_names()
    if not tables:
        print(RED + "No tables available. Please create one first.")
        return
    print(GREEN + "Available tables: " + ", ".join([f"{CYAN}{t}{GREEN}" for t in tables]))
    print(YELLOW + "Enter table name to insert into:")
    table_name = input_colored(">>>")
    schema = get_table_schema(table_name)
    if not schema:
        print(RED + "Table does not exist.")
        return
    fields = [f for f in schema["columns"].keys()]
    print(GREEN + "Fields: " + ", ".join([f"{CYAN}{field}{GREEN}" for field in fields]))
    print(YELLOW + "Enter comma-separated values in the order above:")
    row = input_colored(">>>")
    data_line = ",".join(fields) + "\n" + row
    payload = {
        "table_name": table_name,
        "data": data_line
    }
    resp = requests.post(f"{BASE_URL}/insert_data", headers=HEADERS, json=payload)
    if resp.status_code == 200:
        print_jolly("Inserted successfully! 🍭", "✅")
    else:
        print(RED + f"Error: {resp.text}")

def run_query():
    section("QUERY TABLE")
    tables = get_table_names()
    if not tables:
        print(RED + "No tables created yet.")
        return
    print(GREEN + "Available tables and fields:")
    for t in tables:
        schema = get_table_schema(t)
        cols = ", ".join(f"{CYAN}{k}{RESET}({MAGENTA}{v}{RESET})" for k,v in schema['columns'].items())
        print(f"  {MAGENTA}{t}{RESET}: {cols}")
    print(YELLOW + "Enter natural language question (e.g. 'Show all students'):")
    question = input_colored(">>>")
    print(YELLOW + "Which table to query?")
    table_name = input_colored(">>>")
    payload = {
        "table_name": table_name,
        "question": question
    }
    resp = requests.post(f"{BASE_URL}/query", headers=HEADERS, json=payload)
    try:
        d = resp.json()
        if "results" in d:
            results = d["results"]
            if not results:
                print(RED + "No rows found.")
            else:
                print(GREEN + "\nResult Table:")
                print(tabulate(results, headers="keys", tablefmt="fancy_grid"))
        else:
            print(d)
    except Exception:
        print(RED + f"Error: {resp.text}")

def main():
    print(f"{MAGENTA}=== 💡 NL2SQL Playground CLI 💡 ==={RESET}")
    while True:
        print("\n" + YELLOW + "What do you want to do? (create / insert / query / exit)")
        action = input_colored(">>>").lower()
        if action == "create":
            create_table()
        elif action == "insert":
            insert_row()
        elif action == "query":
            run_query()
        elif action == "exit":
            print_jolly("Goodbye! 👋 See you soon.", "🍀")
            break
        else:
            print(RED + "Invalid command. Please type one of: create, insert, query, exit" + RESET)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n" + RED + "Interrupted, bye!" + RESET)
        sys.exit(0)
