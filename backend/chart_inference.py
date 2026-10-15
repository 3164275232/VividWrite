"""Conservative, traceable numerical inferences from a learner's own claims.

Reference values are deliberately never read here. An unbounded qualitative
trend (for example, 'B increased') does not establish a numerical height.
"""

import math
import re


def _stated(record):
    value = record.get("value")
    return (record.get("explicit_student_value") is True and not record.get("missing")
            and not record.get("estimated") and isinstance(value, (int, float))
            and not isinstance(value, bool) and math.isfinite(value)
            and not record.get("conflicting_values"))


def _label(value):
    return r"(?<!\w)" + re.escape(str(value)) + r"(?!\w)"


def is_asserted_claim(sentence):
    """Do not turn a negated, conditional or speculative sentence into a number."""
    return not re.search(
        r"\b(?:if|unless|would|could|might|may|perhaps|possibly|not|never|neither|nor|no)\b|n['’]t\b",
        sentence, re.I,
    )


def infer_supported_comparisons(result, essay):
    """Recover ratios, numerical differences and an explicitly described remainder.

    Only empty cells can be filled. Ambiguous series, conflicting derivations and
    inferences without a stated anchor remain empty; explicit claims always win.
    """
    chart_type = result.get("chart_type")
    if chart_type not in {"bar", "line", "area", "pie"}:
        return
    records = result.get("records", [])
    anchors = [record for record in records if _stated(record)]
    sentences = [part.strip() for part in re.split(r"(?<=[.!?;])\s+|[\r\n]+", essay) if part.strip()]
    series = {record.get("series") for record in records if record.get("series")}
    link = r"\s+(?:(?:was|is|were|had|recorded|represented|reached|accounted\s+for|stood\s+at)\s+)?(?:about\s+|roughly\s+)?"
    ratio = r"(?P<ratio>twice|double|half|three\s+times|triple)(?:\s+(?:that|the\s+(?:figure|value|share|rate)))?(?:\s+(?:of|for))?\s+"
    difference = r"(?P<delta>\d+(?:\.\d+)?)\s+(?P<unit>percentage\s+points?|million|billion|thousand|units?)\s+(?P<direction>higher|lower|more|less)\s+than\s+"
    for target in records:
        if target.get("value") is not None or not target.get("category"):
            continue
        candidates = []
        for sentence in sentences:
            if not is_asserted_claim(sentence):
                continue
            if chart_type != "pie" and len(series) > 1:
                mentioned = [name for name in series if re.search(_label(name), sentence, re.I)]
                if mentioned != [target.get("series")]:
                    continue
            for anchor in anchors:
                if anchor.get("category") == target.get("category"):
                    continue
                if chart_type != "pie" and anchor.get("series") != target.get("series"):
                    continue
                start = _label(target["category"]) + link
                end = _label(anchor["category"])
                match = re.search(start + ratio + end, sentence, re.I)
                delta_match = re.search(start + difference + end, sentence, re.I)
                if match:
                    word = re.sub(r"\s+", " ", match.group("ratio").lower())
                    factor = {"twice": 2, "double": 2, "half": .5, "three times": 3, "triple": 3}[word]
                    value = anchor["value"] * factor
                    explanation = f"{anchor['category']} ({anchor['value']:g}) × {factor:g}, using your comparison."
                    candidates.append((value, "stated_ratio", explanation, sentence, anchor))
                elif delta_match:
                    unit = re.sub(r"\s+", " ", delta_match.group("unit").lower())
                    axis_unit = str(result.get("axes", {}).get("unit", "")).lower()
                    if not (("percentage" in unit and ("%" in axis_unit or "percent" in axis_unit))
                            or unit.rstrip("s") in axis_unit):
                        continue
                    delta = float(delta_match.group("delta"))
                    sign = 1 if delta_match.group("direction").lower() in {"higher", "more"} else -1
                    value = anchor["value"] + sign * delta
                    explanation = f"{anchor['category']} ({anchor['value']:g}) {'+' if sign > 0 else '−'} {delta:g}, using your comparison."
                    candidates.append((value, "stated_difference", explanation, sentence, anchor))
            if chart_type == "pie" and ("%" in str(result.get("axes", {}).get("unit", "")) or "percent" in str(result.get("axes", {}).get("unit", "")).lower()) and re.search(
                _label(target["category"]) + r"[^.!?;]{0,60}\b(?:remainder|rest|remaining\s+(?:share|portion))\b", sentence, re.I
            ):
                others = [record for record in records if record is not target]
                if others and all(_stated(record) for record in others):
                    value = 100 - sum(record["value"] for record in others)
                    if 0 <= value <= 100:
                        candidates.append((value, "stated_remainder", "100% minus the other shares explicitly stated in your report.", sentence, None))
        values = {round(candidate[0], 6) for candidate in candidates}
        if len(values) != 1 or next(iter(values)) < 0:
            continue
        value, method, explanation, sentence, anchor = candidates[0]
        target.update(value=round(value, 6), missing=False, estimated=True,
                      explicit_student_value=False, confidence=.8, data_source="inferred",
                      inference={"method": method, "explanation": explanation, "student_evidence": sentence,
                                 "anchor": {"category": anchor["category"], "series": anchor.get("series"),
                                            "value": anchor["value"]} if anchor else None})


def finalise_provenance(result):
    """Keep inference provenance separate from errors in explicitly stated values."""
    for record in result.get("records", []):
        if record.get("missing") or record.get("value") is None:
            record["data_source"] = "missing"
        elif record.get("explicit_student_value"):
            record["estimated"] = False
            record["data_source"] = "stated"
            record.pop("inference", None)
        elif record.get("estimated"):
            record.update(data_source="inferred", incorrect=False, feedback_status="estimated")
