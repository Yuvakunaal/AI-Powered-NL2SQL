import gradio as gr
import requests

API_BASE = "http://127.0.0.1:8000/api"
HEADERS = {"Content-Type": "application/json"}

# API helpers

def get_tables():
    try:
        resp = requests.get(f"{API_BASE}/schemas")
        if resp.status_code != 200:
            return {}
        return resp.json()
    except Exception:
        return {}

def get_schema(table_name):
    try:
        resp = requests.get(f"{API_BASE}/schema/{table_name}")
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None

def create_table(table_name, field_defs):
    nl_def = ', '.join(f"{name}({dtype})" for name, dtype in field_defs if name.strip())
    payload = {
        "table_name": table_name.strip(),
        "definition_type": "natural_language",
        "nl_definition": nl_def
    }
    requests.delete(f"{API_BASE}/schema/{table_name}")
    resp = requests.post(f"{API_BASE}/create_table", headers=HEADERS, json=payload)
    if resp.status_code == 200:
        return True, "Table created successfully!"
    else:
        try:
            return False, resp.json().get("error", resp.text)
        except Exception:
            return False, resp.text

def insert_row(table, values):
    schema = get_schema(table)
    if not schema:
        return False, f"Table '{table}' not found."
    cols = [k for k in schema["columns"].keys()]
    # Note: len(values) might be larger if previous widgets are hanging around, zip it for safety
    use_values = values[:len(cols)]
    csv_str = ','.join(cols) + "\n" + ','.join(str(v) for v in use_values)
    payload = {
        "table_name": table,
        "data": csv_str
    }
    resp = requests.post(f"{API_BASE}/insert_data", headers=HEADERS, json=payload)
    if resp.status_code == 200:
        return True, "Inserted!"
    else:
        try:
            return False, resp.json().get("error", resp.text)
        except Exception:
            return False, resp.text

def run_query(table, nl_query):
    payload = {
        "table_name": table,
        "question": nl_query
    }
    resp = requests.post(f"{API_BASE}/query", headers=HEADERS, json=payload)
    if resp.status_code == 200:
        d = resp.json()
        return d.get("sql", ""), d.get("results", []), None
    else:
        try:
            err = resp.json().get("error")
        except Exception:
            err = resp.text
        return "", [], err

# Gradio UI tabs/app logic

def build_create_tab():
    dtype_opts = ["int", "float", "text", "datetime"]
    with gr.Tab("Create Table"):
        table_name = gr.Textbox(label="Table Name", interactive=True)
        with gr.Row():
            n_fields = gr.Number(label="Number of Fields", minimum=1, value=3, step=1, interactive=True)
            refresh_fields = gr.Button("Set Field Count 🔄")
        fields_box = gr.Column()
        fields = []
        for i in range(1, 11):
            with fields_box:
                with gr.Row(visible=False) as r:
                    fname = gr.Textbox(label=f"Field {i} Name", interactive=True)
                    ftype = gr.Dropdown(dtype_opts, value="text", label="Type", interactive=True)
                    fields.append((r, fname, ftype))
        create_btn = gr.Button("Create Table 🚀", interactive=True)
        output = gr.Markdown()

    def _adjust_fields(count):
        vis = []
        for idx, (r, _, _) in enumerate(fields):
            vis.append(gr.update(visible=(idx < count)))
        return vis

    n_fields.change(_adjust_fields, n_fields, [r for r, _, _ in fields])

    def _do_create(table_name, n_fields_val, *args):
        pairs = [(args[i].strip(), args[i + 1].strip()) for i in range(0, n_fields_val * 2, 2)]
        ok, msg = create_table(table_name, pairs)
        if ok:
            return gr.update(value=f"✅ **{msg}**")
        else:
            return gr.update(value=f"❌ **{msg}**")

    def on_create_click(*args):
        tn, n, *rest = args
        n = int(n)
        return _do_create(tn, n, *rest)

    create_btn.click(
        on_create_click,
        inputs=[table_name, n_fields] + sum([[f[1], f[2]] for f in fields], []),
        outputs=output
    )

    _adjust_fields(3)
    return

def build_show_tab():
    with gr.Tab("Show Existing Tables"):
        reload_btn = gr.Button("🔄 Refresh Tables")
        table_selector = gr.Dropdown([], label="Tables", interactive=True)
        show_output = gr.Markdown()

    def _refresh_tables():
        schemas = get_tables()
        names = list(schemas.keys())
        tbls = []
        for t in names:
            cols = schemas[t]["columns"]
            schema_line = ", ".join(f"`{k}` ({v})" for k, v in cols.items())
            tbls.append(f"- **{t}**: {schema_line}")
        info = "\n".join(tbls) if tbls else "_No tables found._"
        return gr.update(choices=names), gr.update(value=info)

    reload_btn.click(_refresh_tables, outputs=[table_selector, show_output])
    table_selector.change(_refresh_tables, outputs=[table_selector, show_output])

def build_insert_tab():
    with gr.Tab("Insert Data"):
        refresh_btn = gr.Button("🔄 Refresh Tables")
        table_selector = gr.Dropdown(label="Choose Table", choices=list(get_tables().keys()))
        
        # Create a fixed number of textboxes (we'll show/hide as needed)
        field_textboxes = []
        for i in range(10):  # Support up to 10 fields
            tb = gr.Textbox(label=f"Field {i+1}", visible=False)
            field_textboxes.append(tb)
        
        insert_btn = gr.Button("Insert Row 📝")
        result_md = gr.Markdown()

        def refresh_tables():
            choices = list(get_tables().keys())
            return gr.update(choices=choices, value=choices[0] if choices else None)
        
        refresh_btn.click(refresh_tables, outputs=table_selector)

        def on_table_select(table_name):
            schema = get_schema(table_name)
            updates = []
            
            if not schema or not schema.get("columns"):
                # Hide all fields
                for tb in field_textboxes:
                    updates.append(gr.update(visible=False))
                updates.append(gr.update(value="Please select a valid table."))
                return updates
            
            cols = list(schema["columns"].items())
            # Show and label the right number of fields
            for i, tb in enumerate(field_textboxes):
                if i < len(cols):
                    col_name, col_type = cols[i]
                    updates.append(gr.update(visible=True, label=f"{col_name} ({col_type})", value=""))
                else:
                    updates.append(gr.update(visible=False))
            
            updates.append(gr.update(value="**Enter values for fields:**"))
            return updates

        table_selector.change(
            on_table_select,
            inputs=table_selector,
            outputs=field_textboxes + [result_md]
        )

        def do_insert(table_name, *values):
            if not table_name:
                return "❌ Please select a table."
            
            schema = get_schema(table_name)
            if not schema:
                return "❌ Table not found!"
            
            # Only use values for visible fields
            n_cols = len(schema["columns"])
            vals = list(values)[:n_cols]
            
            ok, msg = insert_row(table_name, vals)
            return ("✅ " if ok else "❌ ") + msg

        insert_btn.click(
            do_insert,
            inputs=[table_selector] + field_textboxes,
            outputs=result_md
        )



def build_query_tab():
    with gr.Tab("Query Table"):
        refresh_btn = gr.Button("🔄 Refresh Tables")
        tbl_selector = gr.Dropdown(label="Select Table")
        schema_md = gr.Markdown()
        nl_query = gr.Textbox(label="Ask in natural language", lines=1)
        run_btn = gr.Button("Run Query 🤖")
        out_sql = gr.Textbox(label="Generated SQL", interactive=False)
        out_results = gr.Dataframe(label="Results")
        out_msg = gr.Markdown()
        def refresh_query_tables():
            choices = list(get_tables().keys())
            return gr.update(choices=choices, value=choices[0] if choices else None)
        refresh_btn.click(refresh_query_tables, outputs=tbl_selector)
        def on_tbl_select(tbl):
            schema = get_schema(tbl)
            if not schema:
                return "_No such table._"
            return "Schema: " + ", ".join(f"`{k}`({v})" for k, v in schema["columns"].items())
        tbl_selector.change(on_tbl_select, tbl_selector, schema_md)

        def query_run(tbl, question):
            sql, results, err = run_query(tbl, question)
            if err:
                return "", [], f"❌ {err}"
            if results and isinstance(results, list) and results:
                cols = list(results[0].keys())
                data = [[row.get(k, "") for k in cols] for row in results]
                return sql, gr.update(value=data, headers=cols), ""
            else:
                return sql, [], ""
        run_btn.click(
            query_run,
            inputs=[tbl_selector, nl_query],
            outputs=[out_sql, out_results, out_msg]
        )

# App Layout

with gr.Blocks(title="NL2SQL Playground UI") as demo:
    gr.Markdown(
        """
        # 🚀 NL2SQL Playground UI

        **Create tables, insert data, and ask questions in natural language 🔥**

        - Use the tabs below to create tables, insert data, see schemas, and query using English.
        - SQL is generated using LLM models (via your backend).
        """
    )
    with gr.Tabs():
        build_create_tab()
        build_show_tab()
        build_insert_tab()
        build_query_tab()

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080)
