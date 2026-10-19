"""Stateless Gradio UI mounted on FastAPI for Vercel."""
import os
import tempfile

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("GRADIO_TEMP_DIR", os.path.join(tempfile.gettempdir(), "eval-copilot"))

import gradio as gr
from fastapi import FastAPI
from ui_logic import validate_draft, inspect_case, load_demo, compare_runs

CSS = """
.gradio-container {max-width: 1160px !important; margin: auto;}
#hero {padding: 20px 0 8px;}
#hero h1 {font-size: clamp(26px, 5vw, 36px); letter-spacing: -1px;}
#notice {border-left: 3px solid #6366f1; padding-left: 14px; margin-bottom: 16px;}
"""

with gr.Blocks(title="Eval Co-pilot", analytics_enabled=False) as demo:
    gr.Markdown("# Eval Co-pilot\nFind the failure. Understand it. Prove the fix.", elem_id="hero")
    gr.Markdown("**Demo mode** · No requests sent to your app · Nothing saved\n\nDraft your cases or explore the sample evaluation. Reloading clears your draft.", elem_id="notice")
    url = gr.Textbox(label="Their app URL", placeholder="https://their-app.example.com/api/plan", max_length=2048)
    with gr.Row():
        in_key = gr.Textbox(label="Request field name", value="input", max_length=64)
        out_key = gr.Textbox(label="Answer field name", value="output", max_length=64)
    with gr.Tabs():
        with gr.Tab("Cases and run"):
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
        with gr.Tab("Failures"):
            gr.Markdown("### Inspect the answer\nLoad the sample evaluation first. All content here is illustrative.")
            case = gr.Dropdown(label="Sample case", choices=[("GP-01 · Invoice approvals", "GP-01"), ("GP-02 · Onboarding", "GP-02")], value=None)
            with gr.Row():
                with gr.Column():
                    original = gr.Textbox(label="They typed", lines=3, interactive=False)
                    expected = gr.Textbox(label="Good answer criteria", lines=3, interactive=False)
                answer = gr.Textbox(label="Their app said · sample", lines=5, interactive=False)
            checks = gr.Dataframe(headers=["Check", "Result", "Reason"], type="array", interactive=False, wrap=True, label="Sample checks")
            gr.Button("Rerun this case · backend coming next", interactive=False)
        with gr.Tab("Compare runs"):
            gr.Markdown("### Did the fix work?\nTwo predefined sample runs, not executions of your draft.")
            with gr.Row():
                run_a = gr.Dropdown(label="Earlier sample run", choices=["Sample run 1", "Sample run 2"], value=None)
                run_b = gr.Dropdown(label="Later sample run", choices=["Sample run 1", "Sample run 2"], value=None)
            compare = gr.Button("Compare sample runs", variant="primary")
            comparison_status = gr.Textbox(label="Comparison summary", interactive=False)
            comparison = gr.Dataframe(headers=["Case", "Earlier run", "Later run", "Change"], type="array", interactive=False, wrap=True, label="Sample comparison")
    validate.click(validate_draft, [url, in_key, out_key, pairs], validation, queue=False, api_name=False)
    sample.click(load_demo, outputs=[summary, results, case, run_a, run_b, original, expected, answer, checks], queue=False, api_name=False)
    case.change(inspect_case, case, [original, expected, answer, checks], queue=False, api_name=False)
    compare.click(compare_runs, [run_a, run_b], [comparison_status, comparison], queue=False, api_name=False)

app = FastAPI(title="Eval Co-pilot", docs_url=None, redoc_url=None, openapi_url=None)

@app.get("/healthz")
def health():
    return {"status": "ok", "mode": "demo"}

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
