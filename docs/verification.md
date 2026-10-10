# Verification

Checked locally on Windows using Python 3.12 and the committed dependency lock.

- Backend: 10 tests passed, covering persistence, reference versions, routing, review decisions, evaluation jobs, provider failure, and invented citation IDs.
- Frontend: TypeScript checking and the Vite production build passed.
- Formatting: Black and Prettier checks passed.
- Browser: reference question, missing-dose abstention, review creation and resolution, saved evaluation progress, and mobile layout at 390 px were inspected.

The first saved Aster run matched 39 of 40 expected routes. The singular word "dose" exposed a gap in the document exclusion check. A regression test now covers it, and policy version `2026-10-10.2` checks exclusions across the selected reference. The next run matched 40 of 40 expected routes; the unfiltered excerpt baseline matched 12 of 40. [The saved run](example-run.json) includes configuration, source hash, per-case outputs, and measured timing.

These are public, synthetic regression fixtures. The policy was developed against them; this is not a held-out benchmark or an accuracy claim. The default tested path returns source excerpts and does not use a language model. PostgreSQL, OCR, and semantic retrieval were not exercised.

## Public and voice extension

The extended backend passed 12 tests, including independent visitor isolation across uploads, conversations, reviews, evaluation runs, forged tokens, and audio access. The voice-enabled frontend passed TypeScript and production build checks. Piper generated a synthetic WAV question which faster-whisper correctly recognized on Windows. The complete local API round trip returned the correct Aster enrollment answer and a 577,580-byte spoken WAV. The user also confirmed that Start voice hears their microphone input and speaks a reply. Interruption behavior and hosted latency remain unverified.

PyAV 19 was incompatible; version 16.1.0 is pinned for the speech path. Windows application-control policy blocked the PyTorch chat DLL. Linux staging initially stopped because ZeroGPU requires registered Gradio GPU functions and the standard launch hook. The adapter now provides those handlers and the frontend queue client. All 14 backend tests pass, including queued visitor isolation, input validation, context cleanup, evaluation persistence, and rejection of direct GPU-host API calls.

Private ZeroGPU staging successfully loaded Qwen2.5-1.5B-Instruct, faster-whisper base.en, and Piper. The hosted chat model answered the enrollment question with `52`, supported by the study-design passage, recording 880 ms of generation time excluding GPU queue waiting. A synthetic question recording was transcribed and then answered correctly, recording 747 ms of generation time. Read-aloud playback started without an application error. This does not measure live microphone quality on hosting or broad answer accuracy. The initial restart check exposed parallel session renewal creating conflicting visitor sessions; the frontend now shares one replacement token, and the subsequent hosted restart/question check passed.

Hosted missing-dose abstention, safety review creation, and review resolution passed. The hosted 40-case model evaluation completed within its GPU duration, matching 35/40 guarded routing decisions (87.5%) and 2/40 baseline decisions (5%). Five guarded cases did not match the expected route. These results are separate from the earlier 40/40 extractive policy run and must not be represented as model accuracy. The direct app tab hit the anonymous API run limit; the canonical signed-in Hugging Face view continued working and completed the evaluation through the official client's identity handshake. No account access token was copied into application code or shared among visitors.

Signed temporary sessions are implemented for the bounded public demo; this does not provide persistent user accounts.
