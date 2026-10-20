# Eval Co-pilot: local setup

Use Python 3.12, 3.13, or 3.14. Run these PowerShell commands from the repository root:

```powershell
cd hackathon
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Credentials

For a fresh clone, copy `.env.example` to `.env` inside `hackathon` and fill in
`DATABASE_URL` and `GROQ_API_KEY`. Alternatively, create the ignored
`hackathon/local_settings.py` file with these local fallbacks:

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
Existing local defaults are preserved in `hackathon/local_settings.py`, which is
excluded from Git and Vercel. Deployments use environment credentials only.
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
Callbacks use direct requests rather than an in-memory queue, so results appear
when each request finishes without live queue/progress updates.

## API logs

Target app calls log the POST request body and the full response status/body to
the terminal and `logs/api.log` (relative to `hackathon`). Each call has a request
ID and elapsed time; connection errors and timeouts are logged as well. Logs rotate
at 5 MB with three backups and are excluded from Git. Bodies are recorded as JSON
on a single line, including escaped newlines. Groq authorization headers and database
credentials are not included by this logger.


## Shared local entry point

You can also install from the repository root and run the same FastAPI entry point
that Vercel uses:

```powershell
hackathon/.venv/Scripts/python.exe -m pip install -r requirements.txt
hackathon/.venv/Scripts/python.exe app.py
```

Open http://127.0.0.1:7860. Set `PORT` to change the port. On macOS/Linux use
`hackathon/.venv/bin/python` instead. The original `ui/ui.py` command still works.
The root `.python-version` selects Python 3.12 for Vercel; local startup is tested
on the installed Python 3.14.

## Vercel deployment

1. Import the GitHub repository into Vercel.
2. Set **Root Directory** to either the repository root (`.`) or `hackathon`.
   Both directories contain their own `app.py`, `vercel.json`, Python version,
   dependency metadata and lockfile. Leave Output Directory override disabled.
3. Leave Build Command and Output Directory overrides unset. `vercel.json`
   explicitly builds `app.py` with the pinned Python runtime and routes all paths
   to it. This bypasses FastAPI framework entry-point discovery. Existing framework
   settings do not override this explicit build configuration. Dependencies are
   installed from `pyproject.toml` and `uv.lock`. The project file also declares
   `app:app`; local pip commands continue to use `requirements.txt`.
4. Apply `hackathon/db/supabase_schema.sql` in the Supabase SQL Editor.
5. Configure these server environment variables for Production and/or Preview:

   | Variable | Value |
   | --- | --- |
   | `DATABASE_URL` | Supabase **Transaction pooler** URI (port 6543), with password and `sslmode=require` |
   | `GROQ_API_KEY` | Your Groq API key |
   | `GROQ_MODEL` | Optional; defaults to `openai/gpt-oss-120b` |
   | `AUTO_INIT_SCHEMA` | Optional; defaults to `false` on Vercel, `true` locally |
   | `EVAL_RUN_TIMEOUT_SECONDS` | Optional; defaults to `240` on Vercel, `0` (unlimited) locally |

6. Deploy and open `/health` to check startup. Open `/` for the UI and try a small
   evaluation. `/health` checks liveness only; it does not validate database/Groq
   credentials. Redeploy after changing environment variables.

Local connections can use the Session pooler as described above. Hosted connections
must use the Transaction pooler and SSL. Database connections are closed after each
callback, including failed callbacks. Database schema creation is disabled by default
on Vercel; apply the SQL separately before deployment.

Gradio is mounted inside FastAPI with SSR disabled. Hosted cache files use `/tmp`.
Callbacks do not rely on an in-memory queue, and dropdown IDs can be used by a fresh
function instance. `vercel.json` allows 300 seconds per invocation. The evaluation
budget bounds outbound timeouts/retries; cases left after it expires are saved as
failed/not evaluated. Keep batches small: database work, slow responses, and network
behavior can still consume the platform's hard timeout. Durable background runs
would require a separate worker/job system.

On Vercel, request/response logs go to **runtime logs only**, with no writes to the
read-only source directory. Local rotating file logging is unchanged. Deployments
require environment credentials and ignore local credential fallbacks.
`.vercelignore` and function exclusions omit `.env`, `local_settings.py`, virtual
environments, logs, caches, staging copies, and tests. Protect deployment access when
using shared Groq credentials.

References: [Vercel FastAPI deployment](https://vercel.com/docs/frameworks/backend/fastapi),
[function limits](https://vercel.com/docs/functions/limitations), and
[Supabase connections](https://supabase.com/docs/guides/database/connecting-to-postgres).

## Automated checks

From the repository root:

```powershell
hackathon/.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Tests use mocked network/database services and do not call Groq or your target app.


## Diagnosing a deployment that serves source files

Resources must list a Python Function for `app.py`. A deployment showing only static
assets such as `/api/api.py` and `/ui/ui.py` has published source files instead of
running the app. Select the repository root or `hackathon` as Root Directory, leave
Build Command and Output Directory overrides disabled, and deploy the latest commit.
The `vercel.json` in either supported root builds the function and routes requests
to `/app.py`. Check `/health` after the deployment is marked Production / Current.
