"""Next sentence generation module (LLM-only, chat messages version).

Always uses DeepSeek chat messages to produce ONE next sentence.
Requires DEEPSEEK_API_KEY in environment (.env supported).
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import re
from dotenv import load_dotenv
from deepseek_config import get_deepseek_client, get_deepseek_extra_body, get_deepseek_model

load_dotenv()

class NextSentenceRequest(BaseModel):
    current_text: str
    deplot_text: str  # REQUIRED textual extraction from chart (model generated)
    flowchart: Optional[dict] = None  # {nodes:[], edges:[]}
    initial_instruction: Optional[str] = "Assist Descriptive academic writing, Data Commentary, IELTS Writing Task 1 writing"
    requirement: Optional[str] = None
    candidate_count: int = 3  # number of alternative next sentences wanted
    max_tokens: Optional[int] = 180  # allow enough tokens for multiple short sentences
    model: Optional[str] = None
    temperature: Optional[float] = 0.7

class NextSentenceResponse(BaseModel):
    next_sentence: Optional[str] = None  # first candidate for backward compat
    candidates: Optional[List[str]] = None
    debug: Optional[dict] = None
    error: Optional[str] = None

# ---- Flowchart summarizer ----

def summarize_flowchart(flowchart: Optional[dict]) -> str:
    if not flowchart or not isinstance(flowchart, dict):
        return ""
    nodes: List[dict] = flowchart.get("nodes", [])
    if not nodes:
        return ""
    groups: Dict[str, List[str]] = {}
    for n in nodes:
        t = n.get("type", "unknown")
        title = (n.get("title") or n.get("id") or "Untitled").strip()
        groups.setdefault(t, []).append(title[:60])
    
    parts = []
    # Updated order for DATA COMMENTARY MOVE structure
    order = ["background", "presentation", "summary", "results", "reference_explanation", "comment"]
    
    # Process main stages first
    for t in order:
        if t in groups:
            if t == "background":
                label = "Background"
            elif t == "presentation":
                label = "Presentation of Visual (Core)"
            elif t == "comment":
                label = "Comment on Result (Final)"
            elif t == "summary":
                label = "Summary Option"
            elif t == "results":
                label = "Results Option"
            elif t == "reference_explanation":
                label = "Reference & Explanation Option"
            else:
                label = t.capitalize()
            parts.append(f"{label}: " + "; ".join(groups[t]))
    
    # Process any remaining node types not in the main order
    for t, titles in groups.items():
        if t not in order:
            parts.append(f"{t.capitalize()}: " + "; ".join(titles))
    
    return " | ".join(parts)

# ---- Build messages ----

def _build_messages(req: NextSentenceRequest) -> List[Dict[str, str]]:
    """Construct a FIXED template messages list.

    All segments are ALWAYS present (hard‑coded labels) regardless of emptiness.
    No conditional logic about presence of initial_instruction / requirement / flowchart.
    This ensures deterministic prompt shape for every call.
    """
    flow_summary = summarize_flowchart(req.flowchart)

    # Always use the same system instructions (deterministic, explicit rules)
    system_content = (
        "ROLE: You are a specialized assistant for Descriptive academic writing, Data Commentary, IELTS Writing Task 1 writing.\n"
        "GOAL: Propose several high-quality alternative NEXT SENTENCE candidates (each a single sentence) that logically follow the existing text.\n\n"
        "PRIORITIZATION WEIGHTS (High -> Low):\n"
        "1. CHART DATA (deplot_text) factual content and trends.\n"
        "2. EXISTING TEXT progression (avoid repetition, ensure logical follow-on).\n"
        "3. FLOWCHART structural intent (light guidance only; do not force if unnatural).\n\n"
        "STRICT RULES FOR EACH CANDIDATE:\n"
        "- Single sentence only (no conjunction chaining with semicolons).\n"
        "- Max 30 words.\n"
        "- Neutral, objective academic tone.\n"
        "- No meta commentary or quotes.\n"
        "- Use numbers ONLY if clearly present in chart data; otherwise use qualitative/comparative phrasing.\n"
        "- Vary openings among candidates.\n"
        "- Avoid repeating the immediately previous sentence content.\n"
        "- If overview just finished, begin detailing a salient comparison or trend; if mid-body, continue consistent detail; if approaching conclusion, start synthesizing.\n"
        "OUTPUT FORMAT: Return ONLY valid JSON in this exact format: {\"candidates\": [\"sentence1\", \"sentence2\", \"sentence3\"]}\n"
        "CRITICAL: Do not include any other text, explanations, or formatting. Only the JSON object.\n"
    )

    # Hard-coded block labels. Empty values become empty after the colon.
    initial_instruction = req.initial_instruction or ""
    requirement = req.requirement or ""

    # Normalize deplot textual data (replace <0x0A> tokens with newlines for model readability)
    raw_deplot = req.deplot_text or ""
    normalized_deplot = raw_deplot.replace('<0x0A>', '\n')[:6000]  # allow a bit more context

    user_content = (
        f"TASK CONTEXT:\n{initial_instruction}\n\n"
        f"OFFICIAL REQUIREMENT:\n{requirement}\n\n"
        f"EXISTING TEXT (do NOT rewrite it, only continue):\n{req.current_text.strip()}\n\n"
        f"STRUCTURE SUMMARY (flowchart-derived; may be empty):\n{flow_summary}\n\n"
        f"CHART DATA (Primary factual source – may contain minor OCR noise):\n{normalized_deplot}\n\n"
        f"REQUEST: Provide {req.candidate_count} alternative next-sentence candidates strictly following the rules.\n"
        f"OUTPUT ONLY: {{\"candidates\": [\"sentence1\", \"sentence2\", \"sentence3\"]}}\n"
        f"NO OTHER TEXT. NO EXPLANATIONS. NO MARKDOWN. ONLY THE JSON OBJECT."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

# ---- Chat completion call ----

def _call_chat(messages: List[Dict[str, str]], model: str, temperature: float, max_tokens: int) -> str:
    client = get_deepseek_client()
    chat = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        extra_body=get_deepseek_extra_body(),
    )
    content = chat.choices[0].message.content if chat.choices else ""
    return content or "(No content returned)"

# ---- Public API ----

def generate_next_sentence(req: NextSentenceRequest) -> NextSentenceResponse:
    if not req.current_text or not req.current_text.strip():
        return NextSentenceResponse(error="current_text is empty")
    if not req.deplot_text or not req.deplot_text.strip():
        return NextSentenceResponse(error="deplot_text is required")
    # sanitize candidate_count
    if req.candidate_count < 1:
        req.candidate_count = 1
    if req.candidate_count > 6:
        req.candidate_count = 6
    try:
        messages = _build_messages(req)
        raw = _call_chat(
            messages=messages,
            model=get_deepseek_model(req.model),
            temperature=req.temperature if req.temperature is not None else 0.7,
            max_tokens=req.max_tokens or 48,
        )
        # Try parse JSON of candidates
        candidates: List[str] = []
        import json as _json
        parsed_mode = "json"
        print(f"DEBUG: Raw AI response: {repr(raw)}")  # Debug log
        try:
            data = _json.loads(raw)
            print(f"DEBUG: Parsed JSON: {data}")  # Debug log
            if isinstance(data, dict) and isinstance(data.get("candidates"), list):
                candidates = [str(s).strip() for s in data["candidates"] if isinstance(s, str)]
                print(f"DEBUG: Extracted candidates: {candidates}")  # Debug log
        except Exception as e:
            print(f"DEBUG: JSON parse failed: {e}")  # Debug log
            parsed_mode = "fallback-split"
            # Fallback: split raw by newlines -> sentences
            parts = [p.strip() for p in re.split(r'[\n\r]+', raw) if p.strip()]
            print(f"DEBUG: Fallback parts: {parts}")  # Debug log
            for p in parts:
                # take only first sentence fragment of each line
                first = re.split(r'(?<=[.!?])\s+', p)[0].strip()
                if first:
                    candidates.append(first)
            print(f"DEBUG: Fallback candidates: {candidates}")  # Debug log
        if not candidates:
            parsed_mode = "empty"
            # Provide some fallback candidates for testing
            candidates = [
                "The chart shows significant changes over the period.",
                "There are notable differences between the categories.",
                "The data reveals important trends in the analysis."
            ]
        # ensure single sentence constraint & length filter
        cleaned = []
        for c in candidates:
            # remove excessive interior newlines
            c1 = c.replace('\n', ' ').strip()
            # Hard trim to ~30 words (soft enforcement)
            words = c1.split()
            if len(words) > 30:
                c1 = " ".join(words[:30])
            # Keep as-is; could also enforce terminal period if missing
            cleaned.append(c1)
        candidates = cleaned[:req.candidate_count]
        primary = candidates[0] if candidates else None
        debug = {
            "mode": "llm-chat",
            "messages_count": len(messages),
            "model": get_deepseek_model(req.model),
            "temperature": req.temperature if req.temperature is not None else 0.7,
            "max_tokens": req.max_tokens or 48,
            "first_user_chars": len(messages[1]['content']) if len(messages) > 1 else 0,
            "flowchart_used": bool(summarize_flowchart(req.flowchart)),
            "deterministic_template": True,
            "flow_summary_length": len(summarize_flowchart(req.flowchart)),
            "candidate_count_returned": len(candidates),
            "parse_mode": parsed_mode,
        }
        return NextSentenceResponse(next_sentence=primary, candidates=candidates, debug=debug)
    except Exception as e:
        return NextSentenceResponse(error=str(e), debug={
            "mode": "llm-chat",
            "error_type": e.__class__.__name__,
        })
