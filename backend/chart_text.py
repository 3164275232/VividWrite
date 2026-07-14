"""Normalize and validate chart-to-table text before it reaches an LLM."""

from __future__ import annotations

import re
from difflib import get_close_matches


class InvalidExtractedChartData(ValueError):
    pass


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_LABELLED_PERCENT_RE = re.compile(
    r"^(?P<label>.+?)\s+(?P<value>-?\d+(?:\.\d+)?)\s*%\s*$"
)


def _lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.replace("<0x0A>", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.split("|")]


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _format_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:g}"


def _extract_title(text: str) -> str:
    for line in _lines(text):
        cells = _cells(line)
        if cells and cells[0].casefold() == "title":
            return " | ".join(cell for cell in cells[1:] if cell)
    return ""


def _extract_header_categories(text: str) -> list[str]:
    for line in _lines(text):
        cells = _cells(line)
        if len(cells) < 3 or cells[0].casefold() == "title":
            continue
        candidates = [cell for cell in cells[1:] if cell]
        if len(candidates) >= 2 and all(not _NUMBER_RE.search(cell) for cell in candidates):
            return candidates
    return []


def _extract_labelled_percentages(text: str) -> list[tuple[str, float]]:
    values: list[tuple[str, float]] = []
    seen: set[str] = set()
    for line in _lines(text):
        cells = _cells(line)
        if not cells or cells[0].casefold() == "title":
            continue

        match = _LABELLED_PERCENT_RE.match(cells[0])
        if match:
            label = match.group("label").strip()
            value = float(match.group("value"))
        elif len(cells) >= 2 and "%" in cells[1]:
            label = cells[0].strip()
            number = _NUMBER_RE.search(cells[1])
            if not label or number is None:
                continue
            value = float(number.group())
        else:
            continue

        key = _key(label)
        if key and key not in seen:
            values.append((label, value))
            seen.add(key)
    return values


def normalize_pie_deplot_text(full_text: str, plot_text: str) -> str:
    """Merge full-image metadata with values read from the isolated pie plot."""
    labelled_values = _extract_labelled_percentages(plot_text)
    if len(labelled_values) < 2:
        raise InvalidExtractedChartData(
            "The isolated pie plot did not produce enough category-percentage pairs."
        )

    value_by_key = {_key(label): value for label, value in labelled_values}
    categories = _extract_header_categories(full_text)
    if not categories:
        categories = [label for label, _ in labelled_values]

    ordered: list[tuple[str, float]] = []
    available_keys = list(value_by_key)
    for category in categories:
        category_key = _key(category)
        matched_key = category_key if category_key in value_by_key else None
        if matched_key is None:
            matches = get_close_matches(category_key, available_keys, n=1, cutoff=0.78)
            matched_key = matches[0] if matches else None
        if matched_key is None:
            raise InvalidExtractedChartData(
                f"No percentage could be matched to pie category '{category}'."
            )
        ordered.append((category, value_by_key[matched_key]))

    total = sum(value for _, value in ordered)
    if any(value <= 0 or value > 100 for _, value in ordered) or not 98 <= total <= 102:
        raise InvalidExtractedChartData(
            f"Pie percentages are inconsistent: extracted total is {total:g}%, expected about 100%."
        )

    title = _extract_title(full_text)
    result = [f"TITLE | {title}" if title else "TITLE |", "CHART TYPE | Pie chart", "Category | Percentage"]
    result.extend(f"{category} | {_format_number(value)}%" for category, value in ordered)
    return "\n".join(result)


def parse_validated_pie_table(text: str) -> dict[str, float]:
    """Parse the canonical pie table and enforce unique labels and a 100% total."""
    values: dict[str, float] = {}
    for line in _lines(text):
        cells = _cells(line)
        if len(cells) < 2 or "%" not in cells[1]:
            continue
        number = _NUMBER_RE.search(cells[1])
        label = cells[0].strip()
        if not label or number is None:
            continue
        if label.casefold() in {"category", "percentage"}:
            continue
        if label in values:
            raise InvalidExtractedChartData(f"Duplicate pie category '{label}'.")
        values[label] = float(number.group())

    if len(values) < 2:
        raise InvalidExtractedChartData("The pie chart table has too few data rows.")
    total = sum(values.values())
    if any(value <= 0 or value > 100 for value in values.values()) or not 98 <= total <= 102:
        raise InvalidExtractedChartData(
            f"Pie percentages are inconsistent: extracted total is {total:g}%, expected about 100%."
        )
    return values
