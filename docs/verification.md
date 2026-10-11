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

## Guided experience and Hindi checks — October 10, 2026

- 17 backend tests passed, including ten concurrent visitors creating samples, uploading distinct documents, asking questions, and attempting cross-visitor document, conversation and audio access. The model in this concurrency test is extractive; it proves HTTP/database boundaries, not GPU throughput.
- Hindi API tests use model doubles to verify original transcript retention, translated retrieval, citation validation and fail-closed translation handling. They do not establish translation quality.
- Actual Piper Hindi synthesis produced a 111,660-byte WAV for “मुझे साल में कितने दिन की छुट्टी मिलती है?” Multilingual Whisper small returned “मुझे साल में कितने दिन की चुटी मिलती है”, including a spelling error. This is a synthetic speech check, not a human accent or microphone benchmark.
- The guided frontend passed TypeScript and Vite builds. Browser checks confirmed sample onboarding and an English answer with its supporting passage. The desktop browser did not apply the requested phone viewport override, so device-sized visual QA is not yet verified.
- Sixteen original GitHub commit messages were changed to lowercase conventional prefixes. Commit trees, authors and timestamps were preserved. The complete prior history is in the ignored local bundle `data/history-before-message-change.bundle`.

The public HTTP capacity probe created ten independent visitor workspaces and distinct uploads concurrently. All ten cross-visitor document requests returned 404. Ten anonymous GPU jobs were rejected by the Hugging Face runs quota; ten-user model throughput is therefore unverified. Signed-in canonical-browser requests succeeded with the English paid-leave answer and source.

The first Hindi release failed a real user microphone check: the transcript was misspelled and retrieval abstained. Dedicated hi-en translation recovered a clean question, but the chat model returned malformed Hindi. The corrected path uses Whisper medium for Hindi and translates a validated English answer through Marian en-hi, rejecting changed numbers. Eighteen backend tests pass, including a number-preservation regression. Hosted checks below record actual model behavior separately from test doubles.

The hosted Hindi correction answered both the clean question and the actual synthetic Whisper transcript with `24 दिन`, citing Time off. Playback started successfully. Whisper medium returned `मुझे साल में कितने दिन की चुटी मिलती हैं` in 6.29 seconds for the synthetic clip. The user reported improved answers but unreliable recording; complete-question sending is now the default, with optional automatic pause detection at 2.4 seconds.

An initial ten-way Hindi ASR burst completed eight jobs and rejected two after the 30-second slot wait. Successful jobs took 9.83–38.94 seconds including waiting. The wait was extended to 60 seconds; the next measured result is recorded below. This does not measure long recordings or full ten-user GPU throughput.

The repeated ten-way hosted Hindi transcription test completed 10/10 requests with HTTP 200. End-to-end ASR times including queue waits ranged from 10.29 to 52.76 seconds for the same short synthetic clip. Ten independent uploads and ten cross-visitor document rejections passed again. Run `python scripts/check_public_capacity.py --audio <synthetic-hindi.wav>` to repeat. This probe does not prove ten simultaneous human conversations or bypass per-visitor GPU quotas.

The final public build reported all models ready and showed complete-question sending with optional automatic pause detection. The clean Hindi leave question returned `24 दिन` with the Time off source in 2.3 seconds of processing; reply playback started. English equipment reimbursement returned the correct receipt procedure in 0.9 seconds. Its Hindi paraphrase still required review, so broad Hindi answer reliability remains unverified. The user has not yet confirmed the final manual-send recording controls on their microphone.

## Uploaded-document pipeline — October 11, 2026

The reported question “what is this PDF about” failed because the old keyword route removed most generic question words and required a specific fact match. An explicit overview route now includes all extracted passages for short documents and discloses sampling for longer files. Upload builds a persisted E5 index; fact questions combine BM25 and semantic candidates with cross-encoder reranking. Transformers answers require exact supporting quotes and source-backed numeric values.

- The attached three-page English PDF imported successfully through the API into seven passages. The overview route included all seven and returned an answer in local extractive mode. This verifies extraction and coverage, not generated-summary accuracy.
- Real CPU ONNX retrieval selected relevant passages for company, education, and prior-role questions from that PDF. It also selected candidates for an absent salary question, confirming that semantic similarity alone cannot establish answerability; the answer model must abstain on missing evidence.
- Ten independent visitors uploaded unfamiliar synthetic guides and retrieved their distinct return windows using real ONNX retrieval. All ten matched the expected source facts; all ten cross-visitor document reads returned 404. The combined local probe took 4.43 seconds, excluding model-generation and voice work.
- 24 backend tests passed, including overview routing, long-document coverage disclosure, exact-quote rejection, numeric validation, persisted-index reuse, rollback on failed indexing, and existing isolation/voice boundaries. The frontend TypeScript/Vite build passed.
- The first hosted build exposed Tokenizers 0.23.1's Hub dependency conflict. The corrected pin is Tokenizers 0.23.3, whose declared dependency supports the installed Hub version. Hosted generation checks are recorded separately after deployment.

## OCR import checks — October 11, 2026

Tesseract 5 with English/Hindi language packs is installed in the public Space. PDFium renders unreadable/image-bearing PDF pages; text PDFs retain their readable layer. Imports preserve page references, report OCR use and blank pages, and reject unreliable OCR before indexing. The bounded demo allows 20 OCR pages per upload; it does not promise perfect handwriting, tables or image interpretation.

- 29 backend tests passed, covering OCR routing, page references, low-confidence rejection, blank pages, processing limits, database rollback and OCR-text answers through the normal document pipeline. Tesseract calls are mocked in these unit tests; actual hosted checks below are separate.
- Real hosted uploads of a synthetic PNG and its image-only PDF returned HTTP 201. Both preserved the 37-day return window and original-receipt instruction. Tesseract's character-weighted confidence was 96.4 and 96.1 respectively; those scores are not measured transcription accuracy.
- The original three-page text PDF still extracts into seven passages without using OCR. Adding OCR does not by itself resolve generated-answer failures.
- TypeScript/Vite builds and formatting passed. GitHub Actions run 38111601398 passed for commit f3a9b9a.
- An anonymous model request hit the ZeroGPU runs limit. No token or alternate identity was used to bypass it. The signed-in canonical browser successfully generated a readable overview of a separately uploaded four-page English profile PDF, citing three passages in 5.2 seconds of processing. This is one real unfamiliar-document check, not an all-document accuracy benchmark.
