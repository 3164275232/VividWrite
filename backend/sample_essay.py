from fastapi import APIRouter
from pydantic import BaseModel
import os
import re
from typing import Optional, Dict, Any
from next_sentence import summarize_flowchart
from deepseek_config import get_deepseek_api_key, get_deepseek_client, get_deepseek_extra_body, get_deepseek_model
from structure_feedback_agents import (
    OPTION_C_LABELS,
    OPTION_C_NODE_TYPES,
    REQUIRED_OPTION_C_NODE_TYPES,
    normalize_node_type,
)
from chart_text import (
    CHART_TYPE_LABELS,
    InvalidExtractedChartData,
    build_table_fact_checks,
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
    flowchart: dict | None = None  # {nodes:[], edges:[]}
    requirement: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 0.2
    min_words: Optional[int] = 150
    use_standard_structure: Optional[bool] = None  # True: use standard structure, False: use flowchart as-is, None: prompt user
    chart_type: Optional[str] = None

class SampleEssayResponse(BaseModel):
    success: bool
    essay: Optional[str] = None
    error: Optional[str] = None
    debug: Optional[Dict[str, Any]] = None
    requires_choice: Optional[bool] = None  # True when user needs to make a structure choice
    choice_info: Optional[Dict[str, Any]] = None  # Information for the choice dialog

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


@router.post("/api/generate-sample-essay", response_model=SampleEssayResponse)
def generate_sample_essay(req: SampleEssayRequest):
    """Generate a full IELTS Task 1 sample essay (>=150 words) based on DePlot data + flowchart."""
    if not get_deepseek_api_key():
        return SampleEssayResponse(success=False, error="DEEPSEEK_API_KEY not configured")
    if not req.deplot_text or not req.deplot_text.strip():
        return SampleEssayResponse(success=False, error="deplot_text required")
    
    # Check Option C flowchart structure completeness. Optional Commentary is
    # deliberately excluded from the required set.
    if req.flowchart and req.flowchart.get("nodes"):
        nodes = req.flowchart.get("nodes", [])
        normalized_node_types = [
            normalize_node_type(node.get("type")) for node in nodes
        ]
        structure_presence = {
            node_type: node_type in normalized_node_types
            for node_type in OPTION_C_NODE_TYPES
        }
        missing_node_types = [
            node_type
            for node_type in REQUIRED_OPTION_C_NODE_TYPES
            if not structure_presence[node_type]
        ]
        missing_structures = [
            OPTION_C_LABELS[node_type] for node_type in missing_node_types
        ]
        
        if missing_structures and req.use_standard_structure is None:
            # Return choice dialog information instead of error
            return SampleEssayResponse(
                success=False,
                requires_choice=True,
                choice_info={
                    "title": "Flowchart Structure Analysis",
                    "missing_structures": missing_structures,
                    "options": [
                        {
                            "id": "flowchart",
                            "title": "Continue with current flowchart structure",
                            "description": "Use your flowchart as-is (may result in incomplete essay)",
                            "value": False
                        },
                        {
                            "id": "standard",
                            "title": "Use standard IELTS structure",
                            "description": "Introduction -> Overview -> Key Details A -> Key Details B (complete essay)",
                            "value": True
                        }
                    ],
                    "message": f"Your flowchart is missing: {', '.join(missing_structures)}. Choose how to proceed:"
                }
            )
        
        structure_status = [
            OPTION_C_LABELS[node_type]
            for node_type in OPTION_C_NODE_TYPES
            if structure_presence[node_type]
        ]
        print(f"Flowchart structure confirmed: {' | '.join(structure_status)}")
    else:
        return SampleEssayResponse(
            success=False, 
            error="No flowchart provided. Please create a flowchart structure before generating the sample essay."
        )

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
    flow_summary = summarize_flowchart(req.flowchart)
    requirement = req.requirement or (
        "Write a descriptive academic report of at least 150 words, such as IELTS "
        "Task 1, summarizing the main features and making relevant comparisons."
    )
    
    nodes = req.flowchart.get("nodes", []) if req.flowchart else []
    flowchart_types = [
        normalize_node_type(node.get("type")) for node in nodes
    ]
    selected_types = (
        list(REQUIRED_OPTION_C_NODE_TYPES)
        if req.use_standard_structure
        else list(dict.fromkeys(flowchart_types))
    )
    structure_parts = [
        OPTION_C_LABELS[node_type]
        for node_type in OPTION_C_NODE_TYPES
        if node_type in selected_types
    ]
    structure_guidance = (
        "Use the standard Option C IELTS Task 1 structure: "
        "Introduction -> Overview -> Key Details A -> Key Details B. "
        if req.use_standard_structure
        else f"Follow only this flowchart structure: {' -> '.join(structure_parts)}. "
    )
    if "optional_commentary" in selected_types:
        structure_guidance += (
            "Optional Commentary may be included only when the task or visual supports "
            "the interpretation. It must not invent causes or unsupported conclusions. "
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
    if not req.use_standard_structure:
        system_prompt += (
            " Include only functions represented by the current flowchart. "
            "Do not silently add a missing structural section."
        )

    common_prompt = (
        f"OFFICIAL REQUIREMENT:\n{requirement}\n\n"
        f"ORIGINAL VISUAL TYPE:\n{visual_label}\n\n"
        f"CHART TEXTUAL DATA (primary facts, may contain minor OCR noise):\n"
        f"{normalized_deplot}\n\n"
        f"DETERMINISTIC COMPARISON CHECKS (must not be contradicted):\n"
        f"{fact_check_block}\n\n"
    )
    if req.use_standard_structure:
        user_prompt = (
            common_prompt
            + "TASK: Write the full report using Introduction, Overview, Key Details A, "
            f"and Key Details B. Minimum {req.min_words or 150} words. "
            "Do not add a separate conclusion, headings, or meta explanation. "
            "Return only the raw essay text."
        )
    else:
        user_prompt = (
            common_prompt
            + f"FLOWCHART STRUCTURE:\n{flow_summary}\n\n"
            + "TASK: Write the full report following the current flowchart exactly. "
            + f"Minimum {req.min_words or 150} words. "
            + "Do not add functions absent from the flowchart. Do not add a separate "
            + "conclusion, headings, or meta explanation. Return only the raw essay text."
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
            "flowchart_used": bool(flow_summary),
            "structure_check": {
                **structure_presence,
                "required_nodes": list(REQUIRED_OPTION_C_NODE_TYPES),
                "optional_nodes": ["optional_commentary"],
                "all_required_present": not missing_node_types,
            },
            "user_choice": {
                "use_standard_structure": req.use_standard_structure,
                "missing_structures": missing_structures,
            },
            "flowchart_node_types": flowchart_types,
        },
    )
