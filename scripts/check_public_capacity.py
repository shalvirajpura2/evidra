"""Exercise ten isolated visitors against the public demo; optional GPU calls use quota."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from statistics import median
from time import perf_counter

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://rshalvi-evidra.hf.space")
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Submit ten real queued model questions; consumes free GPU quota",
    )
    args = parser.parse_args()
    started = perf_counter()

    def prepare(index):
        with httpx.Client(base_url=args.url, timeout=60) as client:
            response = client.post("/api/session")
            response.raise_for_status()
            token = response.json()["token"]
            client.headers["Authorization"] = "Bearer " + token
            sample = client.post("/api/demo")
            sample.raise_for_status()
            uploaded = client.post(
                "/api/documents",
                files={
                    "file": (
                        "capacity.md",
                        f"# Launch\nThe launch code is {7100 + index}.".encode(),
                    )
                },
            )
            uploaded.raise_for_status()
            doc = uploaded.json()
            return {"index": index, "token": token, "doc": doc["id"]}

    with ThreadPoolExecutor(max_workers=10) as pool:
        visitors = list(pool.map(prepare, range(10)))

    for index, visitor in enumerate(visitors):
        other = visitors[(index + 1) % 10]
        response = httpx.get(
            args.url + f"/api/documents/{visitor['doc']}",
            headers={"Authorization": "Bearer " + other["token"]},
            timeout=60,
        )
        assert (
            response.status_code == 404
        ), "Cross-visitor document access was not rejected"

    results = []
    if args.gpu:

        def question(visitor):
            began = perf_counter()
            try:
                with httpx.Client(base_url=args.url, timeout=240) as client:
                    job = client.post(
                        "/compute/gradio_api/call/ask",
                        json={
                            "data": [
                                visitor["token"],
                                {
                                    "question": "What is the launch code?",
                                    "document_id": visitor["doc"],
                                },
                            ]
                        },
                    )
                    job.raise_for_status()
                    event_id = job.json()["event_id"]
                    event = ""
                    with client.stream(
                        "GET", f"/compute/gradio_api/call/ask/{event_id}"
                    ) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if line.startswith("event: "):
                                event = line[7:]
                            elif line.startswith("data: ") and event in (
                                "complete",
                                "error",
                            ):
                                if event == "error":
                                    return {
                                        "ok": False,
                                        "error": "Hosted queue rejected the request",
                                        "seconds": round(perf_counter() - began, 2),
                                    }
                                data = json.loads(line[6:])[0]
                                turn = data.get("result", {})
                                expected = str(7100 + visitor["index"])
                                correct = (
                                    data.get("ok")
                                    and turn.get("disposition") == "answer"
                                    and expected in turn.get("answer", "")
                                )
                                audio_bytes = 0
                                if correct:
                                    audio = client.post(
                                        f"/api/voice/speak/{turn['id']}",
                                        headers={
                                            "Authorization": "Bearer "
                                            + visitor["token"]
                                        },
                                    )
                                    audio.raise_for_status()
                                    assert audio.content.startswith(b"RIFF")
                                    audio_bytes = len(audio.content)
                                return {
                                    "ok": bool(correct),
                                    "seconds": round(perf_counter() - began, 2),
                                    "audio_bytes": audio_bytes,
                                    "disposition": turn.get("disposition", "error"),
                                }
                    return {
                        "ok": False,
                        "error": "No terminal queue event",
                        "seconds": round(perf_counter() - began, 2),
                    }
            except httpx.HTTPError as error:
                return {
                    "ok": False,
                    "error": type(error).__name__,
                    "seconds": round(perf_counter() - began, 2),
                }

        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(question, visitors))

    metrics = {
        "visitors": len(visitors),
        "isolated_uploads": 10,
        "cross_visitor_rejections": 10,
        "real_gpu_requests": len(results),
        "correct_answers_with_audio": sum(row["ok"] for row in results),
        "elapsed_seconds": round(perf_counter() - started, 2),
        "results": results,
        "scope": "Synthetic documents, anonymous public REST clients. Free GPU quotas apply. Not a human microphone benchmark.",
    }
    if results:
        times = sorted(row["seconds"] for row in results)
        metrics.update(median_seconds=median(times), p95_seconds=times[-1])
    Path("data").mkdir(exist_ok=True)
    Path("data/public-capacity.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
