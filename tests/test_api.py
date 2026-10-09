from fastapi.testclient import TestClient

from evidra.api import create_app


def test_versions_reviews_and_evaluations_persist(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as client:
        demo = client.get("/api/documents").json()[0]
        body = {"question": "A participant had a rash.", "document_id": demo["id"]}
        result = client.post("/api/questions", json=body)
        assert result.status_code == 201
        assert result.json()["disposition"] == "review"
        review = client.get("/api/reviews").json()[0]
        assert (
            client.patch(
                f"/api/reviews/{review['id']}",
                json={"status": "resolved", "note": "Reviewed fictional fixture"},
            ).status_code
            == 200
        )
        assert (
            client.get("/api/reviews").json()[0]["note"] == "Reviewed fictional fixture"
        )
        first = client.post(
            "/api/documents",
            files={"file": ("guide.md", b"# Schedule\nThe workshop starts at noon.")},
            data={"title": "Guide"},
        ).json()
        second = client.post(
            "/api/documents",
            files={"file": ("guide.md", b"# Schedule\nThe workshop starts at two.")},
            data={"title": "Guide"},
        ).json()
        assert first["version"] == 1 and second["version"] == 2
        assert first["digest"] != second["digest"]
        old = client.get(f"/api/documents/{first['id']}").json()
        assert "noon" in old["passages"][0]["text"]
        assert (
            client.post(
                "/api/evaluations", json={"document_id": first["id"]}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/evaluations", json={"document_id": demo["id"]}
            ).status_code
            == 202
        )
        run = client.get("/api/evaluations").json()[0]
        assert run["status"] == "complete"
        assert run["completed"] == 40
        assert run["candidate"]["matched"] > run["baseline"]["matched"]
        assert run["config"]["baseline_name"] == "Unfiltered excerpts"
    with TestClient(create_app(f"sqlite:///{tmp_path / 'test.db'}")) as client:
        assert len(client.get("/api/documents").json()) == 3
        assert client.get("/api/reviews").json()[0]["status"] == "resolved"


def test_bad_upload_and_unknown_document(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'test.db'}")) as client:
        assert (
            client.post(
                "/api/documents", files={"file": ("bad.exe", b"not a document")}
            ).status_code
            == 422
        )
        assert client.get("/api/documents/missing").status_code == 404
        assert (
            client.post(
                "/api/questions", json={"question": " ", "document_id": "missing"}
            ).status_code
            == 422
        )
