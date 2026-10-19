# Eval Co-pilot

A Gradio UI mounted on FastAPI for Vercel. The first tab performs live evaluation:

1. Send the user's request to Groq chat completions.
2. Send the original request, generated answer and each criterion to JEV native Decisions.
3. Display JEV's per-criterion PASS/FAIL choices and confidence when supplied.
4. Overall PASS requires every criterion to pass. Any failed criterion produces FAIL.
   Provider failures, timeouts or missing judgments produce Error, never PASS/FAIL.

JEV judgments are uncalibrated. Validate them against at least three manually graded
examples before treating them as reliable. The app does not invent explanations;
JEV returns typed choices and optional confidence, displayed as received.

The golden-pair editor, sample failure inspector and sample comparison remain
separate previews. Live batch runs, calibration storage and durable history are
not implemented. Results stay in the browser and disappear on reload.

## Environment

Required server-side variables (already configured on Vercel by the project owner):

- GROQ_API_KEY
- JEV_API_KEY

Optional: GROQ_MODEL (default llama-3.3-70b-versatile).
Never prefix keys with a browser-public variable name, paste keys into the UI,
commit them, or log provider request headers. No key values are included in this repo.

Provider URLs are fixed:
- https://api.groq.com/openai/v1/chat/completions
- https://www.jevai.org/api/v1/decisions

The user request alone is sent as Groq's user message. Criteria are not supplied
to the generator. Each criterion is a separate JEV choice question with pass/fail
options. JEV code must be 0 and every answer must contain a valid choice.

Requests are bounded to 8,000 characters and criteria to 4,000 characters, with
1–10 rules separated by newlines or semicolons. JEV payloads must fit its 32 KiB
limit; oversized content is rejected, never silently truncated. Generation is
limited to 1,200 completion tokens; interrupted/truncated generations are errors.
Provider requests have 20-second timeouts, a 45-second overall deadline, no
redirects or automatic retries, and a 1 MB response cap. Vercel duration is 60 seconds.
If JEV fails after generation, the Groq answer is preserved with an Error status.

## Local preview

Use Python 3.12 (the deployment target):

```powershell
cd F:\sgm\eval-copilot
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
# Supply the two keys through your local environment, then:
.venv\Scripts\python app.py
```

Open http://127.0.0.1:7860. Stop any previous preview first, or set PORT to 7861.
No .env loader is enabled. Vercel injects environment variables automatically.

## Deploy to Vercel

Import the repository and select the project root containing app.py. Use FastAPI
autodetection, with ASGI export app. No custom build command or static output
folder is needed. .python-version selects Python 3.12. Confirm both keys are
available to the intended Preview/Production environment, then redeploy.

Smoke-test /healthz, the page/assets, and the Generate & evaluate tab. Try one
clearly satisfied criterion and one clearly unsatisfied criterion, inspect the
actual answer and verdicts, then test repeated runs. Missing keys show a safe
configuration error. Provider bodies, headers and keys are not displayed.

The integration has been verified with mocked provider HTTP responses. An actual
Vercel deployment with the configured credentials is still needed to verify live
provider access, the JEV account response contract and the Linux/Python 3.12 build.

## Serverless operation

Callbacks use direct HTTP requests (queue=False). No Gradio State or process-local
run history is used. A request contains everything needed for one evaluation.
Analytics and SSR are disabled. Gradio temp storage uses the OS temporary folder;
project files are blocked from Gradio's file route. Table imports are subject to
the same draft validation and the mounted app sets a 1 MB upload limit.

Before broad public release, configure Vercel access protection or application
authentication and account quotas appropriate for the API keys funding evaluations.
A public evaluation button can incur provider usage. Database-backed projects,
access control, persistent runs and durable batch execution are future layers.

## Verification

```powershell
python -m unittest discover -s tests -v
```

Tests cover the request/answer/criteria flow, per-rule and overall verdicts,
missing keys, malformed provider data, HTTP errors, timeouts, payload limits,
Gradio assets and callbacks, and draft validation. Tests use fake keys and mock
transports; they never call paid providers. Local checks use installed Python 3.14.
