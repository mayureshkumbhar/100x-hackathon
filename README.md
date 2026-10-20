# Eval Co-pilot

Gradio UI, Groq evaluation, and Supabase Postgres storage.

For local setup and Vercel deployment, see [the setup guide](hackathon/README.md).

Quick start from this repository's root on Windows:

```powershell
python -m venv hackathon/.venv
hackathon/.venv/Scripts/python.exe -m pip install -r requirements.txt
Copy-Item hackathon/.env.example hackathon/.env
# Fill DATABASE_URL and GROQ_API_KEY in hackathon/.env.
hackathon/.venv/Scripts/python.exe app.py
```

Open http://127.0.0.1:7860. Skip the copy command if `.env` already exists.
For Vercel, set Root Directory to `.` or `hackathon` and leave Output Directory
override disabled. Both roots contain deployment configuration. Apply
`hackathon/db/supabase_schema.sql`, and set the environment variables in the setup guide.
