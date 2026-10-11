"""Spaces entry point. The bundle contains only audited app source and built assets."""

import os
import sys
import zipfile
from pathlib import Path

with zipfile.ZipFile("evidra.zip") as archive:
    archive.extractall(".")
sys.path.insert(0, str(Path("backend").resolve()))
os.environ.setdefault("EVIDRA_PUBLIC", "1")
os.environ.setdefault("EVIDRA_PROVIDER", "transformers")
os.environ.setdefault("EVIDRA_MODEL", "Qwen/Qwen3-4B-Instruct-2507")
os.environ["EVIDRA_RETRIEVAL"] = "hybrid"
os.environ.setdefault("EVIDRA_WARM_MODELS", "1")
os.environ["EVIDRA_WARM_MODELS"] = "0"
os.environ["EVIDRA_ZERO_GPU"] = "1"
os.environ["EVIDRA_DEVICE"] = "cuda"
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ["GRADIO_SSR_MODE"] = "false"

import uvicorn
import gradio as gr
import spaces
from evidra.api import app
from evidra.queued import queued_call


@spaces.GPU(
    duration=lambda token, payload: 90 if payload.get("language") == "hi" else 45
)
def ask(token, payload):
    return queued_call(app, "ask", token, payload)


@spaces.GPU(duration=90)
def evaluate(token, payload):
    return queued_call(app, "evaluate", token, payload)


with gr.Blocks(analytics_enabled=False) as compute:
    gr.Markdown("Evidra's GPU queue. Open the main workspace to start a conversation.")
    token_input = gr.Textbox(visible=False)
    payload_input = gr.JSON(visible=False)
    output = gr.JSON(visible=False)
    gr.Button("Ask", visible=False).click(
        ask,
        [token_input, payload_input],
        output,
        api_name="ask",
        concurrency_id="model",
        concurrency_limit=1,
    )
    gr.Button("Evaluate", visible=False).click(
        evaluate,
        [token_input, payload_input],
        output,
        api_name="evaluate",
        concurrency_id="model",
        concurrency_limit=1,
    )
compute.queue(max_size=16)
app.state.model_state["ready"] = False
app.state.warm_models()
# Spaces reports GPU handlers through Blocks.launch. The same queue is mounted
# below for the public same-origin API; this listener stays on loopback only.
compute.launch(
    server_name="127.0.0.1",
    server_port=7861,
    prevent_thread_lock=True,
    ssr_mode=False,
)
# Mount the compute queue before the catch-all React static route.
static_routes = [
    route for route in app.routes if getattr(route, "path", None) in ("", "/")
]
for route in static_routes:
    app.routes.remove(route)
app = gr.mount_gradio_app(app, compute, path="/compute")
app.routes.extend(static_routes)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860, workers=1)
