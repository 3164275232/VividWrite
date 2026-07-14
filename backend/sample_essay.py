from fastapi import APIRouter
from pydantic import BaseModel
import os
from typing import Optional, Dict, Any
from next_sentence import summarize_flowchart
from deepseek_config import get_deepseek_api_key, get_deepseek_client, get_deepseek_extra_body, get_deepseek_model
from chart_text import InvalidExtractedChartData, parse_validated_pie_table

router = APIRouter()

class SampleEssayRequest(BaseModel):
    deplot_text: str
    flowchart: dict | None = None  # {nodes:[], edges:[]}
    requirement: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 0.6
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
    
    # Check flowchart structure completeness
    if req.flowchart and req.flowchart.get("nodes"):
        nodes = req.flowchart.get("nodes", [])
        node_types = [node.get("type") for node in nodes]
        
        # Check for key structures
        has_background = "background" in node_types
        has_presentation = "presentation" in node_types
        has_comment = "comment" in node_types
        
        # Build structure report
        missing_structures = []
        if not has_background:
            missing_structures.append("Background")
        if not has_presentation:
            missing_structures.append("Presentation of Visuals")
        if not has_comment:
            missing_structures.append("Comment on Result")
        
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
                            "description": "Background → Presentation → Comment (complete essay)",
                            "value": True
                        }
                    ],
                    "message": f"Your flowchart is missing: {', '.join(missing_structures)}. Choose how to proceed:"
                }
            )
        
        # Structure confirmation message
        structure_status = []
        if has_background:
            structure_status.append("OK Background")
        if has_presentation:
            structure_status.append("OK Presentation of Visuals")
        if has_comment:
            structure_status.append("OK Comment on Result")
        
        print(f"Flowchart structure confirmed: {' | '.join(structure_status)}")
    else:
        return SampleEssayResponse(
            success=False, 
            error="No flowchart provided. Please create a flowchart structure before generating the sample essay."
        )

    normalized_deplot = (req.deplot_text or '').replace('<0x0A>', '\n')[:8000]
    is_pie_chart = req.chart_type == "pie" or "CHART TYPE | Pie chart" in normalized_deplot
    if is_pie_chart:
        try:
            parse_validated_pie_table(normalized_deplot)
        except InvalidExtractedChartData as exc:
            return SampleEssayResponse(
                success=False,
                error=(
                    f"Pie chart data extraction is inconsistent: {exc} "
                    "Please upload the image again so DePlot can re-extract the isolated pie plot."
                ),
            )
    flow_summary = summarize_flowchart(req.flowchart)
    requirement = req.requirement or (
        "Write an descriptive academic report (at least 150 words， such as IELTS Task 1) summarizing the main features and making relevant comparisons."
    )
    
    # Determine structure based on user choice
    if req.use_standard_structure:
        # Use standard IELTS structure regardless of flowchart
        structure_guidance = "Structure your essay to follow the standard IELTS Task 1 format: Background → Presentation of Visual (core) → Comment on Result (final). "
        essay_structure = "Structure your essay as: Background → Presentation of Visual (with appropriate sub-option) → Comment on Result. "
        print("Using standard IELTS structure as requested by user")
    else:
        # Use flowchart structure as-is
        nodes = req.flowchart.get("nodes", []) if req.flowchart else []
        node_types = [node.get("type") for node in nodes]
        
        # Detect main structure components
        has_background = "background" in node_types
        has_presentation = "presentation" in node_types
        has_comment = "comment" in node_types
        
        # Detect presentation sub-options
        presentation_subtypes = []
        for node in nodes:
            if node.get("type") in ["summary", "results", "reference_explanation"]:
                presentation_subtypes.append(node.get("type"))
        
        # Build structure guidance based on actual flowchart content
        structure_parts = []
        if has_background:
            structure_parts.append("Background")
        if has_presentation:
            structure_parts.append("Presentation of Visual (core)")
        if has_comment:
            structure_parts.append("Comment on Result (final)")
        
        structure_guidance = f"Structure your essay to follow the flowchart plan: {' → '.join(structure_parts)}. "
        
        # Build essay structure with specific sub-options
        essay_parts = []
        if has_background:
            essay_parts.append("Background")
        if has_presentation:
            essay_parts.append("Presentation of Visual")
        if has_comment:
            essay_parts.append("Comment on Result")
        
        essay_structure = f"Structure your essay as: {' → '.join(essay_parts)}. "
        
        # Add specific guidance for presentation sub-options
        if presentation_subtypes:
            sub_options_text = []
            if "summary" in presentation_subtypes:
                sub_options_text.append("Summary")
            if "results" in presentation_subtypes:
                sub_options_text.append("Results")
            if "reference_explanation" in presentation_subtypes:
                sub_options_text.append("Reference & Explanation")
            
            essay_structure += f" For Presentation of Visual, include these sub-options: {', '.join(sub_options_text)}. "
        
        print(f"Using flowchart structure as-is:")
        print(f"  - Background: {has_background}")
        print(f"  - Presentation: {has_presentation}")
        print(f"  - Comment: {has_comment}")
        print(f"  - Presentation sub-options: {presentation_subtypes}")
        print(f"  - Structure: {' -> '.join(structure_parts)}")
    
    if req.use_standard_structure:
        system_prompt = (
            "You are an expert of descriptive academic writing, such as IELTS Task 1, data commentary. Produce a high-quality sample response. "
            "Neutral objective tone; no bullet points; no first-person; no speculative data beyond given facts. "
            "The chart table is the factual source of truth. Preserve every category-value pairing exactly, and silently verify all numeric claims before answering. "
            "Do not infer causes, motives, priorities, perceptions, or whether a cost is fixed or discretionary unless the chart explicitly states them. "
            f"{structure_guidance}"
            "For Presentation of Visual, choose appropriate sub-options (Summary, Results, or Reference & Explanation) based on the data type and requirements. "
            "Use the standard IELTS Task 1 structure regardless of the flowchart provided."
        )
    else:
        system_prompt = (
            "You are an expert of descriptive academic writing, such as IELTS Task 1, data commentary. Produce a high-quality sample response. "
            "Neutral objective tone; no bullet points; no first-person; no speculative data beyond given facts. "
            "The chart table is the factual source of truth. Preserve every category-value pairing exactly, and silently verify all numeric claims before answering. "
            "Do not infer causes, motives, priorities, perceptions, or whether a cost is fixed or discretionary unless the chart explicitly states them. "
            f"{structure_guidance}"
            "For Presentation of Visual, choose appropriate sub-options (Summary, Results, or Reference & Explanation) based on the data type and requirements. "
            "CRITICAL RESTRICTION: You MUST ONLY include sections that are explicitly present in the flowchart structure. "
            "DO NOT add Background if it's not in the flowchart. DO NOT add Comment if it's not in the flowchart. "
            "ONLY write content for the sections that exist in the flowchart structure provided. "
            "If the flowchart only contains 'Presentation of Visual', write ONLY presentation content. "
            "If the flowchart contains 'Presentation of Visual' and 'Comment on Result', write ONLY those two sections. "
            "NEVER add sections that are not explicitly listed in the flowchart structure."
        )
        
        # Add specific guidance for presentation sub-options if detected
        if presentation_subtypes:
            sub_options_guidance = f"IMPORTANT: The flowchart contains these Presentation sub-options: {', '.join(presentation_subtypes)}. You MUST include content for ALL of these sub-options in your essay. "
            system_prompt += sub_options_guidance
    # essay_structure is now defined above based on user choice
    
    if req.use_standard_structure:
        user_prompt = (
            f"OFFICIAL REQUIREMENT:\n{requirement}\n\n"
            f"CHART TEXTUAL DATA (primary facts, may contain minor OCR noise):\n{normalized_deplot}\n\n"
            f"TASK: Write the full report using the standard Background → Presentation → Comment structure. Minimum {req.min_words or 150} words. "
            f"{essay_structure}"
            "Do NOT include any meta explanations or headings. Return ONLY the raw essay text."
        )
    else:
        user_prompt = (
            f"OFFICIAL REQUIREMENT:\n{requirement}\n\n"
            f"CHART TEXTUAL DATA (primary facts, may contain minor OCR noise):\n{normalized_deplot}\n\n"
            f"FLOWCHART STRUCTURE (writer plan - follow this structure EXACTLY):\n{flow_summary}\n\n"
            f"TASK: Write the full report following the flowchart structure EXACTLY. Minimum {req.min_words or 150} words. "
            f"{essay_structure}\n\n"
            "CRITICAL RESTRICTIONS:\n"
            "1. ONLY include sections that are explicitly listed in the flowchart structure above.\n"
            "2. DO NOT add Background section if it's not in the flowchart.\n"
            "3. DO NOT add Comment section if it's not in the flowchart.\n"
            "4. DO NOT add any sections not specified in the flowchart.\n"
            "5. If flowchart only has Presentation, write ONLY presentation content.\n"
            "6. If flowchart has Presentation + Comment, write ONLY those two sections.\n"
            "7. Do NOT include any meta explanations or headings. Return ONLY the raw essay text."
        )
        
        # Add specific guidance for presentation sub-options if detected
        if presentation_subtypes:
            sub_options_restrictions = f"\n\nPRESENTATION SUB-OPTIONS REQUIREMENTS:\n"
            sub_options_restrictions += f"The flowchart contains these Presentation sub-options: {', '.join(presentation_subtypes)}.\n"
            sub_options_restrictions += f"You MUST include content for ALL of these sub-options in your essay.\n"
            if "summary" in presentation_subtypes:
                sub_options_restrictions += "- Include Summary: overview statements and general trends.\n"
            if "results" in presentation_subtypes:
                sub_options_restrictions += "- Include Results: specific data presentation and numerical comparisons.\n"
            if "reference_explanation" in presentation_subtypes:
                sub_options_restrictions += "- Include Reference & Explanation: detailed analysis, comparisons, and trend explanations.\n"
            
            user_prompt += sub_options_restrictions

    client = get_deepseek_client()
    model = get_deepseek_model(req.model)
    try:
        essay = _generate_essay_text(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=req.temperature if req.temperature is not None else 0.6,
            max_tokens=800,
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
            "flowchart_used": bool(flow_summary),
            "has_background": has_background,
            "structure_check": {
                "background": has_background,
                "presentation": has_presentation,
                "comment": has_comment,
                "all_required_present": len(missing_structures) == 0
            },
            "user_choice": {
                "use_standard_structure": req.use_standard_structure,
                "missing_structures": missing_structures if 'missing_structures' in locals() else []
            }
        },
    )
