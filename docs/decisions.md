# Decisions

## 001 — A modular monolith

There is one pipeline and one small workspace. A single API makes failures traceable and avoids distributed state. Boundaries are modules so ingestion and evaluations can move to workers later.

## 002 — An honest offline path

A working demo should not require a large model download. Local mode retrieves and quotes evidence. It is visibly labeled extractive; Ollama is an explicit second provider. We do not display canned generated answers or pretend a model ran.

## 003 — Immutable document versions

Changes to source material should not silently change the evidence behind yesterday's answer. Each imported version owns its passages. Conversation traces reference exact IDs and hashes.

## 004 — SQLite first, PostgreSQL next

SQLite makes the first local run practical on Windows. SQLAlchemy keeps persistence behind a small boundary. PostgreSQL support does not imply the unimplemented pgvector extension is already active.

## 005 — Hand-drawn details, quiet product copy

The workspace uses dark neutral surfaces, mint controls, warm cream text and small original SVG doodles. Decorative art has no screen-reader noise. Product labels explain outcomes: “Show the evidence”, “Needs a second look”, and “Try a question”.

