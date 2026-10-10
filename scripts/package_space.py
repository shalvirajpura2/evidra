"""Build a source allowlist plus compiled UI; never include runtime data or secrets."""

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
output = root / "deploy/huggingface/evidra.zip"
files = sorted((root / "backend").rglob("*.py"))
files += sorted(path for path in (root / "frontend/dist").rglob("*") if path.is_file())
files += sorted(
    path
    for path in (root / "frontend/src").rglob("*")
    if path.suffix in (".ts", ".tsx", ".css")
)
files += [
    root / "pyproject.toml",
    root / "docs/system-design.md",
    root / "docs/decisions.md",
    root / "docs/open-source.md",
    root / "docs/deployment.md",
]
assert (root / "frontend/dist/index.html").is_file(), "Build the frontend first"
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for path in files:
        if "__pycache__" not in path.parts:
            archive.write(path, path.relative_to(root).as_posix())
print(
    f"Packaged {len(files)} app files; SHA256 {hashlib.sha256(output.read_bytes()).hexdigest()}"
)
