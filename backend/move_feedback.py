"""Seven-move feedback contract for IELTS Academic Writing Task 1.

The framework follows Matsuzono's move-based analysis of Task 1 model
responses. Moves are treated as rhetorical options to review, not as errors or
mandatory boxes that every report must tick.
"""

from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any


MOVE_FEEDBACK_VERSION = "1.0"
MOVE_FEEDBACK_SCOPE = "ielts-task-1-rhetorical-moves"

MOVE_DEFINITIONS = (
    {
        "code": "move_1_introducing_topic",
        "number": 1,
        "short_code": "IT",
        "label": "Introducing the topic",
        "purpose": "Identify what the visual presents, including its subject and scope.",
        "feedback_mode": "textual",
    },
    {
        "code": "move_2_stating_overview",
        "number": 2,
        "short_code": "SO",
        "label": "Stating the overview",
        "purpose": "Give a broad synthesis of the most notable patterns without listing details.",
        "feedback_mode": "textual_visual",
    },
    {
        "code": "move_3_highlighting_key_trends",
        "number": 3,
        "short_code": "HKT",
        "label": "Highlighting key trends",
        "purpose": "Prioritise the trends or features that carry the main message of the visual.",
        "feedback_mode": "textual_visual",
    },
    {
        "code": "move_4_elaborating_key_trends",
        "number": 4,
        "short_code": "EKT",
        "label": "Elaborating on the key trends",
        "purpose": "Support an identified trend with relevant and accurate detail.",
        "feedback_mode": "textual",
    },
    {
        "code": "move_5_integrating_trend_and_detail",
        "number": 5,
        "short_code": "KTE",
        "label": "Including key trends and their elaboration",
        "purpose": "Combine a meaningful trend and its supporting evidence coherently.",
        "feedback_mode": "textual_visual",
    },
    {
        "code": "move_6_comparing_contrasting",
        "number": 6,
        "short_code": "MCS",
        "label": "Making comparative or contrastive statements",
        "purpose": "Make relevant relationships across categories, groups, or time periods explicit.",
        "feedback_mode": "textual",
    },
    {
        "code": "move_7_closing_summary",
        "number": 7,
        "short_code": "SC",
        "label": "Stating the conclusion",
        "purpose": "If a closing statement is used, synthesise rather than repeat individual details.",
        "feedback_mode": "textual",
    },
)

MOVE_CODES = tuple(item["code"] for item in MOVE_DEFINITIONS)
VISUAL_MOVE_CODES = {
    "move_2_stating_overview",
    "move_3_highlighting_key_trends",
    "move_5_integrating_trend_and_detail",
}
VALID_STATUSES = {"effective", "developing", "not_detected", "not_applicable"}

_DEFAULT_HINTS = {
    "move_1_introducing_topic": "Clarify what the visual shows and the scope of the comparison.",
    "move_2_stating_overview": "Step back from individual values and state the broad pattern a reader should notice first.",
    "move_3_highlighting_key_trends": "Prioritise the most consequential trend or feature rather than a smaller local change.",
    "move_4_elaborating_key_trends": "Support the selected trend with a small amount of relevant, accurate evidence.",
    "move_5_integrating_trend_and_detail": "Connect each supporting figure to the trend it demonstrates instead of listing it separately.",
    "move_6_comparing_contrasting": "Make one meaningful relationship between categories, groups, or periods explicit.",
    "move_7_closing_summary": "A separate conclusion is optional; if you use one, synthesise the main message without repeating details.",
}

_VISUAL_NOUN_RE = re.compile(
    r"\b(?:chart|graph|graphic|image|table|diagram|map|figure|illustration|visual|data|percentage|proportion)\b",
    flags=re.IGNORECASE,
)
_TREND_RE = re.compile(
    r"\b(?:increase|increased|increasing|rose|rise|grew|growth|climbed|decrease|"
    r"decreased|decline|declined|fell|fall|dropped|stable|unchanged|fluctuat(?:e|ed|ion)|"
    r"highest|lowest|largest|smallest|dominan(?:t|ce)|leading|gain|improvement|expansion|"
    r"first\s+place|main|notable|overall)\b",
    flags=re.IGNORECASE,
)
_COMPARISON_RE = re.compile(
    r"\b(?:while|whereas|compared with|in contrast|by contrast|higher than|lower than|"
    r"more than|less than|respectively|overtook|exceeded|followed by|similar(?:ly)?)\b",
    flags=re.IGNORECASE,
)
_OVERVIEW_RE = re.compile(r"\b(?:overall|in general|generally|it is clear|clearly)\b", re.IGNORECASE)
_CLOSING_RE = re.compile(r"^(?:overall|in summary|to sum up|in conclusion|despite)\b", re.IGNORECASE)
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?")
_TEMPORAL_RE = re.compile(r"^(?:19|20)\d{2}(?:\s*/\s*\d{2,4})?$|^q[1-4]$", re.IGNORECASE)
_PRIORITY_RE = re.compile(
    r"\b(?:key|main|central|principal|defining|clearest|most\s+(?:notable|prominent|important)|"
    r"strongest|dominant)\b",
    re.IGNORECASE,
)
_DECLARED_FOCUS_RE = re.compile(
    r"\b(?:key|main|central|principal|defining|clearest|"
    r"most\s+(?:notable|prominent|important))\s+"
    r"(?:feature|pattern|trend|change|difference|gap|development)\b",
    re.IGNORECASE,
)
_SUPPORT_LINK_RE = re.compile(
    r"\b(?:supported\s+by|demonstrated\s+by|shown\s+by|as\s+shown\s+by|"
    r"as\s+demonstrated\s+by|as\s+evidenced\s+by|evidenced\s+by|because|,\s*as)\b",
    re.IGNORECASE,
)
_VAGUE_COMPARISON_RE = re.compile(
    r"\b(?:some(?:\s+\w+){0,2}\s+(?:figures?|values?|results?|lines?|portions?|shares?)|"
    r"some\s+were\s+(?:higher|lower|larger|smaller)|"
    r"differences?\s+(?:between|among)|compared\s+with\s+one\s+another|"
    r"(?:categories|items|modes|cities|services)\s+can\s+be\s+compared|"
    r"higher\s+than\s+others?|lower\s+than\s+others?|"
    r"several\s+values?\s+were\s+relatively\s+close)\b",
    re.IGNORECASE,
)
_WEAK_CLOSING_RE = re.compile(
    r"\b(?:described\s+above|presented\s+above|(?:already|also)\s+(?:listed|presented|described)|"
    r"as\s+(?:listed|presented|described)|"
    r"contains?\s+\w*\s*(?:figures?|percentages?|lines?|observations?)|"
    r"(?:chart|graph|figure|visual)\s+(?:contains?|covers?|uses?)|"
    r"this\s+is\s+(?:a|an)\s+(?:(?:bar|line|pie)\s+)?(?:chart|graph|figure)|"
    r"(?:shares?|figures?|values?)\s+(?:add|sum|total)(?:s)?\s+(?:up\s+)?to\s+100|"
    r"as\s+(?:is\s+)?expected|add(?:s)?\s+(?:up\s+)?to\s+100|"
    r"producing\s+the\s+values|all\s+of\s+the\s+(?:numbers|figures))\b",
    re.IGNORECASE,
)
_EXPLICIT_CLOSING_RE = re.compile(
    r"^(?:in\s+summary|to\s+sum\s+up|in\s+conclusion|to\s+conclude)\b",
    re.IGNORECASE,
)
_NO_REVISION_NEEDED_RE = re.compile(
    r"\b(?:no\s+(?:revision|change|improvement)s?\s+(?:(?:is|are)\s+)?needed|"
    r"there\s+is\s+no\s+need\s+to\s+(?:revise|change|improve)|"
    r"this\s+criterion\s+is\s+(?:fully\s+)?met)\b",
    re.IGNORECASE,
)
_VAGUE_INTRO_RE = re.compile(
    r"\b(?:collection|sets?|number|several|different|series|measured)\s+(?:of\s+)?"
    r"(?:changing\s+|measured\s+)?"
    r"(?:figures?|numbers?|items?|places?|lines?|shares?|percentages?|parts?|portions?|values?)\b|"
    r"\b(?:figures?|numbers?|items?|lines?|shares?|percentages?|values?)\s+"
    r"(?:for\s+consideration|that\s+changed\s+over\s+time)\b",
    re.IGNORECASE,
)
_OVERVIEW_SYNTHESIS_RE = re.compile(
    r"\b(?:highest|lowest|largest|smallest|dominan(?:t|ce)|majority|over\s+half|"
    r"increase|increased|rise|rose|grew|growth|upward|decrease|decreased|fell|"
    r"decline|declined|downward|stable|unchanged|remained|overtook|concentrat(?:e|ed|ion)|"
    r"upper\s+end|lower\s+end|leading|bottom|top)\b",
    re.IGNORECASE,
)


def move_catalog() -> dict:
    return {
        "version": MOVE_FEEDBACK_VERSION,
        "scope": MOVE_FEEDBACK_SCOPE,
        "definitions": [dict(item) for item in MOVE_DEFINITIONS],
    }


def _normalise(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    start = 0
    for match in re.finditer(r"(?<=[!?;])\s+|\.(?!\d)(?:\s+|$)|[\r\n]+", text):
        end = match.start() + (1 if text[match.start() : match.start() + 1] == "." else 0)
        raw = text[start:end]
        left = len(raw) - len(raw.lstrip())
        right = len(raw.rstrip())
        if right > left:
            spans.append((start + left, start + right, raw[left:right]))
        start = match.end()
    raw = text[start:]
    left = len(raw) - len(raw.lstrip())
    right = len(raw.rstrip())
    if right > left:
        spans.append((start + left, start + right, raw[left:right]))
    return spans


def _find_excerpt_range(text: str, excerpt: str) -> tuple[dict | None, str | None]:
    candidate = str(excerpt or "")[:1000]
    if not candidate.strip():
        return None, None
    for value in (candidate, candidate.strip()):
        index = text.find(value)
        if index >= 0:
            return {"start": index, "end": index + len(value)}, value

    normalised_candidate = _normalise(candidate)
    if not normalised_candidate:
        return None, None
    best: tuple[float, tuple[int, int, str] | None] = (0.0, None)
    for span in _sentence_spans(text):
        ratio = SequenceMatcher(None, normalised_candidate, _normalise(span[2])).ratio()
        if ratio > best[0]:
            best = (ratio, span)
    if best[0] >= 0.72 and best[1] is not None:
        start, end, sentence = best[1]
        return {"start": start, "end": end}, sentence
    return None, None


def _fallback_excerpt(definition: dict, text: str) -> tuple[str, str]:
    spans = _sentence_spans(text)
    if not spans:
        return "not_detected", ""

    code = definition["code"]
    candidates: list[tuple[int, int, str]] = []
    if code == "move_1_introducing_topic":
        candidates = [span for span in spans[:2] if _VISUAL_NOUN_RE.search(span[2])]
    elif code == "move_2_stating_overview":
        candidates = [span for span in spans if _OVERVIEW_RE.search(span[2])]
    elif code == "move_3_highlighting_key_trends":
        candidates = [span for span in spans if _TREND_RE.search(span[2])]
    elif code == "move_4_elaborating_key_trends":
        candidates = [span for span in spans if len(_NUMBER_RE.findall(span[2])) >= 1]
    elif code == "move_5_integrating_trend_and_detail":
        candidates = [
            span for span in spans
            if _TREND_RE.search(span[2]) and _NUMBER_RE.search(span[2])
        ]
    elif code == "move_6_comparing_contrasting":
        candidates = [span for span in spans if _COMPARISON_RE.search(span[2])]
    elif code == "move_7_closing_summary":
        candidates = [span for span in spans[-2:] if _CLOSING_RE.search(span[2])]

    return ("effective", candidates[0][2]) if candidates else ("not_detected", "")


def _normalise_status(value: Any, has_excerpt: bool) -> str:
    status = _normalise(value).replace(" ", "_")
    aliases = {
        "present": "effective",
        "strong": "effective",
        "met": "effective",
        "needs_attention": "developing",
        "weak": "developing",
        "partial": "developing",
        "missing": "not_detected",
        "absent": "not_detected",
        "na": "not_applicable",
    }
    status = aliases.get(status, status)
    if status in VALID_STATUSES:
        return status
    return "developing" if has_excerpt else "not_detected"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _official_value(record: dict) -> float | None:
    value = _number(record.get("official_value"))
    return value if value is not None else _number(record.get("value"))


def _record_axis_value(record: dict) -> str:
    return str(record.get("period") or record.get("category") or "").strip()


def _record_entity(record: dict) -> str:
    return str(record.get("series") or record.get("region") or record.get("category") or "").strip()


def _extreme_indices(records: list[dict]) -> list[int]:
    values = [(index, _official_value(record)) for index, record in enumerate(records)]
    values = [(index, value) for index, value in values if value is not None]
    if not values:
        return []
    highest = max(values, key=lambda item: item[1])[0]
    lowest = min(values, key=lambda item: item[1])[0]
    return list(dict.fromkeys([highest, lowest]))


def _largest_change_indices(chart_data: dict, records: list[dict]) -> list[int]:
    chart_type = str(chart_data.get("chart_type") or "")
    groups: dict[str, list[tuple[int, dict]]] = defaultdict(list)

    if chart_type in {"line", "area"}:
        for index, record in enumerate(records):
            groups[_record_entity(record)].append((index, record))
    elif chart_type == "bar":
        series_values = [str(record.get("series") or "") for record in records]
        temporal_series = sum(bool(_TEMPORAL_RE.match(value.strip())) for value in series_values)
        if temporal_series >= 2:
            for index, record in enumerate(records):
                groups[str(record.get("category") or "")].append((index, record))
        else:
            temporal_categories = sum(
                bool(_TEMPORAL_RE.match(str(record.get("category") or "").strip()))
                for record in records
            )
            if temporal_categories >= 2:
                for index, record in enumerate(records):
                    groups[str(record.get("series") or "")].append((index, record))

    candidates: list[tuple[float, list[int]]] = []
    for items in groups.values():
        valid = [(index, record, _official_value(record)) for index, record in items]
        valid = [(index, record, value) for index, record, value in valid if value is not None]
        if len(valid) < 2:
            continue
        first, last = valid[0], valid[-1]
        candidates.append((abs(last[2] - first[2]), [first[0], last[0]]))
    return max(candidates, key=lambda item: item[0])[1] if candidates else []


def _recommended_visual_indices(chart_data: dict, move_code: str) -> list[int]:
    records = [record for record in chart_data.get("records", []) if isinstance(record, dict)]
    if not records:
        return []
    change = _largest_change_indices(chart_data, records)
    extremes = _extreme_indices(records)
    if move_code == "move_2_stating_overview":
        return list(dict.fromkeys(change + extremes))[:4]
    if move_code == "move_3_highlighting_key_trends":
        return change[:2] if change else extremes[:1]
    if move_code == "move_5_integrating_trend_and_detail":
        return list(dict.fromkeys(change + extremes))[:3]
    return []


def _label_aliases(label: str) -> set[str]:
    key = _normalise(label)
    if not key:
        return set()
    aliases = {key}
    if " " not in key:
        aliases.update({f"{key}s", f"{key}es"})
        if key.endswith("y") and len(key) > 1:
            aliases.add(f"{key[:-1]}ies")
    return aliases


def _entity_mentions(text: str, labels: list[str]) -> list[tuple[int, int, str]]:
    mentions: list[tuple[int, int, str]] = []
    for label in labels:
        for alias in sorted(_label_aliases(label), key=len, reverse=True):
            escaped_alias = re.escape(alias).replace(r"\ ", r"\s+")
            pattern = re.compile(
                rf"(?<!\w){escaped_alias}(?!\w)",
                flags=re.IGNORECASE,
            )
            mentions.extend((match.start(), match.end(), label) for match in pattern.finditer(text))
    return sorted(set(mentions), key=lambda item: (item[0], -(item[1] - item[0])))


def _record_matches_entity(record: dict, entity: str) -> bool:
    entity_key = _normalise(entity)
    return any(
        entity_key and entity_key == _normalise(record.get(field))
        for field in ("category", "series", "region")
    )


def _record_value_matches_numbers(record: dict, numbers: list[float]) -> bool:
    value = _number(record.get("value"))
    if value is None:
        value = _official_value(record)
    return value is not None and any(abs(value - number) <= 1e-9 for number in numbers)


def _record_period_is_mentioned(record: dict, text: str) -> bool:
    return any(
        (label := str(record.get(field) or "").strip())
        and _TEMPORAL_RE.match(label)
        and _label_is_mentioned(text, label)
        for field in ("period", "category", "series")
    )


def _endpoint_record_indices_for_entities(records: list[dict], entities: list[str]) -> list[int]:
    indices: list[int] = []
    for entity in entities:
        matches = [
            index for index, record in enumerate(records)
            if _record_matches_entity(record, entity)
        ]
        if len(matches) > 2:
            matches = [matches[0], matches[-1]]
        indices.extend(matches)
    return list(dict.fromkeys(indices))[:4]


def _entity_has_matching_value(records: list[dict], entity: str, text: str) -> bool:
    numbers = _meaningful_numbers(text, records)
    return bool(numbers) and any(
        _record_matches_entity(record, entity)
        and _record_value_matches_numbers(record, numbers)
        for record in records
    )


def _entity_has_accurate_value(records: list[dict], entity: str, text: str) -> bool:
    mentions = _entity_mentions(text, _chart_entity_labels(records))
    numbers: list[float] = []
    for position, (start, _, mentioned_entity) in enumerate(mentions):
        if _normalise(mentioned_entity) != _normalise(entity):
            continue
        end = mentions[position + 1][0] if position + 1 < len(mentions) else len(text)
        numbers.extend(_meaningful_numbers(text[start:end], records))
        leading_value = re.search(
            r"([-+]?\d[\d,]*(?:\.\d+)?)\s*%?\s+(?:for|in|at|to)\s+$",
            text[max(0, start - 80):start],
            flags=re.IGNORECASE,
        )
        if leading_value:
            numbers.append(float(leading_value.group(1).replace(",", "")))
    return bool(numbers) and any(
        _record_matches_entity(record, entity)
        and (official := _official_value(record)) is not None
        and any(abs(official - number) <= 1e-9 for number in numbers)
        for record in records
    )


def _sentences_share_paragraph(
    text: str,
    first: tuple[int, int, str],
    second: tuple[int, int, str],
) -> bool:
    return not re.search(r"(?:\r?\n)\s*(?:\r?\n)", text[first[1]:second[0]])


def _mark_effective(assessment: dict, student_answer: str, excerpt: str, rationale: str) -> None:
    assessment["status"] = "effective"
    assessment["rationale"] = rationale
    assessment["hint"] = ""
    _replace_assessment_excerpt(assessment, student_answer, excerpt)


def _relative_period_record_indices(
    records: list[dict],
    entities: list[str],
    text: str,
) -> list[int]:
    position: str | None = None
    if re.search(r"\b(?:first|initial)\s+(?:year|period)\b|\bat\s+the\s+(?:start|beginning)\b", text, re.IGNORECASE):
        position = "first"
    elif re.search(r"\b(?:final|last)\s+(?:year|period)\b|\b(?:by|at)\s+the\s+end\b", text, re.IGNORECASE):
        position = "last"
    if position is None:
        return []

    indices: list[int] = []
    for entity in entities:
        matches = [
            index for index, record in enumerate(records)
            if _record_matches_entity(record, entity)
        ]
        if matches:
            indices.append(matches[0] if position == "first" else matches[-1])
    return list(dict.fromkeys(indices))[:4]


def _mentioned_record_indices(records: list[dict], excerpt: str) -> list[int]:
    excerpt_key = _normalise(excerpt)
    relationship_value = bool(re.search(
        r"\b(?:gap|difference|spread|above|below|ahead|behind|exceed(?:ed|s)?|"
        r"higher|lower|more|less)\b",
        excerpt,
        flags=re.IGNORECASE,
    ))
    entity_labels = _chart_entity_labels(records)
    mentions = _entity_mentions(excerpt, entity_labels)
    global_numbers = _meaningful_numbers(excerpt, records)
    matched: list[int] = []

    for position, (start, _, entity) in enumerate(mentions):
        segment_end = mentions[position + 1][0] if position + 1 < len(mentions) else len(excerpt)
        segment = excerpt[start:segment_end]
        segment_numbers = _meaningful_numbers(segment, records)
        candidates = [
            index for index, record in enumerate(records)
            if _record_matches_entity(record, entity)
        ]
        value_matches = [
            index for index in candidates
            if _record_value_matches_numbers(records[index], segment_numbers)
        ]
        period_matches = [
            index for index in candidates
            if _record_period_is_mentioned(records[index], segment)
        ]
        leading_value_match = re.search(
            r"([-+]?\d[\d,]*(?:\.\d+)?)\s*%?\s+(?:for|in|at|to)\s+$",
            excerpt[max(0, start - 80):start],
            flags=re.IGNORECASE,
        )
        leading_value_matches: list[int] = []
        if leading_value_match:
            leading_number = float(leading_value_match.group(1).replace(",", ""))
            leading_value_matches = [
                index for index in candidates
                if _record_value_matches_numbers(records[index], [leading_number])
            ]
        if value_matches:
            matched.extend(value_matches)
        elif period_matches:
            matched.extend(period_matches)
        elif leading_value_matches:
            matched.extend(leading_value_matches)
        elif not global_numbers and not relationship_value:
            matched.extend(_endpoint_record_indices_for_entities(records, [entity]))

    # A stated gap usually gives the relationship value rather than either data
    # value. In that case, map all named entities to the named period.
    if relationship_value:
        temporal_records = [
            index for index, record in enumerate(records)
            if _record_period_is_mentioned(record, excerpt)
        ]
        if temporal_records:
            for _, _, entity in mentions:
                matched.extend(
                    index for index in temporal_records
                    if _record_matches_entity(records[index], entity)
                )
        elif relative_indices := _relative_period_record_indices(
            records,
            [entity for _, _, entity in mentions],
            excerpt,
        ):
            matched.extend(relative_indices)
        elif not matched:
            matched.extend(_endpoint_record_indices_for_entities(
                records,
                [entity for _, _, entity in mentions],
            ))

    respectively = re.search(r"\brespectively\b", excerpt, re.IGNORECASE)
    if respectively:
        prefix = excerpt[:respectively.start()]
        prefix_entities = list(dict.fromkeys(
            entity for start, _, entity in mentions if start < respectively.start()
        ))
        prefix_numbers = _meaningful_numbers(prefix, records)
        if len(prefix_entities) >= 2 and len(prefix_numbers) >= 2:
            pair_count = min(len(prefix_entities), len(prefix_numbers), 4)
            for entity, number in zip(
                prefix_entities[-pair_count:],
                prefix_numbers[-pair_count:],
            ):
                matched.extend(
                    index for index, record in enumerate(records)
                    if _record_matches_entity(record, entity)
                    and _record_value_matches_numbers(record, [number])
                )

    matched_set = set(matched)
    return [index for index in range(len(records)) if index in matched_set][:4]


def _selector_record_indices(records: list[dict], selectors: Any) -> list[int]:
    """Resolve model-provided visual selectors against validated chart records."""
    if not isinstance(selectors, list):
        return []
    matched: list[int] = []
    fields = ("category", "series", "period", "region")
    for selector in selectors[:8]:
        if isinstance(selector, int) and 0 <= selector < len(records):
            matched.append(selector)
            continue
        if not isinstance(selector, dict):
            continue
        selector_fields = {
            field: _normalise(selector.get(field))
            for field in fields
            if selector.get(field) not in (None, "")
        }
        selector_value = _number(selector.get("value"))
        best_index: int | None = None
        best_score = 0
        for index, record in enumerate(records):
            score = sum(
                bool(value) and value == _normalise(record.get(field))
                for field, value in selector_fields.items()
            )
            official = _official_value(record)
            if selector_value is not None and official is not None:
                score += 1 if abs(selector_value - official) <= 1e-6 else -1
            required_score = max(1, len(selector_fields))
            if score >= required_score and score > best_score:
                best_index, best_score = index, score
        if best_index is not None:
            matched.append(best_index)
    return list(dict.fromkeys(matched))[:4]


def _visual_focus_from_model(records: list[dict], raw: dict) -> tuple[list[int], list[int]]:
    focus = raw.get("visual_focus") if isinstance(raw.get("visual_focus"), dict) else {}
    current = _selector_record_indices(
        records,
        focus.get("current") or focus.get("current_focus") or raw.get("current_focus"),
    )
    recommended = _selector_record_indices(
        records,
        focus.get("recommended")
        or focus.get("recommended_focus")
        or raw.get("recommended_focus"),
    )
    return current, recommended


def _label_is_mentioned(text: str, label: str) -> bool:
    aliases = _label_aliases(label)
    if not aliases:
        return False
    text_key = f" {_normalise(text)} "
    return any(f" {alias} " in text_key for alias in aliases)


def _chart_entity_labels(records: list[dict]) -> list[str]:
    labels: list[str] = []
    for record in records:
        for field in ("series", "category", "region"):
            label = str(record.get(field) or "").strip()
            if not label or _TEMPORAL_RE.match(label):
                continue
            if _normalise(label) not in {_normalise(item) for item in labels}:
                labels.append(label)
    return labels


def _mentioned_entities(text: str, labels: list[str]) -> list[str]:
    return [label for label in labels if _label_is_mentioned(text, label)]


def _meaningful_numbers(text: str, records: list[dict]) -> list[float]:
    periods = {
        _normalise(record.get(field))
        for record in records
        for field in ("period", "category", "series")
        if _TEMPORAL_RE.match(str(record.get(field) or "").strip())
    }
    values: list[float] = []
    for match in _NUMBER_RE.finditer(text):
        raw = match.group().replace(",", "")
        if _normalise(raw) in periods:
            continue
        try:
            values.append(float(raw))
        except ValueError:
            continue
    return values


def _record_indices_for_entities(records: list[dict], entities: list[str]) -> list[int]:
    indices: list[int] = []
    for index, record in enumerate(records):
        record_text = " ".join(
            str(record.get(field) or "")
            for field in ("category", "series", "region")
        )
        if any(_label_is_mentioned(record_text, entity) for entity in entities):
            indices.append(index)
    return indices[:4]


def _record_indices_for_values(records: list[dict], text: str) -> list[int]:
    numbers = {
        float(value.replace(",", ""))
        for value in _NUMBER_RE.findall(text)
    }
    return [
        index for index, record in enumerate(records)
        if (value := _number(record.get("value"))) is not None
        and any(abs(value - number) <= 1e-9 for number in numbers)
    ][:4]


def _declared_focus_candidate(
    records: list[dict],
    spans: list[tuple[int, int, str]],
) -> tuple[str, list[int]]:
    """Return the first explicit statement of what the writer treats as central."""
    for _, _, sentence in spans:
        if not _DECLARED_FOCUS_RE.search(sentence):
            continue
        focus_clause = re.split(
            r"\b(?:although|even\s+though|despite|whereas|while|but)\b",
            sentence,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        indices = (
            _mentioned_record_indices(records, focus_clause)
            or _record_indices_for_values(records, focus_clause)
        )
        if indices:
            return sentence, indices
    return "", []


def _finalise_visual_targets(assessments: list[dict], records: list[dict]) -> None:
    """Only expose a red/blue comparison when both sides are grounded and distinct."""
    for assessment in assessments:
        if assessment.get("code") not in VISUAL_MOVE_CODES:
            continue
        if assessment.get("status") not in {"developing", "not_detected"}:
            assessment["visual_available"] = False
            assessment.pop("visual_targets", None)
            continue

        targets = assessment.get("visual_targets")
        if not isinstance(targets, dict):
            assessment["visual_available"] = False
            continue
        recommended = list(dict.fromkeys(
            index for index in targets.get("recommended_record_indices", [])
            if isinstance(index, int) and 0 <= index < len(records)
        ))
        current = list(dict.fromkeys(
            index for index in targets.get("current_focus_record_indices", [])
            if isinstance(index, int) and 0 <= index < len(records)
        ))
        if assessment.get("status") == "developing" and not current:
            excerpt = str(assessment.get("excerpt") or "")
            current = (
                _mentioned_record_indices(records, excerpt)
                or _record_indices_for_values(records, excerpt)
            )

        distinct_current = [index for index in current if index not in recommended]
        assessment["visual_targets"] = {
            "current_focus_record_indices": current,
            "recommended_record_indices": recommended,
        }
        assessment["visual_available"] = bool(
            recommended
            and (distinct_current or assessment.get("status") == "not_detected")
        )


def _replace_assessment_excerpt(assessment: dict, student_answer: str, excerpt: str) -> None:
    excerpt_range, matched_excerpt = _find_excerpt_range(student_answer, excerpt)
    assessment["excerpt"] = matched_excerpt or ""
    assessment["range"] = excerpt_range


def _apply_local_quality_guards(
    chart_data: dict,
    student_answer: str,
    assessments: list[dict],
    records: list[dict],
) -> None:
    """Correct recurring semantic false positives using chart-grounded evidence."""
    by_code = {assessment["code"]: assessment for assessment in assessments}
    spans = _sentence_spans(student_answer)
    entity_labels = _chart_entity_labels(records)

    # Move 1: merely naming generic visual contents does not identify the topic
    # and scope that the reader needs.
    for _, _, sentence in spans[:2]:
        if not _VISUAL_NOUN_RE.search(sentence) or not _VAGUE_INTRO_RE.search(sentence):
            continue
        assessment = by_code["move_1_introducing_topic"]
        assessment["status"] = "developing"
        assessment["rationale"] = "The opening identifies a visual generically but does not establish its subject and scope."
        assessment["hint"] = "Name the subject shown and the relevant scope, such as the groups, place, or time period."
        _replace_assessment_excerpt(assessment, student_answer, sentence)
        break

    # Move 2: an Overall sentence made up of individual values is detail, not a
    # synthesis of the pattern those values create.
    for _, _, sentence in spans:
        if not _OVERVIEW_RE.search(sentence):
            continue
        if len(_meaningful_numbers(sentence, records)) < 2:
            continue
        if _OVERVIEW_SYNTHESIS_RE.search(sentence):
            continue
        assessment = by_code["move_2_stating_overview"]
        assessment["status"] = "developing"
        assessment["rationale"] = "The overview lists individual values without synthesising the broad pattern they form."
        assessment["hint"] = "Step back from the individual values and identify the broad pattern a reader should notice first."
        _replace_assessment_excerpt(assessment, student_answer, sentence)
        current = _mentioned_record_indices(records, sentence) or _record_indices_for_values(records, sentence)
        recommended = _recommended_visual_indices(chart_data, "move_2_stating_overview")
        assessment["visual_targets"] = {
            "current_focus_record_indices": current,
            "recommended_record_indices": recommended,
        }
        assessment["visual_available"] = bool(recommended)
        break

    assessment = by_code["move_2_stating_overview"]
    if assessment["status"] == "developing":
        excerpt = assessment.get("excerpt") or ""
        current = (
            _mentioned_record_indices(records, excerpt)
            or _record_indices_for_values(records, excerpt)
        )
        recommended = _recommended_visual_indices(
            chart_data,
            "move_2_stating_overview",
        )
        assessment["visual_targets"] = {
            "current_focus_record_indices": current,
            "recommended_record_indices": recommended,
        }
        assessment["visual_available"] = bool(recommended)

    # Move 3 follows the writer's explicit declaration of priority. A later
    # accurate description does not erase an earlier "principal pattern" claim.
    assessment = by_code["move_3_highlighting_key_trends"]
    recommended = _recommended_visual_indices(
        chart_data,
        "move_3_highlighting_key_trends",
    )
    declared_sentence, declared_current = _declared_focus_candidate(records, spans)
    declared_misaligned = False
    if declared_sentence and recommended:
        aligned = all(index in declared_current for index in recommended)
        if not aligned:
            declared_misaligned = True
            assessment["status"] = "developing"
            assessment["rationale"] = (
                "The draft explicitly declares a less informative feature as its main focus, "
                "while the official chart contains a more consequential pattern."
            )
            assessment["hint"] = (
                "Prioritise the chart's most consequential pattern before discussing the smaller feature."
            )
            _replace_assessment_excerpt(assessment, student_answer, declared_sentence)
            assessment["visual_targets"] = {
                "current_focus_record_indices": declared_current,
                "recommended_record_indices": recommended,
            }
            assessment["visual_available"] = True
        elif assessment["status"] in {"developing", "not_detected"}:
            _mark_effective(
                assessment,
                student_answer,
                declared_sentence,
                "The draft explicitly prioritises a chart-salient feature.",
            )

    if assessment["status"] == "developing":
        excerpt = assessment.get("excerpt") or ""
        current = declared_current if declared_misaligned else (
            _mentioned_record_indices(records, excerpt)
            or _record_indices_for_values(records, excerpt)
        )
        assessment["visual_targets"] = {
            "current_focus_record_indices": current,
            "recommended_record_indices": recommended,
        }
        assessment["visual_available"] = bool(recommended)

    # Move 4: naming a priority trend is not elaboration unless that same chart
    # entity is supported somewhere with a concrete, non-period value.
    priority_candidates: list[tuple[int, str, list[str]]] = []
    for span_index, (_, _, sentence) in enumerate(spans):
        entities = _mentioned_entities(sentence, entity_labels)
        if (
            entities
            and _PRIORITY_RE.search(sentence)
            and (_TREND_RE.search(sentence) or _OVERVIEW_SYNTHESIS_RE.search(sentence))
        ):
            priority_candidates.append((span_index, sentence, entities))
    unsupported = []
    for _, sentence, entities in priority_candidates:
        for entity in entities:
            has_evidence = any(
                _label_is_mentioned(other_sentence, entity)
                and _entity_has_accurate_value(records, entity, other_sentence)
                for _, _, other_sentence in spans
            )
            if not has_evidence:
                unsupported.append((sentence, entity))
    if unsupported:
        sentence, entity = unsupported[0]
        assessment = by_code["move_4_elaborating_key_trends"]
        assessment["status"] = "developing"
        assessment["rationale"] = (
            f"The draft identifies {entity} as a key feature but does not support that "
            "feature with concrete chart evidence."
        )
        assessment["hint"] = "Add a small amount of relevant evidence for the key feature already identified."
        _replace_assessment_excerpt(assessment, student_answer, sentence)
    elif priority_candidates:
        assessment = by_code["move_4_elaborating_key_trends"]
        if assessment["status"] in {"developing", "not_detected"}:
            _mark_effective(
                assessment,
                student_answer,
                priority_candidates[0][1],
                "The identified key feature is supported with relevant, accurate chart evidence.",
            )

    # Move 5 accepts an explicit priority statement whose chart-grounded evidence
    # appears in the same sentence or the immediately following sentence in the
    # same paragraph. A contradictory support link below still takes precedence.
    for span_index, sentence, entities in priority_candidates:
        evidence_text = sentence
        if span_index + 1 < len(spans) and _sentences_share_paragraph(
            student_answer,
            spans[span_index],
            spans[span_index + 1],
        ):
            evidence_text = f"{sentence} {spans[span_index + 1][2]}"
        if not all(
            _entity_has_accurate_value(records, entity, evidence_text)
            for entity in entities
        ):
            continue
        assessment = by_code["move_5_integrating_trend_and_detail"]
        if assessment["status"] in {"developing", "not_detected"}:
            _mark_effective(
                assessment,
                student_answer,
                sentence,
                "The key feature and its supporting chart evidence are connected coherently.",
            )
        break

    # Move 5: evidence after an explicit support link must belong to the trend
    # subject before the link. Different chart entities indicate a broken link.
    for _, _, sentence in spans:
        link = _SUPPORT_LINK_RE.search(sentence)
        if not link:
            continue
        support_text = sentence[link.end():]
        current_entities = _mentioned_entities(support_text, entity_labels)
        trend_entities = _mentioned_entities(sentence[:link.start()], entity_labels)
        if not trend_entities:
            continue
        support_core = re.split(
            r"\b(?:compared\s+with|whereas|while|rather\s+than)\b",
            support_text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        support_core_entities = _mentioned_entities(support_core, entity_labels)
        if not support_core_entities:
            current_entities.extend(
                entity for entity in trend_entities
                if _entity_has_matching_value(records, entity, support_core)
                and entity not in current_entities
            )
        if not current_entities:
            continue
        if {_normalise(item) for item in current_entities}.intersection(
            {_normalise(item) for item in trend_entities}
        ):
            continue
        assessment = by_code["move_5_integrating_trend_and_detail"]
        assessment["status"] = "developing"
        assessment["rationale"] = (
            "The supporting evidence refers to a different chart entity from the trend it is meant to explain."
        )
        assessment["hint"] = "Link the selected trend to evidence from the same chart entity."
        _replace_assessment_excerpt(assessment, student_answer, sentence)
        current = (
            _mentioned_record_indices(records, support_text)
            or _endpoint_record_indices_for_entities(records, current_entities)
        )
        recommended = _endpoint_record_indices_for_entities(records, trend_entities)
        assessment["visual_targets"] = {
            "current_focus_record_indices": current,
            "recommended_record_indices": recommended,
        }
        assessment["visual_available"] = bool(recommended)
        break

    # Move 6: a sentence that only says unspecified items differ does not make a
    # useful relationship available to the reader.
    for _, _, sentence in spans:
        if not _VAGUE_COMPARISON_RE.search(sentence):
            continue
        if len(_mentioned_entities(sentence, entity_labels)) >= 2:
            continue
        if _meaningful_numbers(sentence, records):
            continue
        assessment = by_code["move_6_comparing_contrasting"]
        assessment["status"] = "developing"
        assessment["rationale"] = "The comparison is present, but the items and relationship remain unspecified."
        assessment["hint"] = "Name the items being compared and make their relevant relationship explicit."
        _replace_assessment_excerpt(assessment, student_answer, sentence)
        break

    # Move 7 remains optional. When a conclusion is actually present, however,
    # metadata or references to previously listed values should be reviewed.
    for _, _, sentence in spans[-3:]:
        if not _EXPLICIT_CLOSING_RE.search(sentence) or not _WEAK_CLOSING_RE.search(sentence):
            continue
        assessment = by_code["move_7_closing_summary"]
        assessment["status"] = "developing"
        assessment["rationale"] = "The closing statement repeats chart metadata or listed details instead of synthesising the message."
        assessment["hint"] = "If a conclusion is retained, use it to synthesise the main message rather than repeat metadata."
        _replace_assessment_excerpt(assessment, student_answer, sentence)
        break


def build_move_feedback(
    chart_data: dict,
    student_answer: str,
    raw_assessments: Any = None,
) -> dict:
    if isinstance(raw_assessments, dict):
        raw_assessments = raw_assessments.get("assessments")
    raw_items = raw_assessments if isinstance(raw_assessments, list) else []
    by_code: dict[str, dict] = {}
    aliases = {
        definition["short_code"].casefold(): definition["code"]
        for definition in MOVE_DEFINITIONS
    }
    aliases.update({str(definition["number"]): definition["code"] for definition in MOVE_DEFINITIONS})
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        raw_code = str(item.get("code") or item.get("short_code") or item.get("move") or "")
        code = aliases.get(raw_code.casefold(), raw_code)
        if code in MOVE_CODES and code not in by_code:
            by_code[code] = item

    records = [record for record in chart_data.get("records", []) if isinstance(record, dict)]
    assessments: list[dict] = []
    for definition in MOVE_DEFINITIONS:
        code = definition["code"]
        raw = by_code.get(code)
        source = "model" if raw is not None else "local_fallback"
        if raw is None:
            fallback_status, fallback_excerpt = _fallback_excerpt(definition, student_answer)
            raw = {
                "status": fallback_status,
                "excerpt": fallback_excerpt,
                "rationale": "A local fallback identified rhetorical evidence in the draft."
                if fallback_excerpt else "No clear evidence for this move was identified locally.",
            }

        excerpt_range, matched_excerpt = _find_excerpt_range(student_answer, raw.get("excerpt", ""))
        status = _normalise_status(raw.get("status"), matched_excerpt is not None)
        if status == "developing" and matched_excerpt is None:
            status = "not_detected"

        hint = str(raw.get("hint") or "").strip()[:500]
        if status in {"developing", "not_detected"} and _NO_REVISION_NEEDED_RE.search(hint):
            status = "effective"
        if status == "effective":
            hint = ""
        if status != "effective" and not hint:
            hint = _DEFAULT_HINTS[code]
        rationale = str(raw.get("rationale") or "").strip()[:500]
        if not rationale:
            rationale = (
                "This rhetorical move is clearly represented in the highlighted text."
                if status == "effective"
                else "This move could be clearer or more purposeful in the current draft."
            )

        assessment = {
            "id": code,
            "code": code,
            "number": definition["number"],
            "short_code": definition["short_code"],
            "label": definition["label"],
            "purpose": definition["purpose"],
            "feedback_mode": definition["feedback_mode"],
            "status": status,
            "rationale": rationale,
            "hint": hint,
            "excerpt": matched_excerpt or "",
            "range": excerpt_range,
            "analysis_source": source,
            "visual_available": False,
        }

        if code in VISUAL_MOVE_CODES and status in {"developing", "not_detected"}:
            model_current, model_recommended = _visual_focus_from_model(records, raw)
            recommended = model_recommended or _recommended_visual_indices(chart_data, code)
            current_focus = (
                model_current
                or _mentioned_record_indices(records, matched_excerpt or "")
            )
            assessment["visual_targets"] = {
                "recommended_record_indices": recommended,
                "current_focus_record_indices": current_focus,
            }
            assessment["visual_available"] = bool(recommended)
        assessments.append(assessment)

    _apply_local_quality_guards(chart_data, student_answer, assessments, records)
    _finalise_visual_targets(assessments, records)

    counts = {status: 0 for status in VALID_STATUSES}
    for assessment in assessments:
        counts[assessment["status"]] += 1
    # Only an identified weakness is counted as requiring attention. An absent
    # optional move is presented as an opportunity, not automatically as an error.
    attention_count = counts["developing"]
    return {
        "version": MOVE_FEEDBACK_VERSION,
        "scope": MOVE_FEEDBACK_SCOPE,
        "definitions": [dict(item) for item in MOVE_DEFINITIONS],
        "assessments": assessments,
        "summary": {
            "total_moves": len(MOVE_DEFINITIONS),
            "attention_count": attention_count,
            "counts": counts,
        },
        "principles": [
            "Feedback provides evidence and hints rather than replacement sentences.",
            "Moves are rhetorical options, so absence is not automatically an error.",
            "Visual cues are complementary and are limited to Moves 2, 3, and 5.",
        ],
    }


def attach_move_feedback(chart_data: dict, student_answer: str, raw_assessments: Any = None) -> dict:
    chart_data["move_feedback"] = build_move_feedback(
        chart_data,
        student_answer,
        raw_assessments,
    )
    chart_data["schema_version"] = "2.0"
    return chart_data
