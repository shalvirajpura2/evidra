"""Extraction routing and quality failures must happen before a document is indexed."""

import io
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter
from evidra.documents import extract_with_report, ingest
from evidra.db import Database, Document, ExtractionReport
from sqlalchemy import select, func


def blank_pdf(pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=600, height=800)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_scanned_pdf_routes_ocr_and_keeps_page_citations(monkeypatch):
    calls = []

    def recognize(content, index):
        calls.append(index)
        return f"Page {index+1}: returns are accepted within 37 days of delivery.", 94.0

    monkeypatch.setattr("evidra.ocr.pdf_page", recognize)
    passages, report = extract_with_report("scan.pdf", blank_pdf(2))
    assert calls == [0, 1]
    assert [p[0] for p in passages] == ["Page 1 · 1", "Page 2 · 1"]
    assert report["ocr_pages"][0]["confidence"] == 94.0
    assert report["warnings"]


def test_unreadable_scan_is_not_saved(monkeypatch, tmp_path):
    def failure(*args):
        raise ValueError("could not be read reliably")

    monkeypatch.setattr("evidra.ocr.pdf_page", failure)
    db = Database(f"sqlite:///{tmp_path / 'ocr.db'}")
    with db.session() as session, pytest.raises(ValueError, match="Page 1"):
        ingest(session, "scan.pdf", blank_pdf(), "Unreadable")
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 0
    db.engine.dispose()


def test_blank_pages_are_reported_and_ocr_budget_is_bounded(monkeypatch):
    monkeypatch.setattr(
        "evidra.ocr.pdf_page",
        lambda data, i: (
            ("", None)
            if i == 0
            else ("A readable scanned product guide with a 37 day return window.", 90)
        ),
    )
    passages, report = extract_with_report("mixed.pdf", blank_pdf(2))
    assert report["blank_pages"] == [1]
    assert passages[0][0] == "Page 2 · 1"
    monkeypatch.setattr(
        "evidra.ocr.pdf_page",
        lambda *args: (
            "A readable scanned product guide with a 37 day return window.",
            90,
        ),
    )
    with pytest.raises(ValueError, match="budget"):
        extract_with_report("longscan.pdf", blank_pdf(21))


def test_ocr_confidence_and_line_order(monkeypatch):
    from PIL import Image, ImageDraw
    from evidra.ocr import recognize

    image = Image.new("RGB", (500, 300), "white")
    ImageDraw.Draw(image).text((10, 10), "A readable document", fill="black")
    monkeypatch.setattr("evidra.ocr.shutil.which", lambda name: "tesseract")
    header = "block_num\tpar_num\tline_num\tconf\ttext\n"

    def tsv(score):
        return SimpleNamespace(
            stdout=(
                header
                + f"1\t1\t1\t{score}\tReturns\n1\t1\t1\t{score}\twithin\n1\t1\t2\t{score}\t37 days of delivery\n"
            ).encode()
        )

    monkeypatch.setattr("evidra.ocr.subprocess.run", lambda *a, **k: tsv(94))
    text, confidence = recognize(image)
    assert text == "Returns within\n37 days of delivery" and confidence == 94
    monkeypatch.setattr("evidra.ocr.subprocess.run", lambda *a, **k: tsv(32))
    with pytest.raises(ValueError, match="reliably"):
        recognize(image)


def test_image_upload_joins_normal_index_and_answer_pipeline(monkeypatch, tmp_path):
    from evidra.pipeline import execute
    from evidra.db import Passage

    monkeypatch.setenv("EVIDRA_PROVIDER", "extractive")
    monkeypatch.setenv("EVIDRA_RETRIEVAL", "lexical")
    monkeypatch.setattr(
        "evidra.ocr.image_text",
        lambda content: ("Returns are accepted within 37 days of delivery.", 93),
    )
    db = Database(f"sqlite:///{tmp_path / 'image.db'}")
    with db.session() as session:
        doc = ingest(session, "guide.png", b"fixture", "Returns")
        assert session.get(ExtractionReport, doc.id).report["ocr_pages"]
        passages = session.scalars(
            select(Passage).where(Passage.document_id == doc.id)
        ).all()
        answer = execute("How many days do I have to return an order?", passages)
        assert answer["disposition"] == "answer" and "37 days" in answer["answer"]
        assert answer["citations"] == [passages[0].id]
    db.engine.dispose()
