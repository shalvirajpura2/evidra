"""Bounded CPU OCR; confidence is a screening signal, not an accuracy guarantee."""

import csv
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from threading import BoundedSemaphore

OCR_SLOT = BoundedSemaphore(1)
RENDER_SLOT = BoundedSemaphore(1)
MAX_PIXELS = 12_000_000


def recognize(image):
    from PIL import ImageOps, ImageFilter

    executable = shutil.which(os.getenv("EVIDRA_TESSERACT", "tesseract"))
    if not executable:
        raise RuntimeError(
            "OCR is unavailable. Install Tesseract with English and Hindi language packs."
        )
    if image.width * image.height > MAX_PIXELS:
        raise ValueError(
            "This image is too large for OCR. Use an image below 12 megapixels."
        )
    image = ImageOps.exif_transpose(image).convert("L")
    # A nearly uniform page is blank, rather than an OCR failure.
    if image.getextrema()[1] - image.getextrema()[0] < 10:
        return "", None
    image = ImageOps.autocontrast(image).filter(ImageFilter.SHARPEN)
    if not OCR_SLOT.acquire(timeout=30):
        raise RuntimeError("OCR is busy. Please try again shortly.")
    try:
        with tempfile.TemporaryDirectory(prefix="evidra-ocr-") as directory:
            path = Path(directory) / "page.png"
            image.save(path)
            env = {**os.environ, "OMP_THREAD_LIMIT": "2"}
            try:
                result = subprocess.run(
                    [
                        executable,
                        str(path),
                        "stdout",
                        "-l",
                        "eng+hin",
                        "--psm",
                        "3",
                        "tsv",
                    ],
                    capture_output=True,
                    timeout=30,
                    check=True,
                    env=env,
                )
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
                raise RuntimeError(
                    "OCR could not complete this page. Try a clearer scan or text export."
                ) from error
        lines, confidence, weight = {}, 0.0, 0
        for row in csv.DictReader(
            io.StringIO(result.stdout.decode("utf-8")), delimiter="\t"
        ):
            word = row.get("text", "").strip()
            if not word or float(row["conf"]) < 0:
                continue
            key = tuple(row[k] for k in ("block_num", "par_num", "line_num"))
            lines.setdefault(key, []).append(word)
            confidence += float(row["conf"]) * len(word)
            weight += len(word)
        text = "\n".join(" ".join(words) for words in lines.values())
        score = round(confidence / weight, 1) if weight else 0.0
        if len(text.strip()) < 15 or score < 65:
            raise ValueError(
                "This page could not be read reliably by OCR. Upload a clearer scan or a text export."
            )
        return text, score
    finally:
        OCR_SLOT.release()


def pdf_page(content, index):
    import pypdfium2 as pdfium

    if not RENDER_SLOT.acquire(timeout=30):
        raise RuntimeError("PDF rendering is busy. Please try again shortly.")
    try:
        return _render_page(pdfium, content, index)
    finally:
        RENDER_SLOT.release()


def _render_page(pdfium, content, index):
    with pdfium.PdfDocument(content) as pdf:
        page = pdf[index]
        try:
            width, height = page.get_size()
            scale = min(300 / 72, (MAX_PIXELS / (width * height)) ** 0.5)
            bitmap = page.render(scale=scale)
            try:
                return recognize(bitmap.to_pil())
            finally:
                bitmap.close()
        finally:
            page.close()


def image_text(content):
    from PIL import Image

    with Image.open(io.BytesIO(content)) as image:
        return recognize(image)
