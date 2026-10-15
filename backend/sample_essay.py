from fastapi import APIRouter, Request
from pydantic import BaseModel
import re
from typing import Optional, Dict, Any
from deepseek_config import get_deepseek_api_key, get_deepseek_client, get_deepseek_extra_body, get_deepseek_model
from chart_text import (
    CHART_TYPE_LABELS,
    InvalidExtractedChartData,
    build_table_fact_checks,
    correct_false_spread_direction_claims,
    find_table_fact_contradictions,
    infer_deplot_value_precision,
    parse_validated_pie_table,
    quantize_chart_value,
    round_deplot_table_values,
    soften_false_monotonic_claims,
)

router = APIRouter()

_DECIMAL_DATA_RE = re.compile(r"(?<![\w.])(?P<value>-?\d+\.\d+)(?![\w.])")


def _round_essay_data_values(text: str, precision: int) -> str:
    return _DECIMAL_DATA_RE.sub(
        lambda match: (
            f"{quantize_chart_value(match.group('value'), precision):g}"
        ),
        text,
    )

class SampleEssayRequest(BaseModel):
    deplot_text: str
    requirement: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 0.2
    min_words: Optional[int] = 150
    chart_type: Optional[str] = None

class SampleEssayResponse(BaseModel):
    success: bool
    essay: Optional[str] = None
    error: Optional[str] = None
    debug: Optional[Dict[str, Any]] = None

def _generate_essay_text(client, model: str, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
    chat = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body=get_deepseek_extra_body(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    if not chat.choices:
        return ""
    message = chat.choices[0].message
    content = getattr(message, "content", None) or ""
    return content.strip()


def _generate_sample_essay(req: SampleEssayRequest):
    """Generate a full IELTS Task 1 sample essay from extracted chart data."""
    if not get_deepseek_api_key():
        return SampleEssayResponse(success=False, error="DEEPSEEK_API_KEY not configured")
    if not req.deplot_text or not req.deplot_text.strip():
        return SampleEssayResponse(success=False, error="deplot_text required")

    raw_deplot = (req.deplot_text or '').replace('<0x0A>', '\n')[:8000]
    normalized_deplot = raw_deplot
    visual_label = CHART_TYPE_LABELS.get((req.chart_type or "").casefold())
    marker = re.search(r"^CHART TYPE\s*\|\s*(.+)$", raw_deplot, flags=re.MULTILINE | re.IGNORECASE)
    if marker:
        visual_label = marker.group(1).strip()
    visual_label = visual_label or "chart"
    visual_type_instruction = (
        f"The original source visual is a {visual_label}. The textual table is only an internal "
        f"machine-readable representation. Refer to the source as a {visual_label}, never as a table. "
    )
    is_pie_chart = req.chart_type == "pie" or "CHART TYPE | Pie chart" in raw_deplot
    if is_pie_chart:
        try:
            parse_validated_pie_table(raw_deplot)
        except InvalidExtractedChartData as exc:
            return SampleEssayResponse(
                success=False,
                error=(
                    f"Pie chart data extraction is inconsistent: {exc} "
                    "Please upload the image again so DePlot can re-extract the isolated pie plot."
                ),
            )
    chart_type_key = (req.chart_type or "").casefold()
    statistical_visual = (
        chart_type_key in {"bar", "line", "pie"}
        or any(name in visual_label.casefold() for name in ("bar", "line", "pie"))
    )
    value_precision = infer_deplot_value_precision(raw_deplot, chart_type_key)
    if statistical_visual:
        normalized_deplot = round_deplot_table_values(
            raw_deplot,
            precision=value_precision,
            chart_type=chart_type_key,
        )
    if value_precision == 0:
        precision_guidance = (
            "All chart data values have been rounded to integers. "
            "Use integer data values only and never print decimal places. "
        )
    else:
        decimal_label = "decimal place" if value_precision == 1 else "decimal places"
        precision_guidance = (
            f"Small-scale chart values retain up to {value_precision} {decimal_label}. "
            "Preserve that precision where shown and do not round those values to whole numbers. "
        )
    fact_checks = build_table_fact_checks(normalized_deplot)
    fact_check_block = fact_checks or "No additional deterministic comparisons were available."
    requirement = req.requirement or (
        "Write a descriptive academic report of at least 150 words, such as IELTS "
        "Task 1, summarizing the main features and making relevant comparisons."
    )
    structure_guidance = (
        "Use the standard IELTS Task 1 structure: "
        "Introduction -> Overview -> Key Details A -> Key Details B. "
    )

    system_prompt = (
        "You are an expert in descriptive academic writing, including IELTS Task 1 "
        "and data commentary. Produce a high-quality sample response. "
        "Use a neutral objective tone, full paragraphs, no bullet points, and no first person. "
        "The chart data is the factual source of truth. Preserve every category-value "
        "pairing exactly and silently verify all numeric claims before answering. "
        f"{precision_guidance}"
        "Never contradict the deterministic rankings or crossing statements supplied "
        "in the user message. Do not infer causes, motives, priorities, perceptions, "
        "or whether a cost is fixed or discretionary unless the visual explicitly states them. "
        f"{visual_type_instruction}"
        f"{structure_guidance}"
        "The Overview must synthesize main patterns rather than list isolated values. "
        "Group supporting data logically across Key Details A and Key Details B. "
        "Do not generate an independent conclusion."
    )

    common_prompt = (
        f"OFFICIAL REQUIREMENT:\n{requirement}\n\n"
        f"ORIGINAL VISUAL TYPE:\n{visual_label}\n\n"
        f"CHART TEXTUAL DATA (primary facts, may contain minor OCR noise):\n"
        f"{normalized_deplot}\n\n"
        f"DETERMINISTIC COMPARISON CHECKS (must not be contradicted):\n"
        f"{fact_check_block}\n\n"
    )
    user_prompt = (
        common_prompt
        + "TASK: Write the full report using Introduction, Overview, Key Details A, "
        f"and Key Details B. Minimum {req.min_words or 150} words. "
        "Do not add a separate conclusion, headings, or meta explanation. "
        "Return only the raw essay text."
    )

    client = get_deepseek_client()
    model = get_deepseek_model(req.model)
    try:
        essay = _generate_essay_text(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=req.temperature if req.temperature is not None else 0.2,
            max_tokens=800,
        )
        if statistical_visual:
            essay = _round_essay_data_values(essay, value_precision)
        fact_attempts = 1
        contradictions = find_table_fact_contradictions(normalized_deplot, essay)
        if contradictions:
            correction_prompt = (
                f"{user_prompt}\n\n"
                "REWRITE REQUIRED: The previous draft failed deterministic factual validation.\n"
                + "\n".join(f"- {item}" for item in contradictions)
                + (
                    "\nRewrite the complete report and correct every issue above. "
                    "Do not reuse any rejected equality or monotonic wording. "
                    "Check whether the highest-to-lowest gap widens or narrows. "
                    "Distinguish an overall change from a steady, consistent, continuous, "
                    "or sustained change: those modifiers are allowed only when every "
                    "recorded interval moves in the same direction. "
                    "Return only the raw essay text.\n\n"
                )
                + f"PREVIOUS DRAFT:\n{essay}"
            )
            essay = _generate_essay_text(
                client=client,
                model=model,
                system_prompt=system_prompt,
                user_prompt=correction_prompt,
                temperature=0,
                max_tokens=800,
            )
            if statistical_visual:
                essay = _round_essay_data_values(essay, value_precision)
            fact_attempts = 2
            contradictions = find_table_fact_contradictions(normalized_deplot, essay)
            if contradictions:
                repaired_essay = soften_false_monotonic_claims(normalized_deplot, essay)
                repaired_essay = correct_false_spread_direction_claims(
                    normalized_deplot,
                    repaired_essay,
                )
                repaired_contradictions = find_table_fact_contradictions(
                    normalized_deplot,
                    repaired_essay,
                )
                if repaired_essay != essay and not repaired_contradictions:
                    essay = repaired_essay
                    contradictions = []
                else:
                    return SampleEssayResponse(
                        success=False,
                        error=(
                            "DeepSeek generated a sample essay that still contradicts the extracted "
                            "chart after one automatic rewrite: " + " ".join(contradictions)
                        ),
                        debug={"model": model, "fact_validation_attempts": fact_attempts},
                    )
    except Exception as e:
        print(f"DeepSeek sample essay generation failed with model {model}: {e}")
        return SampleEssayResponse(
            success=False,
            error=f"DeepSeek sample essay generation failed with model {model}: {e}",
            debug={"model": model, "error_type": e.__class__.__name__},
        )

    word_count = len(essay.split())
    if word_count == 0:
        return SampleEssayResponse(
            success=False,
            error=(
                f"DeepSeek returned an empty essay with model {model}. "
                "The request reached the model, but no final answer content was produced. "
                "Please try again, or set DEEPSEEK_THINKING=disabled and restart the backend."
            ),
            debug={"model": model, "words": 0},
        )

    if word_count < (req.min_words or 150):
        essay += f"\n\n(Note: Model returned only {word_count} words; please extend to meet the minimum word requirement.)"

    return SampleEssayResponse(
        success=True,
        essay=essay,
        debug={
            "model": model,
            "words": word_count,
            "fact_validation_attempts": fact_attempts,
            "structure": "standard-ielts-task-1",
        },
    )


def generate_sample_essay(req: SampleEssayRequest):
    """Generate an essay without an HTTP context (kept for tests and internal callers)."""
    return _generate_sample_essay(req)


@router.post("/api/generate-sample-essay", response_model=SampleEssayResponse)
def generate_sample_essay_route(request: Request, req: SampleEssayRequest):
    from research_api import record_server_event_for_request

    result = generate_sample_essay(req)
    record_server_event_for_request(
        request,
        "sample_essay_completed" if result.success else "sample_essay_failed",
        payload={"request": req.model_dump(), "response": result.model_dump()},
    )
    return result
