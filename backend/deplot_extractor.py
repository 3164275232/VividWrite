"""Lazy-loading wrapper for the Google DePlot model."""

from typing import Any, Optional

from PIL import Image

try:
    from transformers import Pix2StructForConditionalGeneration, Pix2StructProcessor
except ImportError:
    Pix2StructForConditionalGeneration = None
    Pix2StructProcessor = None


MODEL_NAME = "google/deplot"
_processor: Optional[Any] = None
_model: Optional[Any] = None


def _ensure_model_loaded() -> None:
    global _processor, _model
    if _processor is not None and _model is not None:
        return
    if Pix2StructProcessor is None or Pix2StructForConditionalGeneration is None:
        raise RuntimeError("DePlot requires the transformers and pillow packages")

    try:
        _processor = Pix2StructProcessor.from_pretrained(MODEL_NAME)
        _model = Pix2StructForConditionalGeneration.from_pretrained(MODEL_NAME)
    except Exception as exc:
        raise RuntimeError(f"Failed to load DePlot model: {exc}") from exc


def extract_table_from_image_deplot(image_path: str) -> str:
    """Extract an underlying data table from a chart image."""
    _ensure_model_loaded()
    assert _processor is not None and _model is not None

    with Image.open(image_path) as source:
        image = source.convert("RGB")
    inputs = _processor(
        images=image,
        text="Generate underlying data table of the figure below:",
        return_tensors="pt",
    )
    predictions = _model.generate(**inputs, max_new_tokens=512)
    return _processor.decode(predictions[0], skip_special_tokens=True)
