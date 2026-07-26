"""Lazy-loading wrapper for the Google DePlot model."""

import hashlib
import os
import threading
from collections import OrderedDict
from contextlib import nullcontext
from typing import Any, Optional

from PIL import Image

from chart_detection import crop_pie_plot, detect_chart_type
from chart_text import (
    InvalidExtractedChartData,
    add_chart_type_metadata,
    normalize_deplot_numeric_precision,
    normalize_pie_deplot_text,
)

try:
    from transformers import Pix2StructForConditionalGeneration, Pix2StructProcessor
except ImportError:
    Pix2StructForConditionalGeneration = None
    Pix2StructProcessor = None

try:
    import torch
except ImportError:
    torch = None


MODEL_NAME = "google/deplot"
_processor: Optional[Any] = None
_model: Optional[Any] = None
_inference_lock = threading.Lock()
_raw_table_cache: OrderedDict[str, str] = OrderedDict()
_result_cache: OrderedDict[tuple[str, str], str] = OrderedDict()


def _cache_limit() -> int:
    try:
        return max(1, min(128, int(os.getenv("DEPLOT_CACHE_SIZE", "32"))))
    except ValueError:
        return 32


def _cache_get(cache: OrderedDict, key):
    value = cache.get(key)
    if value is not None:
        cache.move_to_end(key)
    return value


def _cache_set(cache: OrderedDict, key, value: str) -> None:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > _cache_limit():
        cache.popitem(last=False)


def _image_digest(image_path: str) -> str:
    digest = hashlib.sha256()
    with open(image_path, "rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _max_new_tokens() -> int:
    try:
        return max(64, min(512, int(os.getenv("DEPLOT_MAX_NEW_TOKENS", "256"))))
    except ValueError:
        return 256


def _ensure_model_loaded() -> None:
    global _processor, _model
    if _processor is not None and _model is not None:
        return
    if Pix2StructProcessor is None or Pix2StructForConditionalGeneration is None:
        raise RuntimeError("DePlot requires the transformers and pillow packages")

    try:
        if torch is not None:
            torch.set_num_threads(
                max(1, min(8, int(os.getenv("DEPLOT_TORCH_THREADS", "2"))))
            )
        _processor = Pix2StructProcessor.from_pretrained(MODEL_NAME)
        _model = Pix2StructForConditionalGeneration.from_pretrained(MODEL_NAME)
        _model.eval()
    except Exception as exc:
        raise RuntimeError(f"Failed to load DePlot model: {exc}") from exc


def extract_table_from_image_deplot(image_path: str, chart_type: str | None = None) -> str:
    """Extract an underlying data table from a chart image."""
    requested_type = (chart_type or "").casefold().strip()
    digest = _image_digest(image_path)

    # Pix2Struct is CPU-heavy and is not useful in parallel on a two-core server.
    # Holding one lock also lets repeated uploads reuse the first completed result.
    with _inference_lock:
        detected_type = (
            detect_chart_type(image_path)
            if requested_type in {"", "auto"}
            else None
        )
        effective_type = detected_type or requested_type
        result_key = (digest, effective_type)
        cached_result = _cache_get(_result_cache, result_key)
        if cached_result is not None:
            return cached_result

        _ensure_model_loaded()
        assert _processor is not None and _model is not None

        with Image.open(image_path) as source:
            image = source.convert("RGB")

        full_text = _cache_get(_raw_table_cache, digest)
        if full_text is None:
            full_text = _generate_table(image)
            _cache_set(_raw_table_cache, digest, full_text)

        if effective_type != "pie":
            normalized = normalize_deplot_numeric_precision(full_text)
            result = add_chart_type_metadata(normalized, effective_type)
        else:
            plot_image = crop_pie_plot(image)
            if plot_image is None:
                raise InvalidExtractedChartData(
                    "A pie chart was detected, but its plot area could not be isolated."
                )
            plot_text = _generate_table(plot_image)
            result = normalize_pie_deplot_text(full_text, plot_text)

        _cache_set(_result_cache, result_key, result)
        return result


def _generate_table(image: Image.Image) -> str:
    assert _processor is not None and _model is not None
    inputs = _processor(
        images=image,
        text="Generate underlying data table of the figure below:",
        return_tensors="pt",
    )
    inference_context = torch.inference_mode() if torch is not None else nullcontext()
    with inference_context:
        predictions = _model.generate(
            **inputs,
            max_new_tokens=_max_new_tokens(),
            do_sample=False,
        )
    return _processor.decode(predictions[0], skip_special_tokens=True)
