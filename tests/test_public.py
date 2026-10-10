from fastapi.testclient import TestClient

from evidra.api import create_app


def test_public_visitors_cannot_read_each_others_data(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVIDRA_PUBLIC", "1")
    with TestClient(create_app()) as client:
        assert client.get("/api/documents").status_code == 401
        a = {"Authorization": "Bearer " + client.post("/api/session").json()["token"]}
        b = {"Authorization": "Bearer " + client.post("/api/session").json()["token"]}
        doc = client.post(
            "/api/documents",
            headers=a,
            files={"file": ("guide.md", b"# Timing\nThe workshop starts at noon.")},
        ).json()
        assert client.get(f"/api/documents/{doc['id']}", headers=b).status_code == 404
        assert all(
            item["id"] != doc["id"]
            for item in client.get("/api/documents", headers=b).json()
        )
        turn = client.post(
            "/api/questions",
            headers=a,
            json={
                "question": "What time does the workshop start?",
                "document_id": doc["id"],
            },
        ).json()
        assert (
            client.get(
                f"/api/conversations/{turn['conversation_id']}", headers=b
            ).json()
            == []
        )
        assert (
            client.post(f"/api/voice/speak/{turn['id']}", headers=b).status_code == 404
        )
        assert client.get(f"/api/documents/{doc['id']}", headers=a).status_code == 200
        forged = {
            "Authorization": a["Authorization"][:-1]
            + ("0" if a["Authorization"][-1] != "0" else "1")
        }
        assert client.get("/api/documents", headers=forged).status_code == 401


def test_public_review_and_evaluation_scope(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVIDRA_PUBLIC", "1")
    with TestClient(create_app()) as client:
        a = {"Authorization": "Bearer " + client.post("/api/session").json()["token"]}
        b = {"Authorization": "Bearer " + client.post("/api/session").json()["token"]}
        demo = client.get("/api/documents", headers=a).json()[0]
        client.post(
            "/api/questions",
            headers=a,
            json={"question": "A participant had a rash", "document_id": demo["id"]},
        )
        review = client.get("/api/reviews", headers=a).json()[0]
        assert client.get("/api/reviews", headers=b).json() == []
        assert (
            client.patch(
                f"/api/reviews/{review['id']}", headers=b, json={"status": "resolved"}
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/evaluations", headers=a, json={"document_id": demo["id"]}
            ).status_code
            == 202
        )
        assert (
            client.get("/api/evaluations", headers=a).json()[0]["status"] == "complete"
        )
        assert client.get("/api/evaluations", headers=b).json() == []
