"""Authenticated entry points executed by the hosted Gradio GPU worker."""

import asyncio
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from .api import GPU_CALL, Question, RunRequest
from .db import Database


def queued_call(app, operation, token, payload):
    visitors = app.state.database
    visitor = visitors.verify(token)
    if not visitor:
        return {
            "ok": False,
            "error": "Your demo session expired. Refresh to start again.",
        }
    if not visitors.allowed(visitor):
        return {"ok": False, "error": "Please wait a moment before your next request."}
    # The normal API creates and bounds visitor databases. Workers only reopen one
    # already created there; never inherit pooled SQLite connections across forks.
    path = Path("data/visitors") / f"{visitor}.db"
    if not path.is_file():
        return {"ok": False, "error": "Refresh the page to load your demo session."}
    database = Database(f"sqlite:///{path}")
    scope = visitors.active.set(database)
    gpu_scope = GPU_CALL.set(True)
    try:
        if operation == "ask":
            result = app.state.ask(Question.model_validate(payload))
        elif operation == "evaluate":
            tasks = BackgroundTasks()
            result = app.state.evaluate(RunRequest.model_validate(payload), tasks)
            asyncio.run(tasks())
        else:
            raise ValueError("Unknown queue operation")
        return {"ok": True, "result": jsonable_encoder(result)}
    except HTTPException as error:
        return {"ok": False, "error": str(error.detail)}
    except ValidationError:
        return {"ok": False, "error": "Please check your question and reference."}
    finally:
        GPU_CALL.reset(gpu_scope)
        visitors.active.reset(scope)
        database.engine.dispose()
