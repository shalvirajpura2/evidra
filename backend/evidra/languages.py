"""Dedicated Hindi-to-English translation for the document search query."""

from functools import lru_cache
from threading import BoundedSemaphore
import re

TRANSLATION_SLOT = BoundedSemaphore(1)


@lru_cache(maxsize=2)
def translation_pair(direction="hi-en"):
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    name = (
        "facebook/nllb-200-distilled-600M"
        if direction == "en-hi"
        else "Helsinki-NLP/opus-mt-hi-en"
    )
    tokenizer = AutoTokenizer.from_pretrained(
        name,
        use_fast=False,
        **({"src_lang": "eng_Latn"} if direction == "en-hi" else {}),
    )
    model = AutoModelForSeq2SeqLM.from_pretrained(name).to("cpu").eval()
    return tokenizer, model


def translate(text, direction):
    import torch

    if not TRANSLATION_SLOT.acquire(timeout=30):
        raise ValueError("Translation is busy")
    try:
        tokenizer, model = translation_pair(direction)
        inputs = tokenizer(text, return_tensors="pt")
        if inputs["input_ids"].shape[1] > 512:
            raise ValueError("Question is too long to translate")
        with torch.inference_mode():
            options = (
                {"forced_bos_token_id": tokenizer.convert_tokens_to_ids("hin_Deva")}
                if direction == "en-hi"
                else {}
            )
            output = model.generate(
                **inputs, max_new_tokens=160, num_beams=2, **options
            )
        result = tokenizer.decode(output[0], skip_special_tokens=True).strip()
        if not result or (
            direction == "hi-en" and re.search(r"[\u0900-\u097f]", result)
        ):
            raise ValueError("Could not translate the question")
        return result
    finally:
        TRANSLATION_SLOT.release()


def english_question(text):
    return translate(text, "hi-en")


def hindi_answer(text):
    result = translate(text, "en-hi")
    if re.search(r"[a-zA-Z]", result) and not re.search(r"[\u0900-\u097f]", result):
        raise ValueError("Translation did not produce Hindi")
    if re.findall(r"\d+(?:\.\d+)?", text) != re.findall(r"\d+(?:\.\d+)?", result):
        raise ValueError("Translation changed an answer's numbers")
    return result
