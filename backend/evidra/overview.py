"""Give overview questions coverage across the document instead of top-k matches."""

import re


def is_overview(question):
    return bool(
        re.search(
            r"\b(summari[sz]e|summary|overview|main (?:points|topics)|what (?:is|does) (?:this|the) (?:pdf|document|file|report|profile) (?:about|cover|say)|what(?:'s| is) (?:in|inside) (?:this|the) (?:pdf|document|file))\b",
            question,
            re.I,
        )
    )


def overview_evidence(passages, budget=8800):
    # Keep document order. Small documents fit in full; long documents include
    # evenly spaced passages, including both the beginning and the ending.
    ordered = list(passages)
    if ordered and all(re.match(r"Page \d+", p.locator) for p in ordered):
        ordered.sort(key=lambda p: tuple(int(n) for n in re.findall(r"\d+", p.locator)))
    total = sum(len(p.text) for p in ordered)
    count = len(ordered) if total <= budget else min(8, len(ordered))
    indices = sorted(
        {round(i * (len(ordered) - 1) / max(count - 1, 1)) for i in range(count)}
    )
    chosen = [ordered[i] for i in indices]
    allowance = budget // max(len(chosen), 1)
    evidence = [
        {
            "id": p.id,
            "locator": p.locator,
            "text": p.text if total <= budget else p.text[:allowance],
            "score": 1.0,
            "retrieval": "overview",
        }
        for p in chosen
    ]
    complete = total <= budget
    return evidence, complete
