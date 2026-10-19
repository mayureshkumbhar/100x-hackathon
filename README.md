# Eval Co-pilot

Gradio UI mounted on FastAPI for Vercel. This deployable UI shell validates drafts
and displays explicitly labeled sample results. It does not call target apps, run
AI judges, or persist history. It is not yet a complete evaluation service.
Drafts disappear on reload. There are no secrets needed for demo mode.

## Local preview

Use Python 3.12 (the deployment target):

```powershell
cd F:\sgm\eval-copilot
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

Open http://127.0.0.1:7860. Stop any previous preview first. To use another port:

```powershell
$env:PORT = '7861'
.venv\Scripts\python app.py
```

## Deploy to Vercel

1. Add this folder to your own Git repository and import it into Vercel.
   For a larger repository, set Root Directory to the eval-copilot folder.
2. Use FastAPI framework detection. The ASGI entrypoint is app.py exporting app.
   No custom build command, start command or static output directory is required.
   Do not use python app.py as a build command.
3. Deploy a preview. Python 3.12 is selected by .python-version. Direct runtime
   dependencies are pinned in requirements.txt; no environment secrets are needed.
4. Check /healthz, page assets, draft validation, sample loading, both case details,
   empty selections, and sample comparison. Open a separate private browser session
   and verify it starts with an empty selection and no loaded results.
5. Promote only after preview validation. Local checks do not prove a Vercel build
   or deployment works. No remote deployment has been performed in this workspace.

Alternatively run a current Vercel CLI with vercel from this folder for a preview.
The Vercel Python bundle must remain under its platform limit. Do not upload your
virtual environment. vercel.json excludes development files and caps duration at
30 seconds. .vercelignore also excludes environment files and tests.

## Serverless behavior

Callbacks use direct HTTP requests with queue=False. There is no Gradio State,
instance-specific history, background evaluation or cross-request data dependency.
Dropdown choices are declared at startup so separate instances validate them.
The browser sends callback inputs each time. Gradio uses OS temporary storage,
analytics and server-side rendering are disabled, and project files are blocked
from the Gradio file route. There are no dedicated file-upload or file-output
components. Gradio's table includes CSV/TSV import; imported rows still pass the
same server validation. The mounted app sets a 1 MB upload limit.

The endpoint validator checks draft syntax only. Before adding outbound requests,
implement DNS/IP checks at connection time, redirect restrictions, response size
limits and timeouts. Draft URL validation alone is not SSRF protection.

Real evaluation needs durable storage for pairs, checks, calibration, runs, answers
and check outcomes. Long runs need durable execution outside UI requests. Add
project authorization when private data is stored. AI judging must be calibrated
against at least three manually graded examples before activation.

## Verification

```powershell
python -m unittest discover -s tests -v
```

Checks cover malformed input, selection guards, distinct case details, health,
page/config responses, bundled assets and direct Gradio callback requests.
Local checks were run with the installed Python 3.14; the Python 3.12 Vercel
build and deployed smoke test remain to be verified.
