# Evaluation protocol

The bundled suite uses fictional reference content. Cases include supported facts, absent information, ambiguous questions, follow-ups, safety mentions and attempted instruction overrides. Expected routing is defined before measuring the candidate.

Local mode compares an unfiltered excerpt-retrieval baseline with the guarded pipeline. Both use the same document and retrieval code. This is not a plain-LLM comparison; the dashboard names it accordingly. Ollama mode compares an unguarded model response with the same model plus retrieval and policy checks.

Scores report agreement with expected answer/abstain/review decisions. Citation validity checks that returned passage IDs exist in the retrieved set. They do not assess medical correctness. Each result includes the question, expected and observed decisions, evidence and elapsed time. No fixture score is advertised as clinical accuracy.

Run records include provider, model, policy and dataset versions. A run is reproducible at the configuration/case level; model output can still vary. The bundled cases are public regression fixtures, not a held-out benchmark. Independent manual review and a separate held-out set are future work.

