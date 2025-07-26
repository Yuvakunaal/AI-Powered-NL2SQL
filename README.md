
# 🚀 NL2SQL Playground

A full-stack AI-powered tool that allows anyone to **create tables**, **insert data**, and **run SQL queries using natural language**, with both a **modern web interface** and a **colorful CLI**.

---

## 📦 What This Project Does

The goal of NL2SQL Playground is to enable non-technical users and developers alike to:
- Dynamically **create SQL tables** through intuitive UI or CLI
- **Insert values** using smart auto-generated forms
- **Ask natural language questions**, translated to SQL using LLMs
- **View results and the SQL** used transparently
- **Understand query generation** with **Chain-of-Thought explainability**, which provides step-by-step reasoning for every query
- **Optimize performance** with a vectorized semantic cache for instant query responses and reduced API costs

Powered by **OpenRouter API** using **Mistral-7B-Instruct** model for secure and accurate NL-to-SQL transformation.

---

## ✨ Key Features

| Area | Highlights |
|------|------------|
| 🏗 Table Creation | • UI: Choose field count, table name, and set each column's name + datatype via dropdown<br>• Dynamic SQLAlchemy model generation<br>• Auto-delete on duplicate tables |
| 📥 Data Insertion | • UI: Select table → dynamically generated form based on schema fields<br>• CLI: Accepts CSV-style strings for batch insert |
| 📊 Show Tables | • UI displays all created tables, including field names & datatypes |
| ❓ NL-to-SQL Querying | • UI: Pick table → ask NL question → get SQL + result<br>• LLM: OpenRouter + Mistral-7B converts natural language into `SELECT` SQL<br>• Supports complex queries including joins<br>• **Chain-of-Thought explainability**: Returns step-by-step reasoning for each query<br>• Both SQL query and table output are shown |
| 🚀 Optimization | • Vectorized semantic cache for NL2SQL queries<br>• Sub-100ms retrieval for previously seen or similar questions<br>• Reduces API call costs by reusing cached SQL<br>• Enhances user experience with instant responses<br>• Lays groundwork for federated caching and horizontal scaling |
| 🧑‍💻 CLI Support | • Text prompts to create tables, insert data via CSV, and ask NL questions<br>• Built using Colorama and Tabulate for user-friendly experience |
| 🛡 Security | • Blocks destructive SQL (`DROP`, `DELETE`, `UPDATE`, etc.)<br>• All execution uses parameterised `sqlalchemy.text` queries |
| 🧪 Testing | • `test_api.py` covers full create → insert → query flow |

---

## 🧠 How the Web UI Works

### 🏗 Create Table
- Input table name and number of fields
- For each field, enter:
  - Field name
  - Select datatype (e.g., int, text, float)
- On submission, table is created dynamically in SQLite

### 📥 Insert Data
- Pick a table from dropdown
- UI renders form fields based on table schema
- Enter values for each field
- Rows are inserted via backend API

### 📊 Show Tables
- Displays all tables created
- For each table, shows field names and corresponding datatypes

### ❓ Query
- Select a table
- Ask a question like:  
  `"What is the average GPA?"`  
  `"Which students scored above 90 in Math?"`  
- Backend uses OpenRouter → Mistral-7B to convert to SQL:  
  `SELECT AVG(gpa) FROM students;`  
  `SELECT students.name FROM students JOIN scores ON students.id = scores.student_id WHERE scores.math > 90;`
- Supports queries with joins for multi-table operations.
- **Chain-of-Thought explainability**: Provides step-by-step reasoning for how the query was generated.
- UI shows:
  - Generated SQL
  - Output table with results
  - Reasoning block explaining the query generation process.

---

## 💻 Gradio Interface

Run using:

```bash
python gradio_app.py
```

Flow:

1. Launches a web-based UI for interactive usage.
2. Create tables by entering table name, number of fields, and field details.
3. Insert rows using dynamically generated forms based on table schema.
4. Query selected table/s using natural language.
5. View SQL query and output results directly in the web interface.
6. **Chain-of-Thought explainability**: Step-by-step reasoning for query generation is displayed below table output.

---

## ⌨️ CLI Interface

Run using:

```bash
python cli_nl2sql.py
```

Flow:

1. Prompt to enter table name and define fields.
2. Insert rows by entering CSV-style data.
3. Query selected table using natural language.
4. SQL result + output shown directly in terminal.
5. **Chain-of-Thought explainability**: Step-by-step reasoning for query generation is displayed in the terminal.

---

## 🔌 Main API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/create_table` | Create SQL table from NL column description |
| POST   | `/api/insert_data`  | Insert rows into table (`table_name`, `data`) |
| POST   | `/api/query`        | Convert natural language → SQL (including joins) → return results + reasoning block |
| GET    | `/api/schema/{tbl}` | View schema of one table |
| GET    | `/api/schemas`      | List all tables & their schemas |
| DELETE | `/api/schema/{tbl}` | Drop a specific table |

---

## 🛠 Tech Stack

- **FastAPI** – Backend server & routing
- **SQLAlchemy** – ORM for dynamic table creation
- **Pydantic** – Request/response validation
- **SQLite** – Embedded relational DB
- **OpenRouter API** – LLM (Mistral-7B-Instruct) for NL2SQL
- **Gradio** – Beautiful web UI
- **Colorama & Tabulate** – CLI styling
- **Python** – Core logic and services
- **FAISS** – Vector-based semantic cache for query optimization

---

## 🔐 Security Design

- Only allows `SELECT` queries via LLM
- Strips/blocks any risky keywords: `DROP`, `DELETE`, `UPDATE`, etc.
- Queries executed using `sqlalchemy.text()` with parameterization to avoid SQL injection

---

## 🧪 Run the Test Workflow

```bash
python test_api.py
```

Tests the complete flow: table creation → data insertion → NL query → result.

---



## 📝 Skills Demonstrated

- ✅ GEN AI
- ✅ LLM prompt engineering (OpenRouter, Mistral-7B)
- ✅ Dynamic SQL model generation via SQLAlchemy
- ✅ REST API architecture with FastAPI
- ✅ Real-time NL to SQL translation & output (including joins)
- ✅ Full-stack testing and validations
- ✅ Gradio UI & CLI UX with Colorama

---

## 🛠 Tools You Can Use

- **Postman / ThunderClient** – To test REST APIs
- **Gradio** – User-friendly local web dashboard
- **CLI** – For quick interactive terminal-based usage
- **VS Code + SQLite viewer** – To inspect DB manually

---

## 💡 Future Enhancements

- Allow CSV upload for bulk inserts
- Table editing or column renaming
- LLM output confidence and SQL explanation

---

## 👤 Author

Built by Kunaal✨ – Engineering student exploring full-stack GenAI projects.

---
