"""Stateless Gradio UI mounted on FastAPI for Vercel."""
import os
import tempfile

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("GRADIO_TEMP_DIR", os.path.join(tempfile.gettempdir(), "eval-copilot"))

import gradio as gr
from fastapi import FastAPI
from ui_logic import validate_draft, inspect_case, load_demo, compare_runs
from evaluation import evaluate_request

CSS = """
.gradio-container {max-width: 1160px !important; margin: auto;}
#hero {padding: 20px 0 8px;}
#hero h1 {font-size: clamp(26px, 5vw, 36px); letter-spacing: -1px;}
#notice {border-left: 3px solid #6366f1; padding-left: 14px; margin-bottom: 16px;}
"""

with gr.Blocks(title="Eval Co-pilot", analytics_enabled=False) as demo:
    gr.Markdown("# Eval Co-pilot\nFind the failure. Understand it. Prove the fix.", elem_id="hero")
    gr.Markdown("**Live evaluation** · Groq generates an answer → JEV checks your criteria\n\nRequests go to Groq; your request, generated answer and criteria go to JEV. Nothing is saved to a database.", elem_id="notice")
    with gr.Tabs():
        with gr.Tab("Generate & evaluate"):
            request = gr.Textbox(label="What would you like the AI to do?", placeholder="Suggest a plan to reduce invoice approval delays.", lines=5, max_length=8000)
            criteria = gr.Textbox(label="Good answer criteria / rules", placeholder="Includes a numeric target\nNames the approval bottleneck\nUnder 300 words", lines=5, max_length=4000)
            gr.Markdown("One criterion per line (up to 10). The request goes to Groq first; criteria are then used by JEV to judge its answer. These AI judgments are uncalibrated; compare them with manually graded examples before relying on them.")
            evaluate = gr.Button("Generate with Groq & evaluate with JEV", variant="primary")
            generated = gr.Textbox(label="Groq's answer", lines=10, interactive=False)
            verdict = gr.Textbox(label="Overall result", interactive=False)
            live_checks = gr.Dataframe(headers=["Criterion", "JEV result", "Confidence"], datatype="str", type="array", interactive=False, wrap=True, label="Per-criterion results")
        with gr.Tab("Golden pairs · draft"):
            gr.Markdown("This draft editor and the sample tabs are separate from live Groq/JEV evaluation.")
            url = gr.Textbox(label="Future target app URL", placeholder="https://their-app.example.com/api/plan", max_length=2048)
            with gr.Row():
                in_key = gr.Textbox(label="Request field name", value="input", max_length=64)
                out_key = gr.Textbox(label="Answer field name", value="output", max_length=64)
            gr.Markdown("### Define ten real cases\nWrite expected answer criteria with the app owner. Leave unused rows blank.")
            pairs = gr.Dataframe(
                headers=["What their user types", "Good answer criteria", "Checks (separate with ;)"],
                value=[["We approve invoices by email and it takes days", "Identifies the bottleneck and a measurable next step", "max_words:300; has_number; judge:names the real bottleneck"]] + [["", "", ""] for _ in range(9)],
                datatype=["str", "str", "str"], type="array", row_count=10,
                column_count=3, interactive=True, wrap=True, label="Golden pairs")
            gr.Markdown("Draft checks: `max_words:300`, `has_number`, `has_baseline`, `judge:criterion`. AI judging stays unavailable until calibrated against at least three manually graded examples.")
            with gr.Row():
                validate = gr.Button("Validate draft")
                gr.Button("Run all cases · backend coming next", interactive=False)
                sample = gr.Button("Load sample evaluation", variant="primary")
            validation = gr.Textbox(label="Draft validation", interactive=False, lines=3)
            summary = gr.Markdown("No sample evaluation loaded.")
            results = gr.Dataframe(headers=["Case", "Result", "Failed checks"], type="array", interactive=False, wrap=True, label="Sample results")
        with gr.Tab("Sample failures"):
            gr.Markdown("### Inspect the answer\nLoad the sample evaluation first. All content here is illustrative.")
            case = gr.Dropdown(label="Sample case", choices=[("GP-01 · Invoice approvals", "GP-01"), ("GP-02 · Onboarding", "GP-02")], value=None)
            with gr.Row():
                with gr.Column():
                    original = gr.Textbox(label="They typed", lines=3, interactive=False)
                    expected = gr.Textbox(label="Good answer criteria", lines=3, interactive=False)
                answer = gr.Textbox(label="Their app said · sample", lines=5, interactive=False)
            checks = gr.Dataframe(headers=["Check", "Result", "Reason"], type="array", interactive=False, wrap=True, label="Sample checks")
            gr.Button("Rerun this case · backend coming next", interactive=False)
        with gr.Tab("Sample comparison"):
            gr.Markdown("### Did the fix work?\nTwo predefined sample runs, not executions of your draft.")
            with gr.Row():
                run_a = gr.Dropdown(label="Earlier sample run", choices=["Sample run 1", "Sample run 2"], value=None)
                run_b = gr.Dropdown(label="Later sample run", choices=["Sample run 1", "Sample run 2"], value=None)
            compare = gr.Button("Compare sample runs", variant="primary")
            comparison_status = gr.Textbox(label="Comparison summary", interactive=False)
            comparison = gr.Dataframe(headers=["Case", "Earlier run", "Later run", "Change"], type="array", interactive=False, wrap=True, label="Sample comparison")
    evaluate.click(evaluate_request, [request, criteria], [generated, verdict, live_checks], queue=False, api_name=False, concurrency_limit=4)
    validate.click(validate_draft, [url, in_key, out_key, pairs], validation, queue=False, api_name=False)
    sample.click(load_demo, outputs=[summary, results, case, run_a, run_b, original, expected, answer, checks], queue=False, api_name=False)
    case.change(inspect_case, case, [original, expected, answer, checks], queue=False, api_name=False)
    compare.click(compare_runs, [run_a, run_b], [comparison_status, comparison], queue=False, api_name=False)

app = FastAPI(title="Eval Co-pilot", docs_url=None, redoc_url=None, openapi_url=None)

@app.get("/healthz")
def health():
    return {"status": "ok", "mode": "groq-jev"}

@app.middleware("http")
async def response_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not request.url.path.startswith(("/assets/", "/static/")):
        response.headers["Cache-Control"] = "no-store"
    return response

app = gr.mount_gradio_app(app, demo, path="/", theme=gr.themes.Soft(primary_hue="indigo"), css=CSS,
    ssr_mode=False, show_error=False, footer_links=[], max_file_size="1mb",
    blocked_paths=[os.path.dirname(os.path.abspath(__file__))])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "7860")))
