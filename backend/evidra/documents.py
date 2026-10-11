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

HANDBOOK_TEXT = """# Northstar team handbook
Northstar is a fictional company. This sample has no real employee information.

## Time off
Employees receive 24 days of paid leave each year. To request leave, submit the dates to your team lead at least five working days in advance.

## Working together
The team works remotely. Core collaboration hours are 11 AM to 3 PM India Standard Time, Monday through Friday. The weekly team meeting is on Monday at 11 AM India Standard Time.

## Equipment
New employees can claim up to 30,000 Indian rupees for work equipment. Send the receipt to the operations team within 30 days of purchase.

## First week
On your first day, meet your buddy, set up your work accounts, and read the security guide. The operations team helps with equipment and account access.

## Information not provided
This handbook does not include salaries, individual employee records, or promotion criteria. Do not invent those details.
"""


def split_text(text, limit=1100, overlap=180):
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text).strip()
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            window = text[start + limit // 2 : end]
            boundaries = list(re.finditer(r"[.!?।]\s+|\n\n", window))
            if boundaries:
                end = start + limit // 2 + boundaries[-1].end()
            else:
                boundary = text.rfind(" ", start + limit // 2, end)
                if boundary > start:
                    end = boundary
        yield text[start:end].strip()
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
        boundary = text.find(" ", start, min(start + 50, end))
        if boundary != -1:
            start = boundary + 1


def extract(filename, content):
    if filename.lower().endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise ValueError(
                "This PDF is encrypted. Export an unlocked text PDF first."
            )
        if len(reader.pages) > 100:
            raise ValueError("Please use a PDF with 100 pages or fewer.")
        sections = [
            (f"Page {index + 1}", page.extract_text(extraction_mode="layout") or "")
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
        for index, chunk in enumerate(split_text(text)):
            if chunk:
                passages.append((f"{locator} · {index + 1}", chunk))
    if not passages:
        raise ValueError(
            "No readable text found. Scanned PDFs need OCR before importing."
        )
    if (
        filename.lower().endswith(".pdf")
        and sum(len(text) for _, text in passages) < 40
    ):
        raise ValueError(
            "Too little readable text was extracted. Export a text PDF or run OCR first."
        )
    if len(passages) > 600:
        raise ValueError(
            "This document is too long to index here. Split it into smaller documents (up to 600 passages each)."
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
    session.flush()
    from .retrieval import enabled, index_passages

    if enabled():
        index_passages(
            session,
            session.scalars(
                select(Passage).where(Passage.document_id == document.id)
            ).all(),
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
