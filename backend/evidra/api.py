from contextlib import asynccontextmanager
from contextvars import ContextVar
import asyncio
import os
from pathlib import Path
from uuid import uuid4
from typing import Literal
from time import perf_counter

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .db import Database, Document, Passage, Review, Run, Turn, ExtractionReport
from .documents import HANDBOOK_TEXT, ingest, seed
from .evaluations import CASES, run_evaluation
from .pipeline import execute, settings
from .public import VisitorDatabases

GPU_CALL = ContextVar("gpu_call", default=False)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_id: str
    language: Literal["en", "hi"] = "en"
    conversation_id: str = Field(default_factory=lambda: str(uuid4()), max_length=36)


class Decision(BaseModel):
    status: str
    note: str = Field(default="", max_length=2000)


class RunRequest(BaseModel):
    document_id: str


def create_app(database_url=None):
    database = VisitorDatabases(Database(database_url))
    warming = os.getenv("EVIDRA_WARM_MODELS", "0") == "1"
    model_state = {"ready": not warming, "error": ""}

    def warm_models():
        try:
            import subprocess
            import sys
            from .models import model_pair
            from .voice import transcription_model, speech_model
            from .languages import translation_pair
            from .retrieval import enabled, encoder

            Path("data/models").mkdir(parents=True, exist_ok=True)
            for voice in ("en_US-ljspeech-medium", "hi_IN-pratham-medium"):
                if Path(f"data/models/{voice}.onnx").is_file():
                    continue
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "piper.download_voices",
                        "--data-dir",
                        "data/models",
                        voice,
                    ],
                    check=True,
                )
            model_pair()
            translation_pair()
            if enabled():
                encoder()
                encoder("reranker")
            transcription_model()
            transcription_model("hi")
            speech_model()
            speech_model("hi")
            model_state["ready"] = True
        except Exception:
            import traceback

            traceback.print_exc()
            model_state["error"] = (
                "The demo models could not start. Please try again later."
            )

    @asynccontextmanager
    async def lifespan(app):
        seed(database)
        # Interrupted runs remain visible rather than looking indefinitely active.
        with database.session() as session:
            for run in session.scalars(
                select(Run).where(Run.status.in_(["pending", "running"]))
            ):
                run.status = "failed"
                run.results = {
                    **run.results,
                    "error": "Server restarted before this run finished.",
                }
            session.commit()
        task = asyncio.create_task(run_in_threadpool(warm_models)) if warming else None
        yield
        if task:
            task.cancel()
        database.engine.dispose()

    app = FastAPI(title="Evidra", lifespan=lifespan)
    app.state.database = database
    app.state.model_state = model_state
    app.state.warm_models = warm_models
    database.install(app)

    def document_or_404(session, document_id):
        document = session.get(Document, document_id)
        if not document:
            raise HTTPException(404, "Reference not found.")
        return document

    def document_dict(session, document):
        extraction = session.get(ExtractionReport, document.id)
        count = session.scalar(
            select(func.count())
            .select_from(Passage)
            .where(Passage.document_id == document.id)
        )
        return {
            "id": document.id,
            "title": document.title,
            "version": document.version,
            "digest": document.digest,
            "source": document.source,
            "extraction": extraction.report if extraction else None,
            "passage_count": count,
            "text_preview": (
                session.scalar(
                    select(Passage.text)
                    .where(Passage.document_id == document.id)
                    .order_by(Passage.locator)
                    .limit(1)
                )
                or ""
            )[:900],
            "created_at": document.created_at,
        }

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "public": database.public,
            "models_ready": model_state["ready"],
            "model_error": model_state["error"],
            "zero_gpu": os.getenv("EVIDRA_ZERO_GPU", "0") == "1",
            "languages": ["en", "hi"],
            "retrieval": os.getenv("EVIDRA_RETRIEVAL", "lexical"),
            **settings(),
        }

    @app.get("/api/documents")
    def documents():
        with database.session() as session:
            return [
                document_dict(session, document)
                for document in session.scalars(
                    select(Document).order_by(Document.created_at.desc())
                )
            ]

    @app.get("/api/documents/{document_id}")
    def document_detail(document_id: str):
        with database.session() as session:
            document = document_or_404(session, document_id)
            return {
                **document_dict(session, document),
                "passages": [
                    {"id": p.id, "locator": p.locator, "text": p.text}
                    for p in session.scalars(
                        select(Passage).where(Passage.document_id == document_id)
                    )
                ],
            }

    @app.post("/api/demo")
    def demo():
        with database.session() as session:
            document = ingest(
                session,
                "northstar.md",
                HANDBOOK_TEXT.encode(),
                "Northstar · sample handbook",
                "Bundled company handbook",
            )
            return document_dict(session, document)

    @app.post("/api/documents", status_code=201)
    async def upload(file: UploadFile = File(...), title: str = Form("")):
        content = await file.read(5 * 1024 * 1024 + 1)
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(413, "Please choose a file smaller than 5 MB.")
        title = (title.strip() or file.filename or "Untitled reference")[:200]

        def import_document():
            with database.session() as session:
                if (
                    database.public
                    and session.scalar(
                        select(func.count())
                        .select_from(Document)
                        .where(
                            Document.source.notin_(
                                [
                                    "Bundled synthetic fixture",
                                    "Bundled company handbook",
                                ]
                            )
                        )
                    )
                    >= 10
                ):
                    raise HTTPException(
                        429,
                        "This demo allows ten imported reference versions per session.",
                    )
                document = ingest(
                    session, file.filename or "upload.txt", content, title
                )
                return document_dict(session, document)

        try:
            return await run_in_threadpool(import_document)
        except HTTPException:
            raise
        except RuntimeError:
            raise HTTPException(
                503,
                "Document OCR or indexing is temporarily unavailable. Please try again or upload a text export.",
            )
        except (ValueError, UnicodeError) as error:
            raise HTTPException(
                422,
                str(error)
                or "Couldn't read this file. Use UTF-8 text, Markdown, or a searchable PDF with up to 100 pages.",
            )
        except Exception:
            raise HTTPException(
                422, "This document couldn't be parsed. Try a text export instead."
            )

    @app.post("/api/questions", status_code=201)
    def question(body: Question):
        if os.getenv("EVIDRA_ZERO_GPU", "0") == "1" and not GPU_CALL.get():
            raise HTTPException(503, "Use the hosted GPU queue to ask a question.")
        if not model_state["ready"]:
            raise HTTPException(
                503,
                model_state["error"]
                or "The open models are warming up. Please try again shortly.",
            )
        if not body.question.strip():
            raise HTTPException(422, "Please enter a question.")
        with database.session() as session:
            if (
                database.public
                and session.scalar(select(func.count()).select_from(Turn)) >= 100
            ):
                raise HTTPException(429, "This demo allows 100 questions per session.")
            document = document_or_404(session, body.document_id)
            passages = session.scalars(
                select(Passage).where(Passage.document_id == document.id)
            ).all()
            from .retrieval import enabled, index_passages

            try:
                vectors = index_passages(session, passages) if enabled() else None
            except (ValueError, RuntimeError, OSError):
                raise HTTPException(
                    503, "Couldn't prepare document search. Please try again shortly."
                )
            previous = session.scalar(
                select(Turn)
                .where(
                    Turn.conversation_id == body.conversation_id,
                    Turn.document_id == document.id,
                )
                .order_by(Turn.created_at.desc())
                .limit(1)
            )
            started = perf_counter()
            search_question = body.question.strip()
            previous_question = (
                previous.result.get("search_question", previous.question)
                if previous
                else None
            )
            if body.language == "hi":
                if len(search_question) > 1200:
                    raise HTTPException(
                        422, "Keep Hindi questions shorter than 1200 characters."
                    )
                if settings()["provider"] != "transformers":
                    raise HTTPException(
                        503, "Hindi answers need the hosted open model."
                    )
                from .languages import english_question

                try:
                    search_question = english_question(search_question)
                except (ValueError, RuntimeError, OSError):
                    raise HTTPException(
                        503,
                        "Couldn't understand this Hindi question. Please try again.",
                    )
            try:
                result = execute(
                    search_question,
                    passages,
                    previous_question,
                    language=body.language,
                    vectors=vectors,
                )
            except (ValueError, RuntimeError, OSError):
                raise HTTPException(
                    503, "Document search is temporarily unavailable. Please try again."
                )
            result["language"] = body.language
            result["search_question"] = search_question
            result["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)
            if body.language == "hi":
                result["trace"].insert(
                    0,
                    {
                        "stage": "Translate",
                        "detail": f"English search question: {search_question}. Original Hindi question is retained.",
                    },
                )
            result.update(
                {
                    "document_title": document.title,
                    "document_version": document.version,
                    "document_digest": document.digest,
                }
            )
            turn = Turn(
                conversation_id=body.conversation_id,
                document_id=document.id,
                question=body.question.strip(),
                result=result,
            )
            session.add(turn)
            session.flush()
            if result["disposition"] == "review":
                session.add(Review(turn_id=turn.id))
            session.commit()
            return {
                "id": turn.id,
                "conversation_id": turn.conversation_id,
                "question": turn.question,
                "created_at": turn.created_at,
                **result,
            }

    @app.get("/api/conversations/{conversation_id}")
    def conversation(conversation_id: str):
        with database.session() as session:
            return [
                {"id": turn.id, "question": turn.question, **turn.result}
                for turn in session.scalars(
                    select(Turn)
                    .where(Turn.conversation_id == conversation_id)
                    .order_by(Turn.created_at)
                )
            ]

    @app.get("/api/reviews")
    def reviews():
        with database.session() as session:
            rows = session.execute(
                select(Review, Turn).join(Turn).order_by(Review.created_at.desc())
            ).all()
            return [
                {
                    "id": review.id,
                    "status": review.status,
                    "note": review.note,
                    "created_at": review.created_at,
                    "question": turn.question,
                    "turn_id": turn.id,
                    **turn.result,
                }
                for review, turn in rows
            ]

    @app.patch("/api/reviews/{review_id}")
    def review_decision(review_id: str, body: Decision):
        if body.status not in ("resolved", "pending"):
            raise HTTPException(422, "Choose resolved or pending.")
        with database.session() as session:
            review = session.get(Review, review_id)
            if not review:
                raise HTTPException(404, "Review not found.")
            review.status, review.note = body.status, body.note
            session.commit()
            return {"id": review.id, "status": review.status, "note": review.note}

    @app.get("/api/evaluations")
    def evaluations():
        with database.session() as session:
            return [
                {
                    "id": run.id,
                    "status": run.status,
                    "created_at": run.created_at,
                    **run.results,
                }
                for run in session.scalars(
                    select(Run).order_by(Run.created_at.desc()).limit(20)
                )
            ]

    @app.post("/api/evaluations", status_code=202)
    def evaluate(body: RunRequest, tasks: BackgroundTasks):
        if os.getenv("EVIDRA_ZERO_GPU", "0") == "1" and not GPU_CALL.get():
            raise HTTPException(503, "Use the hosted GPU queue to run an evaluation.")
        with database.session() as session:
            document = document_or_404(session, body.document_id)
            if document.source != "Bundled synthetic fixture":
                raise HTTPException(
                    422,
                    "The Aster suite needs its bundled fictional reference. Select Aster before running it.",
                )
            if session.scalar(
                select(Run).where(Run.status.in_(["pending", "running"]))
            ):
                raise HTTPException(409, "An evaluation is already running.")
            run = Run(
                document_id=document.id, results={"completed": 0, "total": len(CASES)}
            )
            session.add(run)
            session.commit()
            if (
                database.public
                and session.scalar(select(func.count()).select_from(Run)) > 3
            ):
                session.delete(run)
                session.commit()
                raise HTTPException(
                    429, "This demo allows three evaluation runs per session."
                )
            tasks.add_task(run_evaluation, database.current(), run.id)
            return {"id": run.id, "status": run.status}

    app.state.ask = question
    app.state.evaluate = evaluate

    @app.post("/api/voice/transcribe")
    async def audio(
        file: UploadFile = File(...), language: Literal["en", "hi"] = Form("en")
    ):
        content = await file.read(8 * 1024 * 1024 + 1)
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(413, "Keep recordings under 8 MB.")
        try:
            from .voice import transcribe, VoiceBusy

            text = await run_in_threadpool(transcribe, content, language)
            if not text.strip():
                raise HTTPException(
                    422, "No speech was detected. Try a clearer recording."
                )
            return {"text": text}
        except HTTPException:
            raise
        except VoiceBusy:
            raise HTTPException(503, "Voice is busy. Please try again in a moment.")
        except ImportError:
            raise HTTPException(
                503,
                "Speech isn't installed. Install the voice extras to enable transcription.",
            )
        except Exception:
            raise HTTPException(
                422,
                "Couldn't transcribe this recording. Check the local speech model and audio format.",
            )

    @app.post("/api/voice/speak/{turn_id}")
    def speech(turn_id: str):
        with database.session() as session:
            turn = session.get(Turn, turn_id)
            if not turn:
                raise HTTPException(404, "Turn not found.")
            try:
                from .voice import speak

                return Response(
                    speak(
                        (turn.result["answer"] or turn.result["reason"])[:2000],
                        turn.result.get("language", "en"),
                    ),
                    media_type="audio/wav",
                )
            except ImportError:
                raise HTTPException(
                    503,
                    "Speech isn't installed. Install the voice extras to enable audio.",
                )
            except Exception:
                raise HTTPException(
                    503, "Speech generation failed. Check the configured Piper model."
                )

    static = Path(os.getenv("EVIDRA_STATIC_DIR", "frontend/dist"))
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
    return app


app = create_app()
