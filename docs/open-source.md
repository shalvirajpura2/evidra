# Dependencies and original work

Evidra's application code is independent. The doodles are original SVG paths. Retain upstream notices when distributing dependencies; the private repository does not grant a public license to the application itself.

| Component | Role | Upstream license |
|---|---|---|
| FastAPI | API framework | MIT |
| React, Vite | Interface and build tooling | MIT |
| SQLAlchemy | Database access | MIT |
| pypdf | Searchable PDF extraction | BSD-3-Clause |
| httpx | Local model HTTP client | BSD-3-Clause |
| Lucide | Interface icons | ISC |
| DM Sans, Kalam | Interface fonts | SIL Open Font License |
| pytest | Regression tests | MIT |
| Black | Python formatting | MIT |
| Prettier | Frontend formatting | MIT |

Model adapters: Ollama software (MIT) and Qwen3-8B weights (Apache-2.0); the hosted demo's Qwen3-4B-Instruct-2507 weights (Apache-2.0), Transformers (Apache-2.0), PyTorch (BSD-3-Clause), and faster-whisper software (MIT). Speech uses Piper (GPL-3.0) with the public ljspeech-medium voice; its model card and LJSpeech dataset notice must be retained when distributing the voice. Model assets are downloaded separately and are not vendored in this repository. The previous optional Kokoro adapter has been replaced by Piper.

The project plan discusses Docling, Sentence Transformers and pgvector as extension options. They are not part of the active base pipeline. See development notes for the exact current behavior.

## Hindi voice

Hindi speech uses Piper's `hi_IN-pratham-medium` voice. Its [individual model card](https://huggingface.co/rhasspy/piper-voices/blob/main/hi/hi_IN/pratham/medium/MODEL_CARD) specifies **CC-BY-NC-SA-4.0** for the dataset. This restriction is separate from the repository's general license badge. The hosted application is a noncommercial portfolio demonstration; do not offer this voice as a commercial service without appropriate rights or replacing it with a suitably licensed voice. Keep attribution and share-alike notices with redistributed assets. Voice weights remain outside the GitHub repository and source archive.

Whisper small handles English; Whisper medium handles Hindi. Marian OPUS hi-en translates Hindi questions to English for retrieval (Apache-2.0). The initial Marian en-hi reply translator was replaced after hosted quality testing. Reply translation must preserve numbers; failed translation withholds the draft. This does not establish Hindi document retrieval or translation accuracy.

Hindi reply translation uses [Meta NLLB distilled 600M](https://huggingface.co/facebook/nllb-200-distilled-600M), CC-BY-NC-4.0, after Marian en-hi mistranslated a meeting time in hosted testing. It is a research model used here for a noncommercial portfolio demo, not certified or production translation. Marian hi-en remains Apache-2.0. Number preservation is checked; semantic translation errors remain possible.

The final Hindi path uses one shared NLLB model for both directions, with explicit source/target language tokens. Marian was removed after it distorted the equipment-reimbursement question. The translation weights are CC-BY-NC-4.0; component code remains separately licensed.

Active document retrieval uses [multilingual E5 small](https://huggingface.co/intfloat/multilingual-e5-small) (MIT weights), ONNX Runtime (MIT), Hugging Face Tokenizers (Apache-2.0), and the [MiniLM cross encoder](https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2). These weights are downloaded separately, never committed.
