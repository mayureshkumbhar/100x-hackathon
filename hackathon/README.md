# Eval Co-pilot: local setup

Use Python 3.12, 3.13, or 3.14. Run these PowerShell commands from the repository root:

```powershell
cd hackathon
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Credentials

Open `api/api.py` and replace these two placeholder values:

```python
DEFAULT_DATABASE_URL = "PASTE_SUPABASE_POSTGRES_CONNECTION_STRING_HERE"
DEFAULT_GROQ_API_KEY = "PASTE_GROQ_API_KEY_HERE"
```

For the database URL, copy the Postgres URI from your Supabase project's Connect dialog.
For a local IPv4 network, use the Session pooler URI. Replace its password placeholder
with your database password (URL-encode special characters), and add `?sslmode=require`
if the URI has no query string, or `&sslmode=require` if it already has one.
This is a database connection string, not the Supabase project HTTPS URL or API key.

Existing `DATABASE_URL` and `GROQ_API_KEY` environment variables (including those in
`hackathon/.env`) take precedence over these defaults. `GROQ_API` is also supported as a
legacy environment variable after `GROQ_API_KEY`. Unfilled placeholders are treated as missing configuration.
Keep real credentials local; do not commit them.

The backend creates the tables on first database use if the database role has permission.
Alternatively, run `db/supabase_schema.sql` in the Supabase SQL Editor before using the app.

## Start

From the `hackathon` directory:

```powershell
.\.venv\Scripts\python.exe ui/ui.py
```

Open the local URL printed in the terminal (normally http://127.0.0.1:7860).
Use Ctrl+C to stop the server. Virtual environment activation is not required.

Paste the target app's POST endpoint into the interface. It should
accept `{"data": ["your test input"]}` and return `{"data": ["the answer"]}`.
The first item of the response's `data` array is used as the answer. If it is a JSON
string, it is decoded and formatted as readable JSON before judging and saving it.
Enter inputs and checks in the cases table, then click **Run all cases**. Those rows
are saved to `golden_pair`; evaluation reads each saved input and its checks from that
database table. Single-case reruns also read the saved row. Set `GROQ_MODEL` in the environment to override the
backend's default judge model. Credentials are configured only on the server.

Gradio is pinned to version 5 because the UI uses its version 5 API.

## API logs

Target app calls log the POST request body and the full response status/body to
the terminal and `logs/api.log` (relative to `hackathon`). Each call has a request
ID and elapsed time; connection errors and timeouts are logged as well. Logs rotate
at 5 MB with three backups and are excluded from Git. Bodies are recorded as JSON
on a single line, including escaped newlines. Groq authorization headers and database
credentials are not included by this logger.
