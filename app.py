"""Shared ASGI entry point for Vercel and local Uvicorn."""
import os
import tempfile
from pathlib import Path

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("GRADIO_SSR_MODE", "False")
if os.getenv("VERCEL"):
    os.environ.setdefault("GRADIO_TEMP_DIR", str(Path(tempfile.gettempdir()) / "eval-copilot-gradio"))

import gradio as gr
from fastapi import FastAPI
from hackathon.ui.ui import demo

app = FastAPI(title="Eval Co-pilot", docs_url=None, redoc_url=None)


@app.get("/health")
def health():
    """Liveness only: does not contact the database or expose credentials."""
    return {"status": "ok"}


root = Path(__file__).resolve().parent
app = gr.mount_gradio_app(
    app, demo, path="/", ssr_mode=False,
    blocked_paths=[str(root / "hackathon" / "local_settings.py"),
                   str(root / "hackathon" / ".env"), str(root / ".env"),
                   str(root / "hackathon" / "logs")],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "7860")))
