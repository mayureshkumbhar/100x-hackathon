"""hackathon/ui/ui.py: Eval Co-pilot Gradio UI. Imports the logic from hackathon/api/api.py.

  pip install -r requirements.txt
  Set DATABASE_URL and GROQ_API_KEY in the environment or local_settings.py.
  python ui/ui.py        (run from the hackathon folder)
"""
import sys
from pathlib import Path

import gradio as gr
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import api as core  # noqa: E402

EXAMPLE = [["We approve invoices by email and it takes days",
            "Response is under 300 words; Names the real bottleneck; Includes at least one number"]]


def db():
    try:
        return core.connect()
    except RuntimeError as e:
        raise gr.Error(str(e))


def clean(v):
    return "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()


def rows_from_df(df):
    return [(clean(r.iloc[0]), clean(r.iloc[1])) for _, r in df.iterrows()]


def get_key():
    key = core.get_groq_key()
    if not key:
        raise gr.Error("No Groq API key found. Set GROQ_API_KEY in the environment or DEFAULT_GROQ_API_KEY in local_settings.py for local use.")
    return key


def run_labels(conn, app_id):
    return [(f"Run {r['id']} · {r['started_at'].astimezone().strftime('%H:%M')} {r['note'] or ''}".strip(), r["id"])
            for r in core.list_runs(conn, app_id)]


def render_run(conn, app_id, run_id):
    res = core.run_results(conn, run_id)
    table = []
    for r in res:
        failed = [c["check"] for c in r["checks"] if c["passed"] is False]
        unknown = sum(c["passed"] is None for c in r["checks"])
        note = "; ".join(failed) + (f" (+{unknown} not verified)" if unknown else "")
        table.append([r["user_input"][:70], "PASS" if r["passed"] else "FAIL", note])
    summary = f"### {sum(r['passed'] for r in res)} of {len(res)} passed (run {run_id})\nOpen the **Failures** tab to see each answer and why."
    cases = gr.update(choices=[(p["user_input"][:70], p["id"]) for p in core.list_pairs(conn, app_id)])
    runs = gr.update(choices=run_labels(conn, app_id))
    return summary, pd.DataFrame(table, columns=["Case", "Result", "Failed checks"]), cases, runs, runs


@core.database_session
def run_all(url, df, progress=gr.Progress()):
    url = clean(url)
    if not url.startswith("http"):
        raise gr.Error("Paste the live app URL (starting with http).")
    key = get_key()
    conn = db()
    app_id = core.upsert_app(conn, url)
    try:
        ids = core.save_pairs(conn, app_id, rows_from_df(df))
    except ValueError as e:
        raise gr.Error(str(e))
    if not ids:
        raise gr.Error("Add at least one case.")
    run_id = core.run_cases(conn, app_id, ids, key,
                            on_progress=lambda n, t: progress(n / t, desc=f"Case {n} of {t}"))
    return render_run(conn, app_id, run_id)


@core.database_session
def show_case(pair_id):
    if not pair_id:
        return "Pick a case."
    r = core.latest_result(db(), pair_id)
    if not r:
        return "This case has not been run yet."
    icon = {True: "✅", False: "❌", None: "❔"}
    checks = "\n".join(f"- {icon[c['passed']]} **{c['check']}** — {c['reason']}" for c in r["checks"])
    verdict = "PASS" if r["passed"] else "FAIL"
    return (f"### {verdict} (run {r['run_id']})\n\n**They typed**\n\n{r['user_input']}\n\n"
            f"**Their app said**\n\n{r['answer']}\n\n**Checks**\n\n{checks}")


@core.database_session
def rerun_one(pair_id, url):
    if not pair_id:
        raise gr.Error("Pick a case first.")
    conn = db()
    app_id = core.get_app_id(conn, clean(url))
    if not app_id or pair_id not in {p["id"] for p in core.list_pairs(conn, app_id)}:
        raise gr.Error("The selected case does not belong to this app URL. Run its cases first.")
    core.run_cases(conn, app_id, [pair_id], get_key(), note="single case")
    runs = gr.update(choices=run_labels(conn, app_id))
    return show_case(pair_id), runs, runs


@core.database_session
def compare(a, b):
    if not a or not b:
        raise gr.Error("Pick two runs.")
    rows = core.compare_runs(db(), a, b)
    return pd.DataFrame(rows, columns=["Case", "Earlier run", "Later run", "Change"])


with gr.Blocks(title="Eval Co-pilot", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Eval Co-pilot\nSend your classmate's own cases to their live app, then let Groq check each answer.")
    url = gr.Textbox(label="Their app URL", placeholder="https://their-app.example.com/api/plan")

    with gr.Tabs():
        with gr.Tab("Cases and run"):
            pairs = gr.Dataframe(
                headers=["What their user types", "Checks (plain English, separate with ;)"],
                value=EXAMPLE + [["", ""]] * 9, datatype=["str", "str"],
                row_count=(10, "dynamic"), col_count=(2, "fixed"), interactive=True, wrap=True)
            go = gr.Button("Run all cases", variant="primary")
            summary = gr.Markdown()
            results = gr.Dataframe(label="Results", interactive=False, wrap=True)
        with gr.Tab("Failures"):
            case = gr.Dropdown(label="Case", choices=[])
            detail = gr.Markdown("Run the cases first, then pick one here.")
            again = gr.Button("Re-run just this case")
        with gr.Tab("Compare runs"):
            with gr.Row():
                run_a = gr.Dropdown(label="Earlier run", choices=[])
                run_b = gr.Dropdown(label="Later run", choices=[])
            cmp_btn = gr.Button("Compare", variant="primary")
            cmp_table = gr.Dataframe(label="Fixed cases appear first", interactive=False, wrap=True)

    # Direct requests avoid queue state being split across serverless instances.
    go.click(run_all, [url, pairs], [summary, results, case, run_a, run_b], queue=False)
    # Dropdown updates may have been served by a different function instance.
    # Accept their IDs directly and look up the actual records in Postgres.
    case.change(show_case, case, detail, queue=False, preprocess=False)
    again.click(rerun_one, [case, url], [detail, run_a, run_b], queue=False, preprocess=False)
    cmp_btn.click(compare, [run_a, run_b], cmp_table, queue=False, preprocess=False)

if __name__ == "__main__":
    demo.launch()
