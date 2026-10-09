import hashlib
import io
import re

from sqlalchemy import func, select

from .db import Document, Passage

DEMO_TEXT = """# Aster reference
This is a fictional research reference created for software testing. It does not describe an actual medicine, patient, or clinical study.

## Study design
The fictional Aster study enrolled 52 adult participants. The observation period was 12 weeks. It used two fictional study groups, Cedar and Willow. These numbers are synthetic test facts.

## Enrollment
The fictional enrollment process includes an invitation, a consent review, and a scheduling call. The study coordinator answers enrollment questions. No real participant data is included.

## Storage
Fictional sample kits are stored in the blue cabinet at room temperature. Each sample kit has a study identifier. These instructions are invented for retrieval testing.

## Contact
The fictional study coordinator is the contact for scheduling and enrollment. The research desk handles document questions. There is no real phone number or email address in this reference.

## Safety reporting
The fictional protocol asks reviewers to record a reported safety concern and route it to a human. The assistant does not decide causality, severity, treatment, or real reporting obligations.

## Missing information
This reference does not contain dosing instructions, pregnancy guidance, pediatric guidance, drug comparisons, or treatment recommendations. Questions requiring those details cannot be answered from this document.
"""


def extract(filename, content):
    if filename.lower().endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        if len(reader.pages) > 100:
            raise ValueError("Please use a PDF with 100 pages or fewer.")
        sections = [
            (f"Page {index + 1}", page.extract_text() or "")
            for index, page in enumerate(reader.pages)
        ]
    elif filename.lower().endswith((".txt", ".md")):
        text = content.decode("utf-8-sig")
        sections = []
        heading = "Introduction"
        for block in re.split(r"(?m)^(#{1,3} .+)$", text):
            if block.startswith("#"):
                heading = block.lstrip("# ").strip()[:150]
            elif block.strip():
                sections.append((heading, block.strip()))
    else:
        raise ValueError("Choose a UTF-8 text file, Markdown file, or searchable PDF.")
    passages = []
    for locator, text in sections:
        # Conservative small chunks keep source locators useful; semantic/token-aware splitting is optional later.
        for index in range(0, len(text), 900):
            chunk = text[index : index + 900].strip()
            if chunk:
                passages.append((f"{locator} · {index // 900 + 1}", chunk))
    if not passages:
        raise ValueError(
            "No readable text found. Scanned PDFs need OCR before importing."
        )
    return passages


def ingest(session, filename, content, title, source="Local upload"):
    digest = hashlib.sha256(content).hexdigest()
    existing = session.scalar(
        select(Document).where(Document.digest == digest, Document.title == title)
    )
    if existing:
        return existing
    sections = extract(filename, content)
    version = (
        session.scalar(
            select(func.max(Document.version)).where(Document.title == title)
        )
        or 0
    ) + 1
    document = Document(title=title, version=version, digest=digest, source=source)
    session.add(document)
    session.flush()
    session.add_all(
        [
            Passage(document_id=document.id, locator=locator, text=text)
            for locator, text in sections
        ]
    )
    session.commit()
    return document


def seed(database):
    with database.session() as session:
        if not session.scalar(select(Document.id).limit(1)):
            ingest(
                session,
                "aster.md",
                DEMO_TEXT.encode(),
                "Aster · fictional study",
                "Bundled synthetic fixture",
            )
