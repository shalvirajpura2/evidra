from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from evidra.api import create_app


def test_ten_concurrent_visitors_keep_documents_and_conversations_separate(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVIDRA_PUBLIC", "1")
    monkeypatch.setenv("EVIDRA_PROVIDER", "extractive")
    with TestClient(create_app()) as client:
        headers = [
            {"Authorization": "Bearer " + client.post("/api/session").json()["token"]}
            for _ in range(10)
        ]

        def visitor(index):
            header = headers[index]
            demo = client.post("/api/demo", headers=header)
            assert demo.status_code == 200
            repeated = client.post("/api/demo", headers=header)
            assert repeated.json()["id"] == demo.json()["id"]
            doc = client.post(
                "/api/documents",
                headers=header,
                files={
                    "file": (
                        "launch.md",
                        f"# Launch\nThe launch code is {7100 + index}.".encode(),
                    )
                },
            )
            assert doc.status_code == 201
            turn = client.post(
                "/api/questions",
                headers=header,
                json={
                    "question": "What is the launch code?",
                    "document_id": doc.json()["id"],
                },
            )
            assert turn.status_code == 201
            assert str(7100 + index) in turn.json()["answer"]
            return doc.json(), turn.json()

        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(visitor, range(10)))
        assert len({doc["id"] for doc, _ in results}) == 10
        for index, (doc, turn) in enumerate(results):
            other = headers[(index + 1) % 10]
            assert (
                client.get(f"/api/documents/{doc['id']}", headers=other).status_code
                == 404
            )
            assert (
                client.get(
                    f"/api/conversations/{turn['conversation_id']}", headers=other
                ).json()
                == []
            )
            assert (
                client.post(f"/api/voice/speak/{turn['id']}", headers=other).status_code
                == 404
            )


def test_hindi_question_keeps_original_and_searches_translated_evidence(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVIDRA_PROVIDER", "transformers")
    from evidra import models

    monkeypatch.setattr(
        models,
        "english_question",
        lambda text: "How many days of paid leave do employees receive?",
    )

    def generate(question, evidence, guarded, language):
        assert language == "hi" and guarded
        passage = next(item for item in evidence if "24 days" in item["text"])
        return {
            "answer": "कर्मचारियों को हर साल 24 दिन की छुट्टी मिलती है।",
            "citations": [passage["id"]],
        }

    monkeypatch.setattr(models, "generate", generate)
    with TestClient(create_app()) as client:
        doc = client.post("/api/demo").json()
        original = "मुझे साल में कितने दिन की छुट्टी मिलती है?"
        reply = client.post(
            "/api/questions",
            json={"question": original, "document_id": doc["id"], "language": "hi"},
        )
        assert reply.status_code == 201
        turn = reply.json()
        assert turn["question"] == original and turn["language"] == "hi"
        assert turn["disposition"] == "answer" and "24" in turn["answer"]
        assert turn["trace"][0]["stage"] == "Translate"
        assert any(
            "24 days" in item["text"]
            for item in turn["evidence"]
            if item["id"] in turn["citations"]
        )
        assert (
            client.post(
                "/api/questions",
                json={"question": original, "document_id": doc["id"], "language": "xx"},
            ).status_code
            == 422
        )


def test_failed_hindi_translation_does_not_store_an_invented_answer(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVIDRA_PROVIDER", "transformers")
    from evidra import models

    def failed(text):
        raise ValueError("Bad translation")

    monkeypatch.setattr(models, "english_question", failed)
    with TestClient(create_app()) as client:
        doc = client.post("/api/demo").json()
        assert (
            client.post(
                "/api/questions",
                json={
                    "question": "कितनी छुट्टी?",
                    "document_id": doc["id"],
                    "language": "hi",
                    "conversation_id": "hindi-test",
                },
            ).status_code
            == 503
        )
        assert client.get("/api/conversations/hindi-test").json() == []
