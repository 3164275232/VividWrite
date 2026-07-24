"""Normalize and validate chart-to-table text before it reaches an LLM."""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from difflib import get_close_matches


class InvalidExtractedChartData(ValueError):
    pass


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_LABELLED_PERCENT_RE = re.compile(
    r"^(?P<label>.+?)\s+(?P<value>-?\d+(?:\.\d+)?)\s*%\s*$"
)
_NUMERIC_CELL_RE = re.compile(r"^(?P<value>-?\d+(?:\.\d+)?)(?P<suffix>\s*%?)$")

CHART_TYPE_LABELS = {
    "bar": "Bar chart",
    "line": "Line graph",
    "area": "Area chart",
    "pie": "Pie chart",
}


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


def round_chart_value(value: float | int | str) -> float:
    """Round chart data to the nearest integer using conventional half-up rounding."""
    return float(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def quantize_chart_value(value: float | int | str, precision: int = 0) -> float:
    """Round a chart value to the selected decimal precision using half-up rounding."""
    safe_precision = max(0, min(6, int(precision)))
    quantum = Decimal("1").scaleb(-safe_precision)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def infer_deplot_value_precision(text: str, chart_type: str | None = None) -> int:
    """Choose readable precision without erasing trends in small-scale charts."""
    if (chart_type or "").casefold() == "pie":
        return 0

    rows = [_cells(line) for line in _lines(text)]
    header_index = next(
        (
            index
            for index, cells in enumerate(rows)
            if len(cells) >= 2
            and cells[0].casefold() not in {"title", "chart type"}
            and any(
                len(candidate) >= 2
                and any(_NUMERIC_CELL_RE.match(cell) for cell in candidate[1:])
                for candidate in rows[index + 1 :]
            )
        ),
        None,
    )
    if header_index is None:
        return 0

    numeric_tokens: list[str] = []
    for cells in rows[header_index + 1 :]:
        for cell in cells[1:]:
            match = _NUMERIC_CELL_RE.match(cell)
            if match:
                numeric_tokens.append(match.group("value"))
    if not numeric_tokens:
        return 0

    max_magnitude = max(abs(float(value)) for value in numeric_tokens)
    if max_magnitude >= 10:
        return 0

    observed_precision = max(
        (
            len(value.partition(".")[2].rstrip("0"))
            if "." in value
            else 0
        )
        for value in numeric_tokens
    )
    return max(1, min(3, observed_precision))


def round_deplot_table_values(
    text: str,
    *,
    precision: int | None = None,
    chart_type: str | None = None,
) -> str:
    """Normalize data cells while preserving row labels such as years."""
    rows = [_cells(line) for line in _lines(text)]
    header_index = next(
        (
            index
            for index, cells in enumerate(rows)
            if len(cells) >= 2
            and cells[0].casefold() not in {"title", "chart type"}
            and any(
                len(candidate) >= 2
                and any(_NUMERIC_CELL_RE.match(cell) for cell in candidate[1:])
                for candidate in rows[index + 1 :]
            )
        ),
        None,
    )
    if header_index is None:
        return "\n".join(" | ".join(cells) for cells in rows)

    selected_precision = (
        infer_deplot_value_precision(text, chart_type)
        if precision is None
        else max(0, min(6, int(precision)))
    )
    for cells in rows[header_index + 1 :]:
        for column_index in range(1, len(cells)):
            match = _NUMERIC_CELL_RE.match(cells[column_index])
            if match is None:
                continue
            rounded = quantize_chart_value(match.group("value"), selected_precision)
            cells[column_index] = f"{_format_number(rounded)}{match.group('suffix')}"
    return "\n".join(" | ".join(cells) for cells in rows)


def add_chart_type_metadata(text: str, chart_type: str | None) -> str:
    """Record the original visual type so an LLM does not call it a table."""
    label = CHART_TYPE_LABELS.get((chart_type or "").casefold())
    if not label:
        return "\n".join(_lines(text))

    lines = [line for line in _lines(text) if not line.casefold().startswith("chart type |")]
    marker = f"CHART TYPE | {label}"
    insert_at = 1 if lines and _cells(lines[0])[0].casefold() == "title" else 0
    lines.insert(insert_at, marker)
    return "\n".join(lines)


def normalize_deplot_numeric_precision(text: str) -> str:
    """Remove implausible DePlot decimals when a table strongly follows a coarser grid."""
    rows = [_cells(line) for line in _lines(text)]
    header_index = next(
        (
            index
            for index, cells in enumerate(rows)
            if len(cells) >= 3 and cells[0].casefold() not in {"title", "chart type"}
        ),
        None,
    )
    if header_index is None:
        return "\n".join(" | ".join(cells) for cells in rows)

    numeric_cells: list[tuple[int, int, float, str]] = []
    for row_index in range(header_index + 1, len(rows)):
        for column_index in range(1, len(rows[row_index])):
            match = _NUMERIC_CELL_RE.match(rows[row_index][column_index])
            if match:
                numeric_cells.append(
                    (
                        row_index,
                        column_index,
                        float(match.group("value")),
                        match.group("suffix"),
                    )
                )
    if len(numeric_cells) < 6:
        return "\n".join(" | ".join(cells) for cells in rows)

    chosen_step: float | None = None
    for step in (1.0, 0.5, 0.2, 0.1, 0.05):
        residuals = [abs(value - round(value / step) * step) for _, _, value, _ in numeric_cells]
        if max(residuals) <= step * 0.45 and sum(residuals) / len(residuals) <= step * 0.08:
            chosen_step = step
            break
    if chosen_step is None:
        return "\n".join(" | ".join(cells) for cells in rows)

    for row_index, column_index, value, suffix in numeric_cells:
        snapped = round(value / chosen_step) * chosen_step
        rows[row_index][column_index] = f"{_format_number(snapped)}{suffix}"
    return "\n".join(" | ".join(cells) for cells in rows)


def parse_series_framework(text: str) -> list[tuple[str, str]]:
    """Return the complete period/category by series grid from a DePlot table."""
    rows = [_cells(line) for line in _lines(text)]
    header_index = next(
        (
            index
            for index, cells in enumerate(rows)
            if len(cells) >= 3 and cells[0].casefold() not in {"title", "chart type"}
        ),
        None,
    )
    if header_index is None:
        return []

    series = [cell for cell in rows[header_index][1:] if cell]
    framework: list[tuple[str, str]] = []
    for cells in rows[header_index + 1 :]:
        if not cells or not cells[0]:
            continue
        framework.extend((cells[0], name) for name in series)
    return framework


def parse_numeric_chart_table(text: str) -> list[dict]:
    """Return validated long-form cells from a DePlot-style numeric table."""
    rows = [_cells(line) for line in _lines(text)]
    header_index = next(
        (
            index
            for index, cells in enumerate(rows)
            if len(cells) >= 2
            and cells[0].casefold() not in {"title", "chart type"}
            and any(
                len(candidate) >= 2
                and any(_NUMERIC_CELL_RE.match(cell) for cell in candidate[1:])
                for candidate in rows[index + 1 :]
            )
        ),
        None,
    )
    if header_index is None:
        return []

    header = rows[header_index]
    axis_label = header[0]
    series_names = header[1:]
    records: list[dict] = []
    for cells in rows[header_index + 1 :]:
        if not cells or not cells[0]:
            continue
        for column_index, series in enumerate(series_names, start=1):
            if not series or column_index >= len(cells):
                continue
            match = _NUMERIC_CELL_RE.match(cells[column_index])
            if match is None:
                continue
            records.append(
                {
                    "axis_label": axis_label,
                    "category": cells[0],
                    "series": series,
                    "value": float(match.group("value")),
                }
            )
    return records


def build_table_fact_checks(text: str) -> str:
    """Derive rankings, temporal trends, and crossings prose must not contradict."""
    rows = [_cells(line) for line in _lines(text)]
    header_index = next(
        (
            index
            for index, cells in enumerate(rows)
            if len(cells) >= 3 and cells[0].casefold() not in {"title", "chart type"}
        ),
        None,
    )
    if header_index is None:
        return ""

    series = rows[header_index][1:]
    periods: list[tuple[str, list[float]]] = []
    for cells in rows[header_index + 1 :]:
        if len(cells) < len(series) + 1:
            continue
        values: list[float] = []
        for cell in cells[1 : len(series) + 1]:
            match = _NUMERIC_CELL_RE.match(cell)
            if match is None:
                values = []
                break
            values.append(float(match.group("value")))
        if values:
            periods.append((cells[0], values))
    if not periods:
        return ""

    facts: list[str] = []
    for period, values in periods:
        ranking = sorted(zip(series, values), key=lambda item: item[1], reverse=True)
        ranking_text = ""
        for index, (name, value) in enumerate(ranking):
            if index:
                separator = " = " if value == ranking[index - 1][1] else " > "
                ranking_text += separator
            ranking_text += f"{name} ({_format_number(value)})"
        facts.append(f"{period} ranking: {ranking_text}.")

    axis_key = _key(rows[header_index][0])
    temporal_axis = axis_key in {"year", "date", "period", "time"} or all(
        re.fullmatch(r"\d{4}", period) for period, _ in periods
    )
    if temporal_axis and len(periods) >= 2:
        for series_index, name in enumerate(series):
            values = [row_values[series_index] for _, row_values in periods]
            changes = [
                current - previous
                for previous, current in zip(values, values[1:])
            ]
            path = " -> ".join(
                f"{period}: {_format_number(row_values[series_index])}"
                for period, row_values in periods
            )
            if all(change > 0 for change in changes):
                description = "increases at every recorded interval"
            elif all(change < 0 for change in changes):
                description = "decreases at every recorded interval"
            elif all(change >= 0 for change in changes):
                description = "never decreases, but includes at least one flat interval"
            elif all(change <= 0 for change in changes):
                description = "never increases, but includes at least one flat interval"
            else:
                if values[-1] > values[0]:
                    overall = "increases overall"
                elif values[-1] < values[0]:
                    overall = "decreases overall"
                else:
                    overall = "ends at its starting value"
                description = (
                    f"is non-monotonic and {overall}; do not call it steady, "
                    "consistent, continuous, or sustained"
                )
            facts.append(f"{name} trend: {description} ({path}).")

    for left_index in range(len(series)):
        for right_index in range(left_index + 1, len(series)):
            left_name, right_name = series[left_index], series[right_index]
            for (previous_period, previous), (current_period, current) in zip(periods, periods[1:]):
                previous_difference = previous[left_index] - previous[right_index]
                current_difference = current[left_index] - current[right_index]
                if previous_difference * current_difference < 0:
                    higher = left_name if current_difference > 0 else right_name
                    lower = right_name if current_difference > 0 else left_name
                    facts.append(
                        f"Between {previous_period} and {current_period}, {higher} overtakes {lower}."
                    )
                elif current_difference == 0 and previous_difference != 0:
                    facts.append(f"In {current_period}, {left_name} and {right_name} are equal.")
    return "\n".join(facts)


_EQUALITY_RE = re.compile(
    r"\b(?:equal(?:s|ed|led|ing)?|same as|identical to|drew level|level(?:led)? with|matched)\b",
    flags=re.IGNORECASE,
)
_STEADY_UP_RE = re.compile(
    r"\b(?:steady|consistent|continuous|sustained)\s+(?:growth|increase|rise|upward trend)\b"
    r"|\b(?:rose|grew|increased|climbed)\s+(?:steadily|consistently|continuously)\b",
    flags=re.IGNORECASE,
)
_STEADY_DOWN_RE = re.compile(
    r"\b(?:steady|consistent|continuous|sustained)\s+(?:decline|decrease|fall|drop|downward trend)\b"
    r"|\b(?:fell|declined|decreased|dropped)\s+(?:steadily|consistently|continuously)\b",
    flags=re.IGNORECASE,
)
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_DURATION_RE = re.compile(
    r"\b(?P<duration>\d+|" + "|".join(_NUMBER_WORDS) + r")-year period\b"
    r".{0,80}?\bfrom\s+(?P<start>\d{4})\s+to\s+(?P<end>\d{4})\b",
    flags=re.IGNORECASE,
)


def _parse_numeric_series_table(text: str) -> tuple[list[str], list[tuple[str, list[float]]]]:
    rows = [_cells(line) for line in _lines(text)]
    header_index = next(
        (
            index
            for index, cells in enumerate(rows)
            if len(cells) >= 3 and cells[0].casefold() not in {"title", "chart type"}
        ),
        None,
    )
    if header_index is None:
        return [], []

    series = rows[header_index][1:]
    periods: list[tuple[str, list[float]]] = []
    for cells in rows[header_index + 1 :]:
        if len(cells) < len(series) + 1:
            continue
        values: list[float] = []
        for cell in cells[1 : len(series) + 1]:
            match = _NUMERIC_CELL_RE.match(cell)
            if match is None:
                values = []
                break
            values.append(float(match.group("value")))
        if values:
            periods.append((cells[0], values))
    return series, periods


def _contains_series(text: str, series: str) -> bool:
    text_key = f" {_key(text)} "
    series_key = _key(series)
    aliases = {series_key}
    if series_key and " " not in series_key:
        aliases.add(f"{series_key}s")
        if series_key.endswith("s"):
            aliases.add(series_key[:-1])
    return any(f" {alias} " in text_key for alias in aliases if alias)


def find_table_fact_contradictions(table_text: str, prose: str) -> list[str]:
    """Find direct equality and whole-period monotonic claims contradicted by the table."""
    series, periods = _parse_numeric_series_table(table_text)
    if len(series) < 2 or len(periods) < 2:
        return []

    contradictions: list[str] = []
    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+|[\r\n]+", prose)
        if part.strip()
    ]
    value_by_period = {
        period: dict(zip(series, values))
        for period, values in periods
    }

    for sentence in sentences:
        for duration_match in _DURATION_RE.finditer(sentence):
            duration_text = duration_match.group("duration").casefold()
            claimed_duration = int(duration_text) if duration_text.isdigit() else _NUMBER_WORDS[duration_text]
            start = int(duration_match.group("start"))
            end = int(duration_match.group("end"))
            actual_duration = abs(end - start)
            if claimed_duration != actual_duration:
                contradictions.append(
                    f"The period from {start} to {end} is {actual_duration} years, not "
                    f"{claimed_duration} years."
                )

        equality = _EQUALITY_RE.search(sentence)
        if equality:
            mentioned_series = [name for name in series if _contains_series(sentence, name)]
            period_mentions = [
                (match.start(), period)
                for period, _ in periods
                for match in re.finditer(rf"(?<!\d){re.escape(period)}(?!\d)", sentence)
            ]
            if len(mentioned_series) >= 2 and period_mentions:
                preceding = [item for item in period_mentions if item[0] < equality.start()]
                _, period = max(preceding or period_mentions, key=lambda item: item[0])
                values = [(name, value_by_period[period][name]) for name in mentioned_series]
                if max(value for _, value in values) - min(value for _, value in values) > 1e-9:
                    details = ", ".join(
                        f"{name} is {_format_number(value)}" for name, value in values
                    )
                    contradictions.append(
                        f"The equality claim for {period} is false: {details}."
                    )

        for clause in re.split(r"[,;]|\b(?:while|whereas|although|but)\b", sentence, flags=re.IGNORECASE):
            if any(re.search(rf"(?<!\d){re.escape(period)}(?!\d)", clause) for period, _ in periods):
                continue
            direction = 1 if _STEADY_UP_RE.search(clause) else -1 if _STEADY_DOWN_RE.search(clause) else 0
            if not direction:
                continue
            for index, name in enumerate(series):
                if not _contains_series(clause, name):
                    continue
                values = [row_values[index] for _, row_values in periods]
                violates = any(
                    (current < previous if direction > 0 else current > previous)
                    for previous, current in zip(values, values[1:])
                )
                if violates:
                    trend = "increase" if direction > 0 else "decline"
                    contradictions.append(
                        f"The whole-period claim of a consistent {trend} for {name} is false."
                    )

    return list(dict.fromkeys(contradictions))


_STEADY_UP_ADJECTIVE_RE = re.compile(
    r"\b(?:steady|consistent|continuous|sustained)\s+"
    r"(?=(?:growth|increase|rise|upward trend)\b)",
    flags=re.IGNORECASE,
)
_STEADY_DOWN_ADJECTIVE_RE = re.compile(
    r"\b(?:steady|consistent|continuous|sustained)\s+"
    r"(?=(?:decline|decrease|fall|drop|downward trend)\b)",
    flags=re.IGNORECASE,
)
_STEADY_UP_ADVERB_RE = re.compile(
    r"\b(?P<verb>rose|grew|increased|climbed)\s+"
    r"(?:steadily|consistently|continuously)\b",
    flags=re.IGNORECASE,
)
_STEADY_DOWN_ADVERB_RE = re.compile(
    r"\b(?P<verb>fell|declined|decreased|dropped)\s+"
    r"(?:steadily|consistently|continuously)\b",
    flags=re.IGNORECASE,
)


def soften_false_monotonic_claims(table_text: str, prose: str) -> str:
    """Remove only false monotonic modifiers when the endpoint trend is still true."""
    series, periods = _parse_numeric_series_table(table_text)
    if len(series) < 1 or len(periods) < 2:
        return prose

    non_monotonic: dict[str, int] = {}
    for index, name in enumerate(series):
        values = [row_values[index] for _, row_values in periods]
        rises = any(current > previous for previous, current in zip(values, values[1:]))
        falls = any(current < previous for previous, current in zip(values, values[1:]))
        if rises and falls:
            non_monotonic[name] = 1 if values[-1] > values[0] else -1 if values[-1] < values[0] else 0

    if not non_monotonic:
        return prose

    parts = re.split(
        r"([,;]|\b(?:while|whereas|although|but)\b)",
        prose,
        flags=re.IGNORECASE,
    )
    for part_index in range(0, len(parts), 2):
        clause = parts[part_index]
        for name, endpoint_direction in non_monotonic.items():
            if not _contains_series(clause, name):
                continue
            if endpoint_direction > 0 and _STEADY_UP_RE.search(clause):
                clause = _STEADY_UP_ADJECTIVE_RE.sub("overall ", clause)
                clause = _STEADY_UP_ADVERB_RE.sub(
                    lambda match: f"{match.group('verb')} overall",
                    clause,
                )
            elif endpoint_direction < 0 and _STEADY_DOWN_RE.search(clause):
                clause = _STEADY_DOWN_ADJECTIVE_RE.sub("overall ", clause)
                clause = _STEADY_DOWN_ADVERB_RE.sub(
                    lambda match: f"{match.group('verb')} overall",
                    clause,
                )
            clause = re.sub(r"\ba\s+overall\b", "an overall", clause, flags=re.IGNORECASE)
        parts[part_index] = clause
    return "".join(parts)


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
