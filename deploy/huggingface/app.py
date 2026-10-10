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
os.environ.setdefault("EVIDRA_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
os.environ.setdefault("EVIDRA_WARM_MODELS", "1")
os.environ.setdefault("HF_HOME", str(Path("data/hf-cache").resolve()))
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import uvicorn
from evidra.api import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860, workers=1)
