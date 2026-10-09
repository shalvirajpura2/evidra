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

Optional model adapters: Ollama software (MIT) and Qwen3-8B weights (Apache-2.0); faster-whisper software (MIT); Kokoro model weights (Apache-2.0). Model and voice assets have their own notices. They are not vendored in this repository.

The project plan discusses Docling, Sentence Transformers and pgvector as extension options. They are not part of the active base pipeline. See development notes for the exact current behavior.
