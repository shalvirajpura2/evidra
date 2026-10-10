from fastapi.testclient import TestClient

from evidra.api import GPU_CALL, create_app
from evidra.queued import queued_call


def test_gpu_queue_preserves_visitor_boundaries(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVIDRA_PUBLIC", "1")
    monkeypatch.setenv("EVIDRA_ZERO_GPU", "1")
    app = create_app()
    with TestClient(app) as client:
        a = client.post("/api/session").json()["token"]
        b = client.post("/api/session").json()["token"]
        headers_a = {"Authorization": "Bearer " + a}
        headers_b = {"Authorization": "Bearer " + b}
        doc = client.get("/api/documents", headers=headers_a).json()[0]
        client.get("/api/documents", headers=headers_b)
        payload = {
            "question": "How many participants enrolled?",
            "document_id": doc["id"],
        }
        assert (
            client.post("/api/questions", headers=headers_a, json=payload).status_code
            == 503
        )
        assert not queued_call(app, "ask", "forged", payload)["ok"]
        assert not queued_call(app, "ask", b, payload)["ok"]
        answer = queued_call(app, "ask", a, payload)
        assert answer["ok"] and answer["result"]["disposition"] == "answer"
        conversation = answer["result"]["conversation_id"]
        assert (
            len(
                client.get(
                    f"/api/conversations/{conversation}", headers=headers_a
                ).json()
            )
            == 1
        )
        assert (
            client.get(f"/api/conversations/{conversation}", headers=headers_b).json()
            == []
        )
        assert not GPU_CALL.get()
        assert app.state.database.current() is app.state.database.local


def test_gpu_queue_evaluation_persists_progress_and_validates_input(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVIDRA_PUBLIC", "1")
    monkeypatch.setenv("EVIDRA_ZERO_GPU", "1")
    app = create_app()
    with TestClient(app) as client:
        token = client.post("/api/session").json()["token"]
        headers = {"Authorization": "Bearer " + token}
        doc = client.get("/api/documents", headers=headers).json()[0]
        assert not queued_call(app, "ask", token, {"question": "x" * 4001})["ok"]
        assert (
            client.post(
                "/api/evaluations", headers=headers, json={"document_id": doc["id"]}
            ).status_code
            == 503
        )
        result = queued_call(app, "evaluate", token, {"document_id": doc["id"]})
        assert result["ok"]
        run = client.get("/api/evaluations", headers=headers).json()[0]
        assert run["status"] == "complete" and run["completed"] == 40
