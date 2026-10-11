from types import SimpleNamespace
import pytest
from evidra.overview import is_overview, overview_evidence
from evidra.pipeline import execute
from evidra.models import validate_grounding
from evidra.documents import split_text


def test_generic_pdf_overview_is_answered_without_keyword_matches(monkeypatch):
    monkeypatch.setenv("EVIDRA_PROVIDER", "extractive")
    passages = [
        SimpleNamespace(id=str(i), locator=f"Page {i+1}", text=text)
        for i, text in enumerate(
            [
                "A founder builds sales automation.",
                "Previous roles in finance and research.",
                "Education includes electrical engineering.",
            ]
        )
    ]
    result = execute("what is this pdf about", passages)
    assert result["disposition"] == "answer"
    assert result["overview_complete"]
    assert result["citations"] == ["0", "1", "2"]
    assert "Education" in result["answer"]


def test_long_overview_covers_start_middle_and_end_and_reports_sampling():
    passages = [
        SimpleNamespace(id=str(i), locator=f"Page {i}", text="x" * 1000)
        for i in range(100)
    ]
    evidence, complete = overview_evidence(passages)
    assert not complete
    assert evidence[0]["id"] == "0" and evidence[-1]["id"] == "99"
    assert any(40 < int(e["id"]) < 60 for e in evidence)
    assert sum(len(e["text"]) for e in evidence) <= 8800
    assert is_overview("summarize this file")
    assert not is_overview("What is the refund policy?")


def test_grounding_rejects_invented_quote_and_number():
    evidence = [{"id": "a", "text": "The return window is 30 days after delivery."}]
    valid = {
        "answer": "Returns are accepted within 30 days.",
        "citations": ["a"],
        "quotes": [{"id": "a", "text": "The return window is 30 days after delivery."}],
    }
    assert validate_grounding(valid, evidence) == valid
    with pytest.raises(ValueError):
        validate_grounding(
            {**valid, "answer": "Returns are accepted within 60 days."}, evidence
        )
    with pytest.raises(ValueError):
        validate_grounding(
            {
                **valid,
                "quotes": [{"id": "a", "text": "Everyone receives a free refund."}],
            },
            evidence,
        )
    for malformed in [
        [],
        {"answer": None},
        {**valid, "quotes": ["bad"]},
        {**valid, "citations": [None]},
    ]:
        with pytest.raises(ValueError):
            validate_grounding(malformed, evidence)


def test_chunk_overlap_keeps_boundary_fact_searchable():
    fact = "Return the equipment within 30 days after delivery."
    chunks = list(
        split_text(("Background sentence. " * 45) + fact + (" More context." * 100))
    )
    assert len(chunks) > 1
    assert any(fact in chunk for chunk in chunks)
    assert all(len(chunk) <= 1100 for chunk in chunks)


def test_grounding_accepts_numbers_written_as_words():
    from evidra.models import number_values

    assert number_values("thirty thousand and five days") == {"30005"}
    source = "Submit the dates at least five working days in advance."
    assert validate_grounding(
        {
            "answer": "Submit dates 5 working days ahead.",
            "citations": ["a"],
            "quotes": [{"id": "a", "text": source}],
        },
        [{"id": "a", "text": source}],
    )


def test_model_selects_sources_and_server_copies_exact_text():
    from evidra.models import source_snippets, resolve_sources

    evidence = [
        {
            "id": "a",
            "text": "Doctoral work at MIT focused on auditory physics. Returns are accepted within 37 days.",
        }
    ]
    snippets = source_snippets(evidence)
    result = resolve_sources(
        {
            "answer": "He completed his doctoral work at MIT.",
            "sources": [snippets[0]["id"]],
        },
        snippets,
    )
    assert result["citations"] == ["a"]
    assert result["quotes"][0]["text"] in evidence[0]["text"]
    assert validate_grounding(result, evidence) == result
    with pytest.raises(ValueError, match="source selection"):
        resolve_sources({"answer": "Invented", "sources": ["99.1"]}, snippets)
    empty = resolve_sources({"answer": "", "sources": []}, snippets)
    assert validate_grounding(empty, evidence)["citations"] == []


def test_index_is_reused_and_upload_rolls_back_if_indexing_fails(monkeypatch, tmp_path):
    from sqlalchemy import select, func
    from evidra.db import Database, Passage, PassageEmbedding, Document
    from evidra.documents import ingest
    from evidra.retrieval import index_passages

    monkeypatch.setenv("EVIDRA_RETRIEVAL", "hybrid")
    calls = []

    def encode(texts, **kwargs):
        calls.append(texts)
        return [[0.1, 0.2] for _ in texts]

    monkeypatch.setattr("evidra.retrieval.embed", encode)
    db = Database(f"sqlite:///{tmp_path / 'indexed.db'}")
    with db.session() as s:
        doc = ingest(
            s, "guide.md", b"# Returns\nReturns are accepted within 30 days.", "Guide"
        )
        ps = s.scalars(select(Passage).where(Passage.document_id == doc.id)).all()
        assert len(index_passages(s, ps)) == len(ps)
        assert len(calls) == 1
        assert s.scalar(select(func.count()).select_from(PassageEmbedding)) == len(ps)

    def failure(*args, **kwargs):
        raise RuntimeError("index unavailable")

    monkeypatch.setattr("evidra.retrieval.embed", failure)
    with pytest.raises(RuntimeError), db.session() as s:
        ingest(
            s, "other.md", b"# Other\nAnother document with separate facts.", "Other"
        )
    with db.session() as s:
        assert s.scalar(select(func.count()).select_from(Document)) == 1
    db.engine.dispose()
