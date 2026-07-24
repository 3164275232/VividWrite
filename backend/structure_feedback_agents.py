"""Multi-agent structure feedback for IELTS Academic Writing Task 1.

The agents in this module have separate roles, prompts, typed inputs, typed
outputs, and ``run`` methods. The orchestrator keeps the public response stable
while providing deterministic Option C fallbacks when an LLM is unavailable or
returns invalid JSON.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Type

from fastapi import APIRouter
from pydantic import BaseModel, Field

from deepseek_config import (
    get_deepseek_api_key,
    get_deepseek_client,
    get_deepseek_extra_body,
    get_deepseek_model,
)


router = APIRouter()

OPTION_C_NODE_TYPES = [
    "introduction",
    "overview",
    "key_details_a",
    "key_details_b",
    "optional_commentary",
]
REQUIRED_OPTION_C_NODE_TYPES = OPTION_C_NODE_TYPES[:4]
OPTION_C_LABELS = {
    "introduction": "Introduction / Orient the Visual",
    "overview": "Overview / Highlight Key Patterns",
    "key_details_a": "Key Details A / Report & Compare",
    "key_details_b": "Key Details B / Report & Compare",
    "optional_commentary": "Optional Commentary / Interpret",
}
OPTION_C_FUNCTIONS = {
    "introduction": "Paraphrase the task and identify what the visual presents.",
    "overview": "Summarize the most important trends, contrasts, or overall features.",
    "key_details_a": "Report and compare the first logically grouped set of data.",
    "key_details_b": "Report and compare the second logically grouped set of data.",
    "optional_commentary": (
        "Interpret only when supported by the task or visual; never invent causes "
        "or unsupported conclusions."
    ),
}
LEGACY_NODE_ALIASES = {
    "background": "introduction",
    "presentation": "key_details_a",
    "summary": "overview",
    "results": "key_details_a",
    "reference_explanation": "key_details_b",
    "comment": "optional_commentary",
}


def normalize_node_type(node_type: Optional[str]) -> str:
    value = str(node_type or "custom").strip().casefold().replace("-", "_").replace(" ", "_")
    return LEGACY_NODE_ALIASES.get(value, value or "custom")


class StructureAnalysisRequest(BaseModel):
    current_text: str
    flowchart: Optional[dict] = None
    deplot_text: Optional[str] = None
    chart_type: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 1200


class SentenceInfo(BaseModel):
    index: int
    start: int
    end: int
    text: str
    paragraph_index: int


class ParagraphInfo(BaseModel):
    paragraph_index: int
    start: int
    end: int
    text: str
    sentence_indices: List[int] = Field(default_factory=list)


class NodeInfo(BaseModel):
    id: str
    type: str
    title: Optional[str] = None
    original_type: Optional[str] = None
    optional: bool = False


class SentenceNodeMapping(BaseModel):
    sentence_index: int
    primary_node: Optional[str] = None
    node_ids: List[str] = Field(default_factory=list)
    scores: Dict[str, float] = Field(default_factory=dict)
    secondary_moves: List[str] = Field(default_factory=list)


class ParagraphMapping(BaseModel):
    paragraph_index: int
    start: int
    end: int
    primary_node: Optional[str] = None
    secondary_moves: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    sentence_indices: List[int] = Field(default_factory=list)


class MissingNodeInfo(BaseModel):
    id: str
    title: Optional[str] = None
    reason: Optional[str] = None
    required: bool = True


class TaskUnderstandingInput(BaseModel):
    current_text: str
    deplot_text: Optional[str] = None
    chart_type: Optional[str] = None


class TaskUnderstandingResult(BaseModel):
    task_type: str
    writing_goal: str
    expected_structure: List[str]
    chart_evidence_summary: str


class ParagraphFunctionAssessment(BaseModel):
    paragraph_index: int
    primary_function: str
    confidence: float
    function_clear: bool


class IELTSStructureInput(BaseModel):
    paragraphs: List[ParagraphInfo]
    sentences: List[SentenceInfo]
    task: TaskUnderstandingResult


class IELTSStructureResult(BaseModel):
    presence: Dict[str, bool]
    order_reasonable: bool
    order_issues: List[str] = Field(default_factory=list)
    paragraph_functions: List[ParagraphFunctionAssessment] = Field(default_factory=list)
    missing_required_nodes: List[str] = Field(default_factory=list)


class RhetoricalMoveAssessment(BaseModel):
    move: str
    present: bool
    paragraph_indices: List[int] = Field(default_factory=list)
    sentence_indices: List[int] = Field(default_factory=list)
    evidence_summary: str = ""


class DataCommentaryInput(BaseModel):
    paragraphs: List[ParagraphInfo]
    sentences: List[SentenceInfo]
    task: TaskUnderstandingResult


class DataCommentaryResult(BaseModel):
    moves: List[RhetoricalMoveAssessment] = Field(default_factory=list)
    unsupported_interpretation_warning: Optional[str] = None


class SentenceMappingInput(BaseModel):
    paragraphs: List[ParagraphInfo]
    sentences: List[SentenceInfo]
    nodes: List[NodeInfo]
    ielts_structure: IELTSStructureResult
    commentary: DataCommentaryResult


class SentenceMappingResult(BaseModel):
    paragraph_mappings: List[ParagraphMapping] = Field(default_factory=list)
    sentence_mappings: List[SentenceNodeMapping] = Field(default_factory=list)


class FeedbackIntegrationInput(BaseModel):
    task: TaskUnderstandingResult
    ielts_structure: IELTSStructureResult
    commentary: DataCommentaryResult
    mapping: SentenceMappingResult


class FeedbackIntegrationResult(BaseModel):
    overall_status: str
    is_complete: bool
    summary: str
    missing_nodes: List[str] = Field(default_factory=list)
    order_issues: List[str] = Field(default_factory=list)
    paragraph_correspondence: List[ParagraphMapping] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class AgentTraceEntry(BaseModel):
    agent_name: str
    status: str
    result_summary: Dict[str, Any] = Field(default_factory=dict)


class StructureAnalysisResponse(BaseModel):
    sentences: List[SentenceInfo] = Field(default_factory=list)
    nodes: List[NodeInfo] = Field(default_factory=list)
    mappings: List[SentenceNodeMapping] = Field(default_factory=list)
    missing_nodes: List[MissingNodeInfo] = Field(default_factory=list)
    paragraphs: List[ParagraphInfo] = Field(default_factory=list)
    paragraph_mappings: List[ParagraphMapping] = Field(default_factory=list)
    structure_feedback: Optional[FeedbackIntegrationResult] = None
    agent_trace: List[AgentTraceEntry] = Field(default_factory=list)
    error: Optional[str] = None
    debug: Optional[dict] = None


LLMCaller = Callable[[List[Dict[str, str]], str, float, int], str]


def _deepseek_llm_caller(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    client = get_deepseek_client()
    chat = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body=get_deepseek_extra_body(),
    )
    if not chat.choices:
        return ""
    return getattr(chat.choices[0].message, "content", "") or ""


def _extract_json(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    first = text.find("{")
    last = text.rfind("}")
    if first < 0 or last <= first:
        raise ValueError("Agent response did not contain a JSON object")
    value = json.loads(text[first : last + 1])
    if not isinstance(value, dict):
        raise ValueError("Agent response JSON must be an object")
    return value


class BaseStructureAgent:
    name = "BaseStructureAgent"
    role_prompt = ""
    output_model: Type[BaseModel]

    def __init__(
        self,
        llm_caller: Optional[LLMCaller],
        model: str,
        temperature: float,
        max_tokens: int,
    ):
        self.llm_caller = llm_caller
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def build_user_prompt(self, agent_input: BaseModel) -> str:
        return (
            "INPUT_JSON:\n"
            f"{agent_input.model_dump_json()}\n\n"
            "OUTPUT_JSON_SCHEMA:\n"
            f"{json.dumps(self.output_model.model_json_schema())}\n\n"
            "Return only one JSON object matching the schema. Do not provide hidden "
            "reasoning, chain-of-thought, markdown, or prose outside the JSON."
        )

    def run(self, agent_input: BaseModel) -> BaseModel:
        if self.llm_caller is None:
            raise RuntimeError("No LLM caller is configured")
        messages = [
            {"role": "system", "content": self.role_prompt},
            {"role": "user", "content": self.build_user_prompt(agent_input)},
        ]
        raw = self.llm_caller(
            messages,
            self.model,
            self.temperature,
            self.max_tokens,
        )
        return self.output_model.model_validate(_extract_json(raw))

    def fallback(self, agent_input: BaseModel) -> BaseModel:
        raise NotImplementedError


class TaskUnderstandingAgent(BaseStructureAgent):
    name = "TaskUnderstandingAgent"
    output_model = TaskUnderstandingResult
    role_prompt = (
        "You identify the IELTS Academic Writing Task 1 visual type, the objective "
        "writing goal, and the expected Option C structure. Use chart_type and "
        "DePlot text as evidence. Do not assess the student's quality."
    )

    def fallback(self, agent_input: TaskUnderstandingInput) -> TaskUnderstandingResult:
        source = f"{agent_input.chart_type or ''} {agent_input.deplot_text or ''}".casefold()
        chart_type = (agent_input.chart_type or "").strip().casefold()
        if not chart_type or chart_type == "auto":
            for candidate in ("line", "bar", "pie", "table", "process", "map"):
                if candidate in source:
                    chart_type = candidate
                    break
        chart_type = chart_type or "unspecified_visual"
        return TaskUnderstandingResult(
            task_type=chart_type,
            writing_goal=(
                "Objectively summarize the visual's main features and report relevant "
                "comparisons without unsupported causes or opinions."
            ),
            expected_structure=list(OPTION_C_NODE_TYPES),
            chart_evidence_summary=(
                f"Task treated as {chart_type}; DePlot context was "
                f"{'available' if (agent_input.deplot_text or '').strip() else 'not available'}."
            ),
        )


ORIENT_TERMS = (
    "chart",
    "graph",
    "table",
    "diagram",
    "map",
    "process",
    "figure",
    "illustrates",
    "shows",
    "depicts",
    "presents",
    "compares",
)
OVERVIEW_TERMS = (
    "overall",
    "in general",
    "generally",
    "it is clear",
    "it is apparent",
    "the main feature",
    "the most noticeable",
    "on the whole",
)
COMPARISON_TERMS = (
    "higher",
    "lower",
    "more than",
    "less than",
    "compared",
    "whereas",
    "while",
    "respectively",
    "similar",
    "difference",
    "exceeded",
)
TREND_TERMS = (
    "increase",
    "increased",
    "rise",
    "rose",
    "grow",
    "grew",
    "decrease",
    "decreased",
    "fall",
    "fell",
    "decline",
    "declined",
    "stable",
    "fluctuat",
    "peak",
    "highest",
    "lowest",
)
INTERPRETATION_TERMS = (
    "because",
    "due to",
    "as a result",
    "this suggests",
    "this implies",
    "may reflect",
    "can be attributed",
    "the reason",
)


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(term in lowered for term in terms)


def _detect_moves(text: str) -> List[str]:
    moves: List[str] = []
    lowered = text.casefold()
    if _has_any(lowered, ORIENT_TERMS):
        moves.append("orient_visual")
    if _has_any(lowered, OVERVIEW_TERMS) or (
        _has_any(lowered, ("highest", "lowest", "dominant", "main trend"))
        and len(re.findall(r"\d+(?:\.\d+)?%?", lowered)) <= 1
    ):
        moves.append("highlight_patterns")
    if re.search(r"\d+(?:\.\d+)?%?", lowered) or _has_any(lowered, TREND_TERMS):
        moves.append("report_results")
    if _has_any(lowered, COMPARISON_TERMS):
        moves.append("compare_elaborate")
    if _has_any(lowered, INTERPRETATION_TERMS):
        moves.append("optional_interpretation")
    return list(dict.fromkeys(moves))


def _heuristic_paragraph_functions(
    paragraphs: List[ParagraphInfo],
) -> List[ParagraphFunctionAssessment]:
    if not paragraphs:
        return []

    functions: Dict[int, ParagraphFunctionAssessment] = {}
    first = paragraphs[0]
    first_orients = _has_any(first.text, ORIENT_TERMS)
    functions[first.paragraph_index] = ParagraphFunctionAssessment(
        paragraph_index=first.paragraph_index,
        primary_function="introduction",
        confidence=0.92 if first_orients else 0.65,
        function_clear=first_orients,
    )

    overview_index: Optional[int] = None
    for paragraph in paragraphs:
        if _has_any(paragraph.text, OVERVIEW_TERMS):
            overview_index = paragraph.paragraph_index
            break
    if overview_index is not None and overview_index != first.paragraph_index:
        functions[overview_index] = ParagraphFunctionAssessment(
            paragraph_index=overview_index,
            primary_function="overview",
            confidence=0.94,
            function_clear=True,
        )

    commentary_index: Optional[int] = None
    last = paragraphs[-1]
    if len(paragraphs) > 1 and _has_any(last.text, INTERPRETATION_TERMS):
        commentary_index = last.paragraph_index
        functions[commentary_index] = ParagraphFunctionAssessment(
            paragraph_index=commentary_index,
            primary_function="optional_commentary",
            confidence=0.85,
            function_clear=True,
        )

    detail_candidates = [
        paragraph
        for paragraph in paragraphs
        if paragraph.paragraph_index not in functions
    ]
    for detail_position, paragraph in enumerate(detail_candidates):
        detail_type = "key_details_a" if detail_position == 0 else "key_details_b"
        has_detail_signal = bool(
            re.search(r"\d+(?:\.\d+)?%?", paragraph.text)
            or _has_any(paragraph.text, COMPARISON_TERMS + TREND_TERMS)
        )
        functions[paragraph.paragraph_index] = ParagraphFunctionAssessment(
            paragraph_index=paragraph.paragraph_index,
            primary_function=detail_type,
            confidence=0.88 if has_detail_signal else 0.62,
            function_clear=has_detail_signal,
        )

    return [functions[p.paragraph_index] for p in paragraphs]


class IELTSStructureAgent(BaseStructureAgent):
    name = "IELTSStructureAgent"
    output_model = IELTSStructureResult
    role_prompt = (
        "You evaluate IELTS Task 1 structure under Option C. Check whether "
        "Introduction, Overview, Key Details A, and Key Details B exist, whether "
        "their order is reasonable, and whether each paragraph's function is clear. "
        "Optional Commentary is never required and is not a conclusion."
    )

    def fallback(self, agent_input: IELTSStructureInput) -> IELTSStructureResult:
        functions = _heuristic_paragraph_functions(agent_input.paragraphs)
        by_function = {item.primary_function: item.paragraph_index for item in functions}
        has_overview_move = any(
            _has_any(sentence.text, OVERVIEW_TERMS) for sentence in agent_input.sentences
        )
        presence = {
            "introduction": bool(agent_input.paragraphs),
            "overview": "overview" in by_function or has_overview_move,
            "key_details_a": "key_details_a" in by_function,
            "key_details_b": "key_details_b" in by_function,
            "optional_commentary": "optional_commentary" in by_function,
        }
        missing = [
            node_type
            for node_type in REQUIRED_OPTION_C_NODE_TYPES
            if not presence.get(node_type, False)
        ]

        ordered_positions: List[tuple[str, int]] = []
        for node_type in REQUIRED_OPTION_C_NODE_TYPES:
            if node_type == "overview" and has_overview_move:
                matching = next(
                    (
                        sentence.paragraph_index
                        for sentence in agent_input.sentences
                        if _has_any(sentence.text, OVERVIEW_TERMS)
                    ),
                    None,
                )
                if matching is not None:
                    ordered_positions.append((node_type, matching))
            elif node_type in by_function:
                ordered_positions.append((node_type, by_function[node_type]))
        positions = [position for _, position in ordered_positions]
        order_reasonable = positions == sorted(positions)
        order_issues = []
        if not order_reasonable:
            order_issues.append(
                "Place the Introduction and Overview before the two grouped detail sections."
            )
        return IELTSStructureResult(
            presence=presence,
            order_reasonable=order_reasonable,
            order_issues=order_issues,
            paragraph_functions=functions,
            missing_required_nodes=missing,
        )


class DataCommentaryAgent(BaseStructureAgent):
    name = "DataCommentaryAgent"
    output_model = DataCommentaryResult
    role_prompt = (
        "You identify rhetorical moves in visual data commentary: orient_visual, "
        "highlight_patterns, report_results, compare_elaborate, and "
        "optional_interpretation. Interpretation must be supported by the task or "
        "visual; flag speculative causes or conclusions."
    )

    def fallback(self, agent_input: DataCommentaryInput) -> DataCommentaryResult:
        move_names = [
            "orient_visual",
            "highlight_patterns",
            "report_results",
            "compare_elaborate",
            "optional_interpretation",
        ]
        assessments: List[RhetoricalMoveAssessment] = []
        for move_name in move_names:
            sentence_indices = [
                sentence.index
                for sentence in agent_input.sentences
                if move_name in _detect_moves(sentence.text)
            ]
            paragraph_indices = sorted(
                {
                    sentence.paragraph_index
                    for sentence in agent_input.sentences
                    if sentence.index in sentence_indices
                }
            )
            assessments.append(
                RhetoricalMoveAssessment(
                    move=move_name,
                    present=bool(sentence_indices),
                    paragraph_indices=paragraph_indices,
                    sentence_indices=sentence_indices,
                    evidence_summary=(
                        f"Detected in {len(sentence_indices)} sentence(s)."
                        if sentence_indices
                        else "No deterministic signal detected."
                    ),
                )
            )
        interpretation_present = next(
            (item.present for item in assessments if item.move == "optional_interpretation"),
            False,
        )
        warning = None
        if interpretation_present:
            warning = (
                "Check that any interpretation is explicitly supported by the task or visual; "
                "IELTS Task 1 does not require speculative causes or a separate conclusion."
            )
        return DataCommentaryResult(
            moves=assessments,
            unsupported_interpretation_warning=warning,
        )


def _node_id_for_type(nodes: List[NodeInfo], node_type: str) -> Optional[str]:
    normalized = normalize_node_type(node_type)
    for node in nodes:
        if node.type == normalized:
            return node.id
    return None


def _custom_node_for_text(
    nodes: List[NodeInfo],
    text: str,
) -> tuple[Optional[str], float]:
    stop_words = {
        "custom",
        "structure",
        "node",
        "paragraph",
        "writing",
        "report",
        "the",
        "and",
        "with",
        "from",
    }
    text_tokens = set(re.findall(r"[a-z]{3,}", text.casefold())) - stop_words
    best_node: Optional[str] = None
    best_score = 0.0
    for node in nodes:
        if node.type != "custom":
            continue
        title_tokens = set(
            re.findall(r"[a-z]{3,}", (node.title or "").casefold())
        ) - stop_words
        if not title_tokens:
            continue
        score = len(title_tokens & text_tokens) / len(title_tokens)
        if score > best_score:
            best_node = node.id
            best_score = score
    return best_node, best_score


class SentenceMappingAgent(BaseStructureAgent):
    name = "SentenceMappingAgent"
    output_model = SentenceMappingResult
    role_prompt = (
        "You map the student's paragraphs and sentences to the exact node IDs in "
        "the current flowchart. Give each paragraph at most one primary node. "
        "Sentences may express secondary rhetorical moves. Preserve the supplied "
        "character offsets and never invent node IDs."
    )

    def fallback(self, agent_input: SentenceMappingInput) -> SentenceMappingResult:
        function_by_paragraph = {
            item.paragraph_index: item
            for item in agent_input.ielts_structure.paragraph_functions
        }
        paragraph_mappings: List[ParagraphMapping] = []
        sentence_mappings: List[SentenceNodeMapping] = []

        for paragraph in agent_input.paragraphs:
            function = function_by_paragraph.get(paragraph.paragraph_index)
            function_type = function.primary_function if function else "key_details_a"
            primary_node = _node_id_for_type(agent_input.nodes, function_type)
            custom_node, custom_score = _custom_node_for_text(
                agent_input.nodes,
                paragraph.text,
            )
            if custom_node and custom_score >= 0.5:
                primary_node = custom_node
            moves: List[str] = []
            for sentence_index in paragraph.sentence_indices:
                sentence = next(
                    (item for item in agent_input.sentences if item.index == sentence_index),
                    None,
                )
                if sentence:
                    moves.extend(_detect_moves(sentence.text))
            moves = list(dict.fromkeys(moves))
            paragraph_mappings.append(
                ParagraphMapping(
                    paragraph_index=paragraph.paragraph_index,
                    start=paragraph.start,
                    end=paragraph.end,
                    primary_node=primary_node,
                    secondary_moves=moves,
                    confidence=(
                        max(function.confidence if function else 0.55, custom_score)
                        if primary_node
                        else 0.0
                    ),
                    sentence_indices=list(paragraph.sentence_indices),
                )
            )

            for sentence_index in paragraph.sentence_indices:
                sentence = next(
                    item for item in agent_input.sentences if item.index == sentence_index
                )
                sentence_moves = _detect_moves(sentence.text)
                sentence_primary_type = function_type
                if "optional_interpretation" in sentence_moves:
                    sentence_primary_type = "optional_commentary"
                elif "highlight_patterns" in sentence_moves:
                    sentence_primary_type = "overview"
                elif (
                    function_type == "introduction"
                    and "orient_visual" in sentence_moves
                ):
                    sentence_primary_type = "introduction"
                primary_sentence_node = (
                    _node_id_for_type(agent_input.nodes, sentence_primary_type)
                    or primary_node
                )
                sentence_custom_node, sentence_custom_score = _custom_node_for_text(
                    agent_input.nodes,
                    sentence.text,
                )
                if sentence_custom_node and sentence_custom_score >= 0.5:
                    primary_sentence_node = sentence_custom_node
                node_ids = [primary_sentence_node] if primary_sentence_node else []
                score = max(
                    function.confidence if function else 0.55,
                    sentence_custom_score,
                )
                scores = {node_id: round(max(0.0, min(1.0, score)), 2) for node_id in node_ids}
                sentence_mappings.append(
                    SentenceNodeMapping(
                        sentence_index=sentence.index,
                        primary_node=primary_sentence_node,
                        node_ids=node_ids,
                        scores=scores,
                        secondary_moves=sentence_moves,
                    )
                )

        return SentenceMappingResult(
            paragraph_mappings=paragraph_mappings,
            sentence_mappings=sentence_mappings,
        )


class FeedbackIntegrationAgent(BaseStructureAgent):
    name = "FeedbackIntegrationAgent"
    output_model = FeedbackIntegrationResult
    role_prompt = (
        "You integrate the four specialist results into concise, actionable "
        "structure feedback. Option C is complete when Introduction, Overview, "
        "Key Details A, and Key Details B are present. Optional Commentary is never "
        "required and must not introduce unsupported causes or conclusions."
    )

    def fallback(self, agent_input: FeedbackIntegrationInput) -> FeedbackIntegrationResult:
        missing = list(agent_input.ielts_structure.missing_required_nodes)
        suggestions: List[str] = []
        for node_type in missing:
            if node_type == "overview":
                suggestions.append(
                    "Add a clear overview that highlights the most important overall patterns."
                )
            elif node_type == "introduction":
                suggestions.append(
                    "Begin with a paraphrase that identifies what the visual presents."
                )
            elif node_type == "key_details_a":
                suggestions.append(
                    "Add a first logically grouped detail paragraph with data and comparisons."
                )
            elif node_type == "key_details_b":
                suggestions.append(
                    "Add a second logically grouped detail paragraph to complete the comparison."
                )
        suggestions.extend(agent_input.ielts_structure.order_issues)
        if agent_input.commentary.unsupported_interpretation_warning:
            suggestions.append(agent_input.commentary.unsupported_interpretation_warning)
        is_complete = not missing
        return FeedbackIntegrationResult(
            overall_status="complete" if is_complete else "incomplete",
            is_complete=is_complete,
            summary=(
                "The required Option C structure is present."
                if is_complete
                else f"Missing required structure: {', '.join(missing)}."
            ),
            missing_nodes=missing,
            order_issues=list(agent_input.ielts_structure.order_issues),
            paragraph_correspondence=list(agent_input.mapping.paragraph_mappings),
            suggestions=list(dict.fromkeys(suggestions)),
        )


def split_paragraphs_and_sentences(
    text: str,
) -> tuple[List[ParagraphInfo], List[SentenceInfo]]:
    paragraphs: List[ParagraphInfo] = []
    sentences: List[SentenceInfo] = []
    if not text:
        return paragraphs, sentences

    paragraph_spans: List[tuple[int, int]] = []
    blank_line_pattern = re.compile(r"\r?\n[ \t]*\r?\n")
    separators = list(blank_line_pattern.finditer(text))
    if separators:
        cursor = 0
        for separator in separators:
            paragraph_spans.append((cursor, separator.start()))
            cursor = separator.end()
        paragraph_spans.append((cursor, len(text)))
    else:
        nonempty_lines = list(re.finditer(r"(?m)^[ \t]*\S[^\r\n]*", text))
        lines_look_like_paragraphs = (
            len(nonempty_lines) > 1
            and all(
                match.group(0).rstrip().endswith((".", "!", "?"))
                for match in nonempty_lines
            )
        )
        paragraph_spans = (
            [match.span() for match in nonempty_lines]
            if lines_look_like_paragraphs
            else [(0, len(text))]
        )

    for raw_start, raw_end in paragraph_spans:
        raw_text = text[raw_start:raw_end]
        leading = len(raw_text) - len(raw_text.lstrip())
        trailing = len(raw_text.rstrip())
        start = raw_start + leading
        end = raw_start + trailing
        if end <= start:
            continue
        paragraph_index = len(paragraphs)
        paragraph_text = text[start:end]
        sentence_indices: List[int] = []
        sentence_pattern = re.compile(r"(?s)\S.*?(?:[.!?]+(?=\s|$)|\Z)")
        for sentence_match in sentence_pattern.finditer(paragraph_text):
            fragment = sentence_match.group(0)
            fragment_leading = len(fragment) - len(fragment.lstrip())
            fragment_trailing = len(fragment.rstrip())
            sentence_start = start + sentence_match.start() + fragment_leading
            sentence_end = start + sentence_match.start() + fragment_trailing
            if sentence_end <= sentence_start:
                continue
            sentence_index = len(sentences)
            sentence_indices.append(sentence_index)
            sentences.append(
                SentenceInfo(
                    index=sentence_index,
                    start=sentence_start,
                    end=sentence_end,
                    text=text[sentence_start:sentence_end],
                    paragraph_index=paragraph_index,
                )
            )
        paragraphs.append(
            ParagraphInfo(
                paragraph_index=paragraph_index,
                start=start,
                end=end,
                text=paragraph_text,
                sentence_indices=sentence_indices,
            )
        )
    return paragraphs, sentences


def split_sentences(text: str) -> List[SentenceInfo]:
    return split_paragraphs_and_sentences(text)[1]


def extract_nodes(flowchart: Optional[dict]) -> List[NodeInfo]:
    nodes: List[NodeInfo] = []
    if isinstance(flowchart, dict):
        for raw_node in flowchart.get("nodes", []) or []:
            if not isinstance(raw_node, dict):
                continue
            node_id = str(raw_node.get("id") or raw_node.get("type") or f"node_{len(nodes)}")
            original_type = str(raw_node.get("type") or "custom")
            normalized_type = normalize_node_type(original_type)
            nodes.append(
                NodeInfo(
                    id=node_id,
                    type=normalized_type,
                    original_type=original_type,
                    title=raw_node.get("title") or raw_node.get("label") or node_id,
                    optional=normalized_type == "optional_commentary"
                    or bool(raw_node.get("optional")),
                )
            )
    if nodes:
        return nodes
    return [
        NodeInfo(
            id=node_type,
            type=node_type,
            original_type=node_type,
            title=OPTION_C_LABELS[node_type],
            optional=node_type == "optional_commentary",
        )
        for node_type in OPTION_C_NODE_TYPES
    ]


class StructureFeedbackOrchestrator:
    def __init__(
        self,
        llm_caller: Optional[LLMCaller] = None,
        *,
        use_llm: bool = True,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1200,
    ):
        if llm_caller is not None:
            self.llm_caller = llm_caller
        elif use_llm and get_deepseek_api_key():
            self.llm_caller = _deepseek_llm_caller
        else:
            self.llm_caller = None
        self.model = get_deepseek_model(model)
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _agent(self, agent_class: Type[BaseStructureAgent]) -> BaseStructureAgent:
        return agent_class(
            self.llm_caller,
            self.model,
            self.temperature,
            self.max_tokens,
        )

    def _run_agent(
        self,
        agent: BaseStructureAgent,
        agent_input: BaseModel,
        trace: List[AgentTraceEntry],
    ) -> BaseModel:
        status = "completed"
        try:
            result = agent.run(agent_input)
        except Exception:
            result = agent.fallback(agent_input)
            status = "fallback"
        trace.append(
            AgentTraceEntry(
                agent_name=agent.name,
                status=status,
                result_summary=self._summarize_result(result),
            )
        )
        return result

    @staticmethod
    def _summarize_result(result: BaseModel) -> Dict[str, Any]:
        if isinstance(result, TaskUnderstandingResult):
            return {"task_type": result.task_type, "expected_nodes": len(result.expected_structure)}
        if isinstance(result, IELTSStructureResult):
            return {
                "missing_required_nodes": list(result.missing_required_nodes),
                "order_reasonable": result.order_reasonable,
            }
        if isinstance(result, DataCommentaryResult):
            return {
                "moves_present": [move.move for move in result.moves if move.present],
                "interpretation_warning": bool(result.unsupported_interpretation_warning),
            }
        if isinstance(result, SentenceMappingResult):
            return {
                "paragraphs_mapped": len(result.paragraph_mappings),
                "sentences_mapped": len(result.sentence_mappings),
            }
        if isinstance(result, FeedbackIntegrationResult):
            return {
                "overall_status": result.overall_status,
                "missing_count": len(result.missing_nodes),
                "suggestion_count": len(result.suggestions),
            }
        return {"result_type": result.__class__.__name__}

    @staticmethod
    def _normalize_mapping(
        result: SentenceMappingResult,
        fallback: SentenceMappingResult,
        paragraphs: List[ParagraphInfo],
        sentences: List[SentenceInfo],
        nodes: List[NodeInfo],
    ) -> SentenceMappingResult:
        valid_node_ids = {node.id for node in nodes}
        paragraph_by_index = {item.paragraph_index: item for item in paragraphs}
        fallback_paragraphs = {
            item.paragraph_index: item for item in fallback.paragraph_mappings
        }
        normalized_paragraphs: List[ParagraphMapping] = []
        supplied_paragraphs = {
            item.paragraph_index: item for item in result.paragraph_mappings
        }
        for paragraph in paragraphs:
            item = supplied_paragraphs.get(paragraph.paragraph_index)
            if item is None or (
                item.primary_node is not None and item.primary_node not in valid_node_ids
            ) or (
                item.primary_node is None
                and fallback_paragraphs[paragraph.paragraph_index].primary_node is not None
            ):
                item = fallback_paragraphs[paragraph.paragraph_index]
            normalized_paragraphs.append(
                item.model_copy(
                    update={
                        "start": paragraph.start,
                        "end": paragraph.end,
                        "sentence_indices": list(paragraph.sentence_indices),
                    }
                )
            )

        fallback_sentences = {
            item.sentence_index: item for item in fallback.sentence_mappings
        }
        supplied_sentences = {
            item.sentence_index: item for item in result.sentence_mappings
        }
        normalized_sentences: List[SentenceNodeMapping] = []
        for sentence in sentences:
            item = supplied_sentences.get(sentence.index)
            if item is None or (
                item.primary_node is not None and item.primary_node not in valid_node_ids
            ) or (
                item.primary_node is None
                and fallback_sentences[sentence.index].primary_node is not None
            ):
                item = fallback_sentences[sentence.index]
            valid_ids = [node_id for node_id in item.node_ids if node_id in valid_node_ids]
            primary = item.primary_node if item.primary_node in valid_node_ids else None
            if primary and primary not in valid_ids:
                valid_ids.insert(0, primary)
            normalized_sentences.append(
                item.model_copy(
                    update={
                        "primary_node": primary,
                        "node_ids": valid_ids,
                        "scores": {
                            key: value
                            for key, value in item.scores.items()
                            if key in valid_node_ids
                        },
                    }
                )
            )
        return SentenceMappingResult(
            paragraph_mappings=normalized_paragraphs,
            sentence_mappings=normalized_sentences,
        )

    def analyze(self, request: StructureAnalysisRequest) -> StructureAnalysisResponse:
        if not request.current_text or not request.current_text.strip():
            return StructureAnalysisResponse(error="current_text is empty")

        paragraphs, sentences = split_paragraphs_and_sentences(request.current_text)
        nodes = extract_nodes(request.flowchart)
        trace: List[AgentTraceEntry] = []

        task_input = TaskUnderstandingInput(
            current_text=request.current_text,
            deplot_text=request.deplot_text,
            chart_type=request.chart_type,
        )
        task = self._run_agent(
            self._agent(TaskUnderstandingAgent),
            task_input,
            trace,
        )
        assert isinstance(task, TaskUnderstandingResult)

        ielts_input = IELTSStructureInput(
            paragraphs=paragraphs,
            sentences=sentences,
            task=task,
        )
        ielts = self._run_agent(
            self._agent(IELTSStructureAgent),
            ielts_input,
            trace,
        )
        assert isinstance(ielts, IELTSStructureResult)
        deterministic_ielts = IELTSStructureAgent(
            None, self.model, 0.0, self.max_tokens
        ).fallback(ielts_input)
        ielts = ielts.model_copy(
            update={
                "presence": deterministic_ielts.presence,
                "order_reasonable": deterministic_ielts.order_reasonable,
                "order_issues": list(
                    dict.fromkeys(
                        deterministic_ielts.order_issues + ielts.order_issues
                    )
                ),
                "paragraph_functions": deterministic_ielts.paragraph_functions,
                "missing_required_nodes": deterministic_ielts.missing_required_nodes,
            }
        )

        commentary_input = DataCommentaryInput(
            paragraphs=paragraphs,
            sentences=sentences,
            task=task,
        )
        commentary = self._run_agent(
            self._agent(DataCommentaryAgent),
            commentary_input,
            trace,
        )
        assert isinstance(commentary, DataCommentaryResult)

        mapping_input = SentenceMappingInput(
            paragraphs=paragraphs,
            sentences=sentences,
            nodes=nodes,
            ielts_structure=ielts,
            commentary=commentary,
        )
        mapping_agent = self._agent(SentenceMappingAgent)
        mapping = self._run_agent(mapping_agent, mapping_input, trace)
        assert isinstance(mapping, SentenceMappingResult)
        fallback_mapping = mapping_agent.fallback(
            mapping_input.model_copy(update={"ielts_structure": deterministic_ielts})
        )
        assert isinstance(fallback_mapping, SentenceMappingResult)
        mapping = self._normalize_mapping(
            mapping,
            fallback_mapping,
            paragraphs,
            sentences,
            nodes,
        )

        integration_input = FeedbackIntegrationInput(
            task=task,
            ielts_structure=ielts,
            commentary=commentary,
            mapping=mapping,
        )
        integration_agent = self._agent(FeedbackIntegrationAgent)
        feedback = self._run_agent(integration_agent, integration_input, trace)
        assert isinstance(feedback, FeedbackIntegrationResult)

        deterministic_integration_input = integration_input.model_copy(
            update={"ielts_structure": deterministic_ielts, "mapping": mapping}
        )
        deterministic_feedback = integration_agent.fallback(
            deterministic_integration_input
        )
        missing_types = list(deterministic_feedback.missing_nodes)
        feedback = feedback.model_copy(
            update={
                "overall_status": deterministic_feedback.overall_status,
                "is_complete": deterministic_feedback.is_complete,
                "summary": deterministic_feedback.summary,
                "missing_nodes": missing_types,
                "order_issues": deterministic_feedback.order_issues,
                "paragraph_correspondence": mapping.paragraph_mappings,
                "suggestions": list(
                    dict.fromkeys(
                        deterministic_feedback.suggestions + feedback.suggestions
                    )
                ),
            }
        )

        missing_nodes: List[MissingNodeInfo] = []
        for node_type in missing_types:
            node = next((item for item in nodes if item.type == node_type), None)
            missing_nodes.append(
                MissingNodeInfo(
                    id=node.id if node else node_type,
                    title=node.title if node else OPTION_C_LABELS[node_type],
                    reason=f"Required Option C function '{node_type}' was not detected.",
                    required=True,
                )
            )
        mapped_node_ids = {
            mapping.primary_node
            for mapping in mapping.paragraph_mappings + mapping.sentence_mappings
            if mapping.primary_node
        }
        for node in nodes:
            if node.type == "custom" and node.id not in mapped_node_ids:
                missing_nodes.append(
                    MissingNodeInfo(
                        id=node.id,
                        title=node.title,
                        reason="No paragraph or sentence was mapped to this custom node.",
                        required=False,
                    )
                )

        alias_types = {
            node.original_type: node.type
            for node in nodes
            if node.original_type and node.original_type != node.type
        }
        return StructureAnalysisResponse(
            sentences=sentences,
            nodes=nodes,
            mappings=mapping.sentence_mappings,
            missing_nodes=missing_nodes,
            paragraphs=paragraphs,
            paragraph_mappings=mapping.paragraph_mappings,
            structure_feedback=feedback,
            agent_trace=trace,
            debug={
                "orchestrator": "StructureFeedbackOrchestrator",
                "model": self.model,
                "llm_enabled": self.llm_caller is not None,
                "fallback_used": any(item.status == "fallback" for item in trace),
                "required_structure": list(REQUIRED_OPTION_C_NODE_TYPES),
                "optional_structure": ["optional_commentary"],
                "legacy_aliases_applied": alias_types,
                "paragraph_count": len(paragraphs),
                "sentence_count": len(sentences),
            },
        )


def analyze_structure(request: StructureAnalysisRequest) -> StructureAnalysisResponse:
    return StructureFeedbackOrchestrator(
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    ).analyze(request)


@router.post("/api/analyze-structure", response_model=StructureAnalysisResponse)
def analyze_structure_endpoint(
    request: StructureAnalysisRequest,
) -> StructureAnalysisResponse:
    return analyze_structure(request)
