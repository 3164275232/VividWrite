"""Deterministic content-error taxonomy for statistical IELTS Task 1 feedback.

The taxonomy intentionally reports only claims that can be checked against the
official chart framework. It does not grade grammar, style, or overall IELTS band.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable


TAXONOMY_VERSION = "1.1"
TAXONOMY_SCOPE = "statistical-chart-content-fidelity"

ERROR_TYPE_DEFINITIONS = (
    {
        "code": "value_inaccuracy",
        "label": "Value inaccuracy",
        "description": "An explicit student value differs from the aligned official value.",
        "verification_rule": "Compare aligned numeric values using the chart's declared tolerance.",
    },
    {
        "code": "entity_misalignment",
        "label": "Entity or series misalignment",
        "description": "A value is assigned to the wrong category, series, or period.",
        "verification_rule": "Verify a reciprocal value swap or an entity absent from the official framework.",
    },
    {
        "code": "trend_direction_error",
        "label": "Trend direction error",
        "description": "An explicit increase, decrease, or stable claim contradicts the official direction.",
        "verification_rule": "Compare the stated direction with the first-to-last official values for the same entity.",
    },
    {
        "code": "comparison_ranking_error",
        "label": "Comparison or ranking error",
        "description": "An explicit highest, lowest, higher, or lower claim contradicts the official ordering.",
        "verification_rule": "Recompute the relevant ranking from official values in the same comparison context.",
    },
    {
        "code": "key_feature_omission",
        "label": "Key feature omission",
        "description": "No traceable student data is available for an entire chart entity or required endpoint.",
        "verification_rule": "Check aligned records for complete entity absence or a missing temporal endpoint.",
    },
)

ERROR_CODES = tuple(item["code"] for item in ERROR_TYPE_DEFINITIONS)
_DEFINITION_BY_CODE = {item["code"]: item for item in ERROR_TYPE_DEFINITIONS}

_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?")
_TEMPORAL_RE = re.compile(
    r"(?:\b(?:19|20)\d{2}(?:\s*/\s*\d{2,4})?\b|\bq[1-4]\b|"
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\b)",
    flags=re.IGNORECASE,
)
_DIRECTION_PATTERNS = {
    "increase": re.compile(
        r"\b(?:increase[ds]?|increasing|rise[sn]?|rose|rising|grow(?:s|th|ing)?|grew|"
        r"climb(?:ed|s|ing)?|surge[ds]?|upward)\b",
        flags=re.IGNORECASE,
    ),
    "decrease": re.compile(
        r"\b(?:decrease[ds]?|decreasing|decline[ds]?|declining|fall(?:s|ing)?|fell|"
        r"drop(?:ped|s|ping)?|plummet(?:ed|s|ing)?|downward)\b",
        flags=re.IGNORECASE,
    ),
    "stable": re.compile(
        r"\b(?:stable|steady|unchanged|constant|flat|level(?:led)?\s+off)\b",
        flags=re.IGNORECASE,
    ),
}
_RANK_PATTERNS = {
    "highest": re.compile(r"\b(?:highest|largest|greatest)\b", flags=re.IGNORECASE),
    "lowest": re.compile(r"\b(?:lowest|smallest|least)\b", flags=re.IGNORECASE),
}
_HIGHER_THAN_RE = re.compile(
    r"\b(?:higher|larger|greater|more)\s+than\b", flags=re.IGNORECASE
)
_LOWER_THAN_RE = re.compile(
    r"\b(?:lower|smaller|less|fewer)\s+than\b", flags=re.IGNORECASE
)
_ENTITY_PRONOUN_RE = re.compile(
    r"^(?:however|meanwhile|by contrast|in contrast)?\s*,?\s*"
    r"(?:it|its|this\s+(?:city|category|series|figure|rate))\b",
    flags=re.IGNORECASE,
)
_RELATIONAL_ORDER_RE = re.compile(
    r"\b(?:rank(?:ing|ings)?|rank\s+order|order(?:ing)?|position(?:s)?|"
    r"standing(?:s)?|placement(?:s)?|hierarch(?:y|ies)|distribution)\b",
    flags=re.IGNORECASE,
)
_CLAUSE_DIVIDER_RE = re.compile(
    r"[;:.!?]|\b(?:although|though|while|whereas|but)\b",
    flags=re.IGNORECASE,
)


def taxonomy_catalog() -> dict:
    """Return the stable taxonomy contract without chart-specific issue counts."""
    return {
        "version": TAXONOMY_VERSION,
        "scope": TAXONOMY_SCOPE,
        "definitions": [dict(item) for item in ERROR_TYPE_DEFINITIONS],
    }


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _normalise(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _display_number(value: float | None) -> str:
    if value is None:
        return "not stated"
    return f"{value:g}"


def _record_label(record: dict) -> str:
    if record.get("feedback_label"):
        return str(record["feedback_label"])
    parts = []
    for field in ("category", "series", "period", "region"):
        value = record.get(field)
        if value not in (None, "") and str(value) not in parts:
            parts.append(str(value))
    return " - ".join(parts) or "Unrecognised chart item"


def _record_key(record: dict) -> dict:
    return {
        field: record.get(field)
        for field in ("category", "series", "period", "region")
        if record.get(field) not in (None, "")
    }


def _sentence_parts(student_answer: str) -> list[str]:
    text = student_answer or ""
    parts = []
    start = 0
    for index, character in enumerate(text):
        previous = text[index - 1] if index else ""
        following = text[index + 1] if index + 1 < len(text) else ""
        decimal_point = character == "." and previous.isdigit() and following.isdigit()
        sentence_end = character in "!?;" or (character == "." and not decimal_point)
        line_end = character in "\r\n"
        if not sentence_end and not line_end:
            continue
        end = index + 1 if sentence_end else index
        sentence = text[start:end].strip()
        if sentence:
            parts.append(sentence)
        start = index + 1
    remainder = text[start:].strip()
    if remainder:
        parts.append(remainder)
    return parts


def _contains_label(sentence: str, label: Any) -> bool:
    key = _normalise(label)
    return bool(key) and key in _normalise(sentence)


def _sentence_numbers(sentence: str) -> list[float]:
    values = []
    for match in _NUMBER_RE.finditer(sentence):
        try:
            values.append(float(match.group().replace(",", "")))
        except ValueError:
            continue
    return values


def _source_sentences(student_answer: str, records: Iterable[dict]) -> list[str]:
    labels = []
    values = []
    for record in records:
        labels.extend(
            record.get(field)
            for field in ("category", "series", "period", "region")
            if record.get(field) not in (None, "")
        )
        value = _number(record.get("value"))
        if value is not None:
            values.append(value)

    ranked = []
    for sentence in _sentence_parts(student_answer):
        label_score = sum(1 for label in labels if _contains_label(sentence, label))
        sentence_values = _sentence_numbers(sentence)
        value_score = sum(
            1
            for expected in values
            if any(abs(actual - expected) <= 1e-9 for actual in sentence_values)
        )
        if label_score and (value_score or not values):
            ranked.append((label_score + value_score, sentence))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return list(dict.fromkeys(sentence for _, sentence in ranked[:2]))


def _tolerance(chart_data: dict) -> float:
    comparison = chart_data.get("comparison") if isinstance(chart_data.get("comparison"), dict) else {}
    return max(0.0, _number(comparison.get("accepted_value_tolerance")) or 0.0)


def _nearly_equal(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance + 1e-9


def _direction(start: float, end: float, tolerance: float) -> str:
    difference = end - start
    if difference > tolerance:
        return "increase"
    if difference < -tolerance:
        return "decrease"
    return "stable"


def _direction_adjective(direction: str) -> str:
    return {
        "increase": "increasing",
        "decrease": "decreasing",
        "stable": "stable",
    }.get(direction, direction)


def _is_temporal_label(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and _TEMPORAL_RE.search(text))


def _all_temporal(values: Iterable[Any]) -> bool:
    unique = list(dict.fromkeys(str(value) for value in values if value not in (None, "")))
    return len(unique) >= 2 and all(_is_temporal_label(value) for value in unique)


def _student_value(record: dict) -> float | None:
    if record.get("estimated"):
        return None
    return _number(record.get("value"))


def _official_value(record: dict) -> float | None:
    return _number(record.get("official_value"))


def _claim_payload(record: dict) -> dict:
    conflicting = record.get("conflicting_values")
    if isinstance(conflicting, list) and len(conflicting) > 1:
        values = [value for value in (_number(item) for item in conflicting) if value is not None]
        return {"values": values}
    return {"value": _student_value(record)}


def _make_issue(
    error_type: str,
    *,
    item: str,
    message: str,
    records: list[dict],
    record_indices: list[int],
    student_claim: dict,
    official_fact: dict,
    verification_method: str,
    source_sentences: list[str] | None = None,
    confidence: float = 1.0,
    tolerance: float | None = None,
) -> dict:
    issue = {
        "error_type": error_type,
        "label": _DEFINITION_BY_CODE[error_type]["label"],
        "item": item,
        "message": message,
        "student_claim": student_claim,
        "official_fact": official_fact,
        "evidence": {
            "record_keys": [_record_key(record) for record in records],
            "source_sentences": source_sentences or [],
        },
        "verification": {
            "status": "verified",
            "method": verification_method,
        },
        "confidence": round(min(1.0, max(0.0, confidence)), 3),
        "_record_indices": record_indices,
    }
    if tolerance is not None:
        issue["verification"]["tolerance"] = tolerance
    return issue


def _find_entity_misalignments(
    records: list[dict], student_answer: str, tolerance: float
) -> tuple[list[dict], set[int]]:
    issues = []
    assigned_indices: set[int] = set()
    wrong = [
        (index, record)
        for index, record in enumerate(records)
        if record.get("feedback_status") in {"incorrect", "conflicting"}
        and _student_value(record) is not None
        and _official_value(record) is not None
    ]
    for left_position, (left_index, left) in enumerate(wrong):
        if left_index in assigned_indices:
            continue
        for right_index, right in wrong[left_position + 1 :]:
            if right_index in assigned_indices:
                continue
            left_student = _student_value(left)
            right_student = _student_value(right)
            left_official = _official_value(left)
            right_official = _official_value(right)
            if None in {left_student, right_student, left_official, right_official}:
                continue
            if _nearly_equal(left_official, right_official, tolerance):
                continue
            if not (
                _nearly_equal(left_student, right_official, tolerance)
                and _nearly_equal(right_student, left_official, tolerance)
            ):
                continue
            left_label = _record_label(left)
            right_label = _record_label(right)
            issues.append(
                _make_issue(
                    "entity_misalignment",
                    item=f"{left_label} / {right_label}",
                    message=f"The values for {left_label} and {right_label} appear to be exchanged.",
                    records=[left, right],
                    record_indices=[left_index, right_index],
                    student_claim={
                        left_label: left_student,
                        right_label: right_student,
                    },
                    official_fact={
                        left_label: left_official,
                        right_label: right_official,
                    },
                    verification_method="reciprocal_value_swap",
                    source_sentences=_source_sentences(student_answer, [left, right]),
                    tolerance=tolerance,
                )
            )
            assigned_indices.update({left_index, right_index})
            break

    for index, record in enumerate(records):
        if record.get("feedback_status") != "unexpected":
            continue
        issues.append(
            _make_issue(
                "entity_misalignment",
                item=_record_label(record),
                message=f"{_record_label(record)} is not part of the official chart framework.",
                records=[record],
                record_indices=[index],
                student_claim={"entity": _record_label(record), "value": _student_value(record)},
                official_fact={"entity_present": False},
                verification_method="official_framework_membership",
                source_sentences=_source_sentences(student_answer, [record]),
            )
        )
        assigned_indices.add(index)
    return issues, assigned_indices


def _find_value_inaccuracies(
    records: list[dict], student_answer: str, tolerance: float, excluded_indices: set[int]
) -> list[dict]:
    issues = []
    for index, record in enumerate(records):
        if index in excluded_indices or record.get("feedback_status") not in {"incorrect", "conflicting"}:
            continue
        student_value = _student_value(record)
        official_value = _official_value(record)
        if official_value is None:
            continue
        label = _record_label(record)
        claim = _claim_payload(record)
        if "values" in claim:
            message = f"The report gives conflicting values for {label}; the official value is {_display_number(official_value)}."
        else:
            message = (
                f"The report gives {_display_number(student_value)} for {label}; "
                f"the official value is {_display_number(official_value)}."
            )
        issues.append(
            _make_issue(
                "value_inaccuracy",
                item=label,
                message=message,
                records=[record],
                record_indices=[index],
                student_claim=claim,
                official_fact={"value": official_value},
                verification_method="aligned_numeric_comparison",
                source_sentences=_source_sentences(student_answer, [record]),
                confidence=_number(record.get("confidence")) or 1.0,
                tolerance=tolerance,
            )
        )
    return issues


def _trend_entities(chart_data: dict, records: list[dict]) -> list[tuple[str, list[tuple[int, dict]]]]:
    categories = [record.get("category") for record in records]
    series = [record.get("series") for record in records]
    chart_type = chart_data.get("chart_type")
    category_temporal = _all_temporal(categories)
    series_temporal = _all_temporal(series)
    if chart_type == "line" or category_temporal:
        entity_field = "series"
    elif series_temporal:
        entity_field = "category"
    else:
        return []

    grouped: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for index, record in enumerate(records):
        entity = record.get(entity_field)
        if entity not in (None, ""):
            grouped[str(entity)].append((index, record))
    return list(grouped.items())


def _claimed_direction(sentence: str) -> str | None:
    matches = [name for name, pattern in _DIRECTION_PATTERNS.items() if pattern.search(sentence)]
    if len(matches) != 1:
        return None
    match = _DIRECTION_PATTERNS[matches[0]].search(sentence)
    if match:
        if matches[0] == "stable":
            left = max(
                (divider.end() for divider in _CLAUSE_DIVIDER_RE.finditer(sentence)
                 if divider.end() <= match.start()),
                default=0,
            )
            right = min(
                (divider.start() for divider in _CLAUSE_DIVIDER_RE.finditer(sentence)
                 if divider.start() >= match.end()),
                default=len(sentence),
            )
            if _RELATIONAL_ORDER_RE.search(sentence[left:right]):
                return None
        preceding = sentence[max(0, match.start() - 12) : match.start()]
        if re.search(r"\b(?:not|never|no)\b", preceding, flags=re.IGNORECASE):
            return None
    return matches[0]


def _trend_sentence_candidates(
    sentences: list[str], entity: str, all_entities: list[str]
) -> list[tuple[str, list[str]]]:
    candidates = []
    for index, sentence in enumerate(sentences):
        if _contains_label(sentence, entity):
            candidates.append((sentence, [sentence]))
            continue
        if index == 0 or not _ENTITY_PRONOUN_RE.search(sentence):
            continue
        previous = sentences[index - 1]
        mentioned = [
            candidate for candidate in all_entities if _contains_label(previous, candidate)
        ]
        if mentioned == [entity]:
            candidates.append((sentence, [previous, sentence]))
    return candidates


def _find_trend_errors(chart_data: dict, records: list[dict], student_answer: str, tolerance: float) -> list[dict]:
    issues = []
    sentences = _sentence_parts(student_answer)
    trend_entities = _trend_entities(chart_data, records)
    all_entities = [entity for entity, _ in trend_entities]
    for entity, indexed_records in trend_entities:
        official_points = [
            (index, record, _official_value(record))
            for index, record in indexed_records
            if _official_value(record) is not None
        ]
        if len(official_points) < 2:
            continue
        start_index, start_record, start_value = official_points[0]
        end_index, end_record, end_value = official_points[-1]
        official_direction = _direction(start_value, end_value, tolerance)
        for sentence, evidence_sentences in _trend_sentence_candidates(
            sentences, entity, all_entities
        ):
            claimed_direction = _claimed_direction(sentence)
            if claimed_direction is None or claimed_direction == official_direction:
                continue
            issues.append(
                _make_issue(
                    "trend_direction_error",
                    item=entity,
                    message=(
                        f"The report describes {entity} as {_direction_adjective(claimed_direction)}, "
                        f"but the official first-to-last direction is {_direction_adjective(official_direction)}."
                    ),
                    records=[start_record, end_record],
                    record_indices=[start_index, end_index],
                    student_claim={"direction": claimed_direction},
                    official_fact={
                        "direction": official_direction,
                        "start_value": start_value,
                        "end_value": end_value,
                    },
                    verification_method="official_endpoint_direction",
                    source_sentences=evidence_sentences,
                    tolerance=tolerance,
                )
            )
            break
    return issues


def _ranking_contexts(chart_data: dict, records: list[dict]) -> list[tuple[str, list[tuple[int, dict]]]]:
    if chart_data.get("chart_type") == "pie":
        categories = [record.get("category") for record in records]
        series = [record.get("series") for record in records]
        if _all_temporal(series) and not _all_temporal(categories):
            group_field = "series"
        elif _all_temporal(categories) and not _all_temporal(series):
            group_field = "category"
        else:
            return [("Whole chart", list(enumerate(records)))]

        grouped: dict[str, list[tuple[int, dict]]] = defaultdict(list)
        for index, record in enumerate(records):
            context = record.get(group_field)
            if context not in (None, ""):
                grouped[str(context)].append((index, record))
        return [item for item in grouped.items() if len(item[1]) >= 2]

    categories = [record.get("category") for record in records]
    series = [record.get("series") for record in records]
    group_field = "category"
    if _all_temporal(series) and not _all_temporal(categories):
        group_field = "series"

    grouped: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for index, record in enumerate(records):
        context = record.get(group_field)
        if context not in (None, ""):
            grouped[str(context)].append((index, record))
    return [item for item in grouped.items() if len(item[1]) >= 2]


def _entity_for_context(record: dict, context: str) -> str:
    for field in ("category", "series", "region", "period"):
        value = record.get(field)
        if value not in (None, "") and str(value) != context:
            return str(value)
    return _record_label(record)


def _rank_claim_for_entity(sentence: str, entity: str) -> str | None:
    if not _contains_label(sentence, entity):
        return None
    if re.search(
        r"\b(?:highest|largest|greatest|lowest|smallest)\s+"
        r"(?:increase|growth|change|rise|decline|decrease)\b",
        sentence,
        flags=re.IGNORECASE,
    ):
        return None
    entity_pattern = re.compile(rf"\b{re.escape(str(entity))}\b", flags=re.IGNORECASE)
    entity_matches = list(entity_pattern.finditer(sentence))
    clause_boundary = re.compile(r"[,;:]|\b(?:while|whereas|but|although)\b", flags=re.IGNORECASE)
    candidates: list[tuple[float, str]] = []
    for rank, pattern in _RANK_PATTERNS.items():
        for rank_match in pattern.finditer(sentence):
            qualifier = sentence[max(0, rank_match.start() - 32) : rank_match.start()]
            if re.search(
                r"\b(?:second|third|fourth|fifth|next)\s*[- ]?\s*$",
                qualifier,
                flags=re.IGNORECASE,
            ):
                continue
            # A grouped superlative (for example, "the two smallest shares")
            # does not claim that every member of the group is the unique minimum.
            if re.search(
                r"\b(?:one\s+of\s+the|among\s+the|two|three|four|five|six|several)\s+$",
                qualifier,
                flags=re.IGNORECASE,
            ):
                continue
            if rank_match.group(0).casefold() == "least" and re.search(
                r"\bat\s+$", qualifier, flags=re.IGNORECASE
            ):
                continue
            for entity_match in entity_matches:
                between_start = min(entity_match.end(), rank_match.end())
                between_end = max(entity_match.start(), rank_match.start())
                between = sentence[between_start:between_end]
                if len(between) <= 60 and not clause_boundary.search(between):
                    entity_middle = (entity_match.start() + entity_match.end()) / 2
                    rank_middle = (rank_match.start() + rank_match.end()) / 2
                    candidates.append((abs(entity_middle - rank_middle), rank))
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1]


def _find_ranking_errors(chart_data: dict, records: list[dict], student_answer: str, tolerance: float) -> list[dict]:
    issues = []
    sentences = _sentence_parts(student_answer)
    for context, indexed_records in _ranking_contexts(chart_data, records):
        official = [
            (index, record, _official_value(record))
            for index, record in indexed_records
            if _official_value(record) is not None
        ]
        if len(official) < 2:
            continue
        maximum = max(value for _, _, value in official)
        minimum = min(value for _, _, value in official)
        official_high = {
            _entity_for_context(record, context)
            for _, record, value in official
            if _nearly_equal(value, maximum, tolerance)
        }
        official_low = {
            _entity_for_context(record, context)
            for _, record, value in official
            if _nearly_equal(value, minimum, tolerance)
        }
        for sentence in sentences:
            if context != "Whole chart" and not _contains_label(sentence, context):
                continue
            for index, record, value in official:
                entity = _entity_for_context(record, context)
                claim = _rank_claim_for_entity(sentence, entity)
                expected_entities = official_high if claim == "highest" else official_low
                if claim is None or entity in expected_entities:
                    continue
                expected = ", ".join(sorted(expected_entities))
                issues.append(
                    _make_issue(
                        "comparison_ranking_error",
                        item=f"{context}: {entity}",
                        message=(
                            f"The report calls {entity} the {claim} in {context}, but the official "
                            f"{claim} item is {expected}."
                        ),
                        records=[record],
                        record_indices=[index],
                        student_claim={"entity": entity, "rank": claim, "context": context},
                        official_fact={"entities": sorted(expected_entities), "rank": claim, "context": context},
                        verification_method="official_context_ranking",
                        source_sentences=[sentence],
                        tolerance=tolerance,
                    )
                )
                break
    return issues


def _find_relational_comparison_errors(
    chart_data: dict, records: list[dict], student_answer: str, tolerance: float
) -> list[dict]:
    issues = []
    sentences = _sentence_parts(student_answer)
    for context, indexed_records in _ranking_contexts(chart_data, records):
        official = [
            (index, record, _official_value(record))
            for index, record in indexed_records
            if _official_value(record) is not None
        ]
        for sentence in sentences:
            if context != "Whole chart" and not _contains_label(sentence, context):
                continue
            relation = "higher" if _HIGHER_THAN_RE.search(sentence) else "lower" if _LOWER_THAN_RE.search(sentence) else None
            if relation is None:
                continue
            for left_pos, (left_index, left_record, left_value) in enumerate(official):
                left_entity = _entity_for_context(left_record, context)
                if not _contains_label(sentence, left_entity):
                    continue
                for right_index, right_record, right_value in official[left_pos + 1 :]:
                    right_entity = _entity_for_context(right_record, context)
                    if not _contains_label(sentence, right_entity):
                        continue
                    left_match = re.search(re.escape(left_entity), sentence, flags=re.IGNORECASE)
                    right_match = re.search(re.escape(right_entity), sentence, flags=re.IGNORECASE)
                    if left_match is None or right_match is None:
                        continue
                    left_position = left_match.start()
                    right_position = right_match.start()
                    relation_position = (
                        _HIGHER_THAN_RE.search(sentence) or _LOWER_THAN_RE.search(sentence)
                    ).start()
                    if left_position < relation_position < right_position:
                        claimed_left, claimed_right = left_entity, right_entity
                        claimed_left_value, claimed_right_value = left_value, right_value
                    elif right_position < relation_position < left_position:
                        claimed_left, claimed_right = right_entity, left_entity
                        claimed_left_value, claimed_right_value = right_value, left_value
                    else:
                        continue
                    correct = (
                        claimed_left_value > claimed_right_value + tolerance
                        if relation == "higher"
                        else claimed_left_value < claimed_right_value - tolerance
                    )
                    if correct:
                        continue
                    issues.append(
                        _make_issue(
                            "comparison_ranking_error",
                            item=f"{context}: {claimed_left} / {claimed_right}",
                            message=(
                                f"The report says {claimed_left} is {relation} than {claimed_right} in {context}, "
                                "but the official values show the opposite ordering or a tie."
                            ),
                            records=[left_record, right_record],
                            record_indices=[left_index, right_index],
                            student_claim={"left": claimed_left, "relation": relation, "right": claimed_right},
                            official_fact={
                                left_entity: left_value,
                                right_entity: right_value,
                                "context": context,
                            },
                            verification_method="official_pairwise_comparison",
                            source_sentences=[sentence],
                            tolerance=tolerance,
                        )
                    )
                    break
                else:
                    continue
                break
    return issues


def _find_omissions(chart_data: dict, records: list[dict]) -> list[dict]:
    issues = []
    chart_type = chart_data.get("chart_type")
    categories = [record.get("category") for record in records]
    series = [record.get("series") for record in records]

    if chart_type == "pie":
        entity_field = "category"
    elif _all_temporal(series) and not _all_temporal(categories):
        entity_field = "category"
    elif len({str(value) for value in series if value not in (None, "")}) > 1:
        entity_field = "series"
    else:
        entity_field = "category"

    grouped: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for index, record in enumerate(records):
        entity = record.get(entity_field)
        if entity not in (None, ""):
            grouped[str(entity)].append((index, record))

    for entity, indexed_records in grouped.items():
        if any(_student_value(record) is not None for _, record in indexed_records):
            continue
        official_values = [
            value
            for _, record in indexed_records
            if (value := _official_value(record)) is not None
        ]
        if not official_values:
            continue
        indices = [index for index, _ in indexed_records]
        entity_records = [record for _, record in indexed_records]
        issues.append(
            _make_issue(
                "key_feature_omission",
                item=entity,
                message=f"No verifiable data point from the report was found for {entity}.",
                records=entity_records,
                record_indices=indices,
                student_claim={"traceable_values": 0},
                official_fact={"values": official_values},
                verification_method="complete_entity_coverage_check",
                confidence=0.95,
            )
        )

    if chart_type == "line":
        for entity, indexed_records in _trend_entities(chart_data, records):
            if len(indexed_records) < 2:
                continue
            endpoints = [indexed_records[0], indexed_records[-1]]
            missing_endpoints = [
                (index, record)
                for index, record in endpoints
                if _student_value(record) is None and _official_value(record) is not None
            ]
            entity_is_completely_missing = all(
                _student_value(record) is None for _, record in indexed_records
            )
            if not missing_endpoints or entity_is_completely_missing:
                continue
            for index, record in missing_endpoints:
                label = _record_label(record)
                issues.append(
                    _make_issue(
                        "key_feature_omission",
                        item=label,
                        message=f"The report does not provide a traceable endpoint for {label}.",
                        records=[record],
                        record_indices=[index],
                        student_claim={"value": None},
                        official_fact={"value": _official_value(record)},
                        verification_method="temporal_endpoint_coverage_check",
                        confidence=0.95,
                    )
                )
    return issues


def _deduplicate(issues: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for issue in issues:
        key = (
            issue["error_type"],
            issue["item"],
            tuple(issue["evidence"]["source_sentences"]),
            issue["verification"]["method"],
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    return unique


def _taxonomy_applicability(chart_data: dict, records: list[dict]) -> dict[str, dict]:
    official_records = [record for record in records if _official_value(record) is not None]
    trend_available = any(
        sum(1 for _, record in indexed_records if _official_value(record) is not None) >= 2
        for _, indexed_records in _trend_entities(chart_data, records)
    )
    ranking_available = any(
        sum(1 for _, record in indexed_records if _official_value(record) is not None) >= 2
        for _, indexed_records in _ranking_contexts(chart_data, records)
    )
    chart_type = str(chart_data.get("chart_type") or "chart")

    applicable = {
        "value_inaccuracy": bool(official_records),
        "entity_misalignment": bool(official_records),
        "trend_direction_error": trend_available,
        "comparison_ranking_error": ranking_available,
        "key_feature_omission": bool(official_records),
    }
    reasons = {
        "value_inaccuracy": "Official values are available for aligned numeric comparison.",
        "entity_misalignment": "The official category and series framework is available.",
        "trend_direction_error": (
            "At least two ordered official values are available for the same entity."
            if trend_available
            else (
                "A single-period pie chart has no temporal endpoints, so trend direction cannot be verified."
                if chart_type == "pie"
                else "No entity has two ordered official values for a direction check."
            )
        ),
        "comparison_ranking_error": (
            "At least two official values are available in the same comparison context."
            if ranking_available
            else "The chart has no comparison context containing at least two official values."
        ),
        "key_feature_omission": "The official chart framework is available for coverage checks.",
    }
    return {
        code: {"applicable": is_applicable, "reason": reasons[code]}
        for code, is_applicable in applicable.items()
    }


def build_error_taxonomy(chart_data: dict, student_answer: str) -> dict:
    """Build the five-class taxonomy and attach evidence to every issue."""
    records = chart_data.get("records") if isinstance(chart_data.get("records"), list) else []
    records = [record for record in records if isinstance(record, dict)]
    tolerance = _tolerance(chart_data)

    entity_issues, entity_indices = _find_entity_misalignments(records, student_answer, tolerance)
    issues = [
        *entity_issues,
        *_find_value_inaccuracies(records, student_answer, tolerance, entity_indices),
        *_find_trend_errors(chart_data, records, student_answer, tolerance),
        *_find_ranking_errors(chart_data, records, student_answer, tolerance),
        *_find_relational_comparison_errors(chart_data, records, student_answer, tolerance),
        *_find_omissions(chart_data, records),
    ]
    issues = _deduplicate(issues)
    applicability = _taxonomy_applicability(chart_data, records)

    counts = {code: 0 for code in ERROR_CODES}
    for index, issue in enumerate(issues, start=1):
        issue["id"] = f'{issue["error_type"]}:{index}'
        counts[issue["error_type"]] += 1
        for record_index in issue.pop("_record_indices", []):
            if 0 <= record_index < len(records):
                records[record_index].setdefault("taxonomy_issue_ids", []).append(issue["id"])

    definitions = []
    for definition in ERROR_TYPE_DEFINITIONS:
        item = dict(definition)
        item["issue_count"] = counts[item["code"]]
        item.update(applicability[item["code"]])
        definitions.append(item)

    return {
        "version": TAXONOMY_VERSION,
        "scope": TAXONOMY_SCOPE,
        "chart_type": chart_data.get("chart_type"),
        "definitions": definitions,
        "applicability": applicability,
        "issues": issues,
        "summary": {
            "total_issues": len(issues),
            "verified_issues": sum(
                1 for issue in issues if issue["verification"]["status"] == "verified"
            ),
            "affected_error_types": sum(1 for count in counts.values() if count),
            "applicable_checks": sum(
                1 for item in applicability.values() if item["applicable"]
            ),
            "not_applicable_checks": sum(
                1 for item in applicability.values() if not item["applicable"]
            ),
            "counts": counts,
        },
        "limitations": [
            "Only explicit, locally verifiable chart-content claims are classified.",
            "Pronoun-only references and implied comparisons may require human review.",
            "Grammar, vocabulary, style, and IELTS band scoring are outside this taxonomy.",
        ],
    }


def attach_error_taxonomy(chart_data: dict, student_answer: str) -> dict:
    chart_data["error_taxonomy"] = build_error_taxonomy(chart_data, student_answer)
    chart_data["schema_version"] = "1.1"
    return chart_data
