"""CPU hybrid retrieval, with persisted document embeddings and a cross encoder."""

from collections import Counter
from functools import lru_cache
import math
import os
import re
from threading import BoundedSemaphore

from sqlalchemy import select

from .db import PassageEmbedding

EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
INDEX_VERSION = EMBEDDING_MODEL + ":mean-normalized-v1"
CPU_SLOT = BoundedSemaphore(1)


def enabled():
    return os.getenv("EVIDRA_RETRIEVAL", "lexical") == "hybrid"


@lru_cache(maxsize=2)
def encoder(kind="embedding"):
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer

    name = EMBEDDING_MODEL if kind == "embedding" else RERANK_MODEL
    folder = "data/models/retrieval/" + ("e5" if kind == "embedding" else "reranker")
    weights = hf_hub_download(name, "onnx/model.onnx", local_dir=folder)
    tokenizer = Tokenizer.from_file(
        hf_hub_download(name, "tokenizer.json", local_dir=folder)
    )
    tokenizer.enable_truncation(max_length=512)
    tokenizer.enable_padding(pad_id=1 if kind == "embedding" else 0)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    return tokenizer, ort.InferenceSession(
        weights, sess_options=options, providers=["CPUExecutionProvider"]
    )


def infer(kind, texts):
    import numpy as np

    tokenizer, model = encoder(kind)
    encodings = tokenizer.encode_batch(texts)
    values = {
        "input_ids": np.array([item.ids for item in encodings], dtype=np.int64),
        "attention_mask": np.array(
            [item.attention_mask for item in encodings], dtype=np.int64
        ),
        "token_type_ids": np.array(
            [item.type_ids for item in encodings], dtype=np.int64
        ),
    }
    output = model.run(
        None, {item.name: values[item.name] for item in model.get_inputs()}
    )[0]
    if kind == "reranker":
        return output.reshape(-1)
    mask = values["attention_mask"][..., None]
    pooled = (output * mask).sum(1) / mask.sum(1).clip(min=1)
    return pooled / np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-12)


def embed(texts, query=False):
    if not CPU_SLOT.acquire(timeout=60):
        raise ValueError("Document search is busy. Please try again.")
    try:
        import numpy as np

        prefix = "query: " if query else "passage: "
        batches = [
            infer("embedding", [prefix + text for text in texts[start : start + 8]])
            for start in range(0, len(texts), 8)
        ]
        return np.concatenate(batches).tolist() if batches else []
    finally:
        CPU_SLOT.release()


def index_passages(session, passages):
    ids = [p.id for p in passages]
    if not ids:
        return {}
    existing = session.scalars(
        select(PassageEmbedding).where(
            PassageEmbedding.passage_id.in_(ids),
            PassageEmbedding.model == INDEX_VERSION,
        )
    ).all()
    vectors = {row.passage_id: row.vector for row in existing}
    missing = [p for p in passages if p.id not in vectors]
    if not missing:
        return vectors
    for passage, vector in zip(
        missing, embed([p.locator + "\n" + p.text for p in missing])
    ):
        session.add(
            PassageEmbedding(passage_id=passage.id, model=INDEX_VERSION, vector=vector)
        )
        vectors[passage.id] = vector
    session.flush()
    return vectors


def words(text):
    return re.findall(r"\w+", text.lower())


def hybrid_retrieve(question, passages, vectors=None):
    import numpy as np

    if not passages:
        return []
    documents = [p.locator + "\n" + p.text for p in passages]
    matrix = np.array(
        [vectors[p.id] for p in passages] if vectors is not None else embed(documents)
    )
    query = np.array(embed([question], query=True)[0])
    similarities = matrix @ query
    terms = set(words(question))
    counts = [Counter(words(text)) for text in documents]
    average = sum(sum(row.values()) for row in counts) / max(len(counts), 1)
    lexical = []
    for row in counts:
        length = sum(row.values())
        score = 0.0
        for term in terms:
            frequency = row[term]
            df = sum(term in other for other in counts)
            idf = math.log(1 + (len(counts) - df + 0.5) / (df + 0.5))
            score += (
                idf
                * frequency
                * 2.2
                / (frequency + 1.2 * (0.25 + 0.75 * length / max(average, 1)))
            )
        lexical.append(score)
    fused = {}
    for order in (np.argsort(-similarities)[:16], np.argsort(-np.array(lexical))[:16]):
        for rank, index in enumerate(order):
            fused[int(index)] = fused.get(int(index), 0) + 1 / (60 + rank)
    candidates = sorted(fused, key=fused.get, reverse=True)[:12]
    if not CPU_SLOT.acquire(timeout=60):
        raise ValueError("Document search is busy. Please try again.")
    try:
        logits = infer(
            "reranker", [(question, documents[index]) for index in candidates]
        )
    finally:
        CPU_SLOT.release()
    ranked = sorted(zip(candidates, logits), key=lambda item: item[1], reverse=True)
    return [
        {
            "id": passages[i].id,
            "locator": passages[i].locator,
            "text": passages[i].text,
            "score": round(
                min(
                    1.0,
                    max(
                        1 / (1 + math.exp(-max(-30, min(30, float(logit))))),
                        max(0, (float(similarities[i]) - 0.72) / 0.25),
                    ),
                ),
                4,
            ),
            "semantic_score": round(float(similarities[i]), 4),
            "rerank_logit": round(float(logit), 4),
            "retrieval": "hybrid",
        }
        for i, logit in ranked[:4]
    ]
