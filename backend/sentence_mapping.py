"""Sentence to flowchart node mapping module.

Given full current text and flowchart JSON (nodes, edges), produce mapping of each
sentence to relevant node ids with a primary node and relevance scores.

Design goals:
- Deterministic prompt structure (same blocks always included)
- Graceful fallback if LLM JSON invalid (simple heuristic keyword overlap)
- Provide sentence character offsets for frontend highlighting

Environment: requires DEEPSEEK_API_KEY in environment (.env supported).
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import re
import json
from dotenv import load_dotenv
from deepseek_config import get_deepseek_client, get_deepseek_extra_body, get_deepseek_model

load_dotenv()

# ------------------ Data Models ------------------
class SentenceMappingRequest(BaseModel):
    current_text: str
    flowchart: Optional[dict] = None  # expects {nodes:[], edges:[]}
    model: Optional[str] = None
    temperature: Optional[float] = 0.0  # deterministic for mapping
    max_tokens: Optional[int] = 600

class SentenceInfo(BaseModel):
    index: int
    start: int
    end: int
    text: str

class NodeInfo(BaseModel):
    id: str
    type: Optional[str] = None
    title: Optional[str] = None

class SentenceNodeMapping(BaseModel):
    sentence_index: int
    primary_node: Optional[str] = None
    node_ids: List[str] = []
    scores: Dict[str, float] = {}

class MissingNodeInfo(BaseModel):
    id: str
    title: Optional[str] = None
    reason: Optional[str] = None

class SentenceMappingResponse(BaseModel):
    sentences: Optional[List[SentenceInfo]] = None
    nodes: Optional[List[NodeInfo]] = None
    mappings: Optional[List[SentenceNodeMapping]] = None
    missing_nodes: Optional[List[MissingNodeInfo]] = None
    error: Optional[str] = None
    debug: Optional[dict] = None

# ------------------ Sentence Splitting ------------------
SENTENCE_REGEX = re.compile(r"([^.!?]*[.!?])", re.UNICODE)

# ------------------ IELTS Structure Detection ------------------
def _detect_ielts_structure(sentences: List[SentenceInfo]) -> Dict[str, List[int]]:
    """Detect IELTS Task 1 structure patterns in sentences."""
    structure = {
        "introduction": [],
        "overview": [],
        "body": [],
        "conclusion": []
    }
    
    if not sentences:
        return structure
    
    total_sentences = len(sentences)
    
    # Simple heuristic based on position and content
    for i, sentence in enumerate(sentences):
        text = sentence.text.lower()
        
        # Introduction: first 1-2 sentences, often contain paraphrasing
        if i < 2 and any(keyword in text for keyword in ["chart", "graph", "table", "shows", "illustrates", "displays", "presents"]):
            structure["introduction"].append(i)
        # Overview: sentences 2-4, often contain "overall", "generally", "in general"
        elif 1 <= i < 4 and any(keyword in text for keyword in ["overall", "generally", "in general", "in summary", "in conclusion"]):
            structure["overview"].append(i)
        # Body: middle sentences with data
        elif 2 <= i < total_sentences - 1:
            structure["body"].append(i)
        # Conclusion: last 1-2 sentences
        elif i >= total_sentences - 2:
            structure["conclusion"].append(i)
    
    return structure

def split_sentences(text: str) -> List[SentenceInfo]:
    sentences: List[SentenceInfo] = []
    if not text:
        return sentences
    # Basic strategy: iterate over regex matches capturing end punctuation
    pos = 0
    idx = 0
    for match in re.finditer(r"(?s)(.+?)([.!?])(\s+|$)", text):
        full = match.group(0)
        core = match.group(1).strip()
        if not core:
            continue
        start = match.start(1)
        end = match.end(2)  # include punctuation
        sentences.append(SentenceInfo(index=idx, start=start, end=end, text=text[start:end].strip()))
        idx += 1
        pos = match.end()
    # Tail fragment without terminal punctuation
    if pos < len(text):
        tail = text[pos:].strip()
        if tail:
            sentences.append(SentenceInfo(index=idx, start=pos, end=len(text), text=tail))
    return sentences

# ------------------ Prompt Construction ------------------

def _extract_nodes(flowchart: Optional[dict]) -> List[NodeInfo]:
    out: List[NodeInfo] = []
    if not flowchart or not isinstance(flowchart, dict):
        return out
    for n in flowchart.get("nodes", []) or []:
        node_id = str(n.get("id"))
        title = n.get("title") or n.get("label") or node_id
        out.append(NodeInfo(id=node_id, type=n.get("type"), title=title))
    return out

PROMPT_SYSTEM = (
    "ROLE: You are an expert assistant that precisely maps sentences to structural flowchart nodes for IELTS Task 1 writing.\n"
    "TASK: For EACH sentence, determine the MOST APPROPRIATE flowchart node based on sentence function and content.\n"
    "ANALYSIS CRITERIA:\n"
    "1. SENTENCE FUNCTION: What is the sentence's primary purpose?\n"
    "   - Data presentation (specific numbers, percentages, comparisons)\n"
    "   - General introduction/paraphrase (describing what the chart shows)\n"
    "   - Overview/summary (key trends, main patterns)\n"
    "   - Interpretation/analysis (explaining what the data means)\n"
    "2. CONTENT TYPE: What kind of information does it contain?\n"
    "   - Raw data (numbers, percentages, specific values)\n"
    "   - Comparative analysis (higher than, lower than, similar to)\n"
    "   - Trend description (increased, decreased, remained stable)\n"
    "   - General statements (overall, in general, the chart shows)\n"
    "PRECISE MAPPING RULES:\n"
    "- 'background': Only for introductory context or disciplinary knowledge\n"
    "- 'summary': For overview statements and general trends (\"Overall, the chart shows...\")\n"
    "- 'results': For specific data presentation and numerical comparisons\n"
    "- 'reference_explanation': For detailed analysis, comparisons, and trend explanations\n"
    "- 'comment': For interpretations, conclusions, and analytical insights\n"
    "ACCURACY REQUIREMENTS:\n"
    "1. You MUST return valid JSON only (no commentary, no markdown).\n"
    "2. Each sentence has: primary_node (string or null), node_ids (list of node ids), scores (object mapping node id to relevance 0-1).\n"
    "3. Be PRECISE: Only map to nodes that truly match the sentence's function.\n"
    "4. Relevance scores: 1.0 = perfect match, 0.8 = strong match, 0.6 = good match, 0.4 = weak match, 0.2 = very weak.\n"
    "5. Do NOT hallucinate node ids not present in provided list.\n"
    "6. Primary node must be the BEST match for the sentence's primary function.\n"
    "7. Keep scores to at most 2 decimal places.\n"
    "8. If a sentence doesn't clearly fit any node, set primary_node=null and node_ids=[].\n"
    "9. Consider sentence position: early sentences are more likely introduction/overview, later sentences more likely analysis/interpretation.\n"
    "10. Focus on the sentence's MAIN purpose, not secondary details.\n"
)

def _build_messages(sentences: List[SentenceInfo], nodes: List[NodeInfo]) -> List[Dict[str, str]]:
    def _esc(val: Optional[str]) -> str:
        if not val:
            return ""
        return val.replace("\"", "\\\"").replace("\n", " ").strip()
    
    # Detect IELTS structure patterns
    ielts_structure = _detect_ielts_structure(sentences)
    
    node_block_lines = [
        '{"id": "%s", "type": "%s", "title": "%s"}' % (
            n.id,
            _esc(n.type or ""),
            _esc(n.title or ""),
        ) for n in nodes
    ]
    node_block = "[" + ",\n".join(node_block_lines) + "]"
    sent_block_lines = [
        '{"index": %d, "text": "%s"}' % (
            s.index,
            _esc(s.text),
        ) for s in sentences
    ]
    sent_block = "[" + ",\n".join(sent_block_lines) + "]"

    # Build structure analysis text
    structure_analysis = ""
    if any(ielts_structure.values()):
        structure_analysis = "\nDETECTED IELTS STRUCTURE:\n"
        for section, indices in ielts_structure.items():
            if indices:
                structure_analysis += f"- {section.capitalize()} sentences: {indices}\n"

    user_content = (
        "FLOWCHART_NODES_JSON:\n" + node_block + "\n\n" +
        "SENTENCES_JSON:\n" + sent_block + "\n\n" +
        structure_analysis +
        "DETAILED ANALYSIS INSTRUCTIONS:\n"
        "For each sentence, analyze:\n"
        "1. PRIMARY FUNCTION: What is the sentence's main purpose?\n"
        "2. CONTENT TYPE: What kind of information does it contain?\n"
        "3. POSITION CONTEXT: How does it relate to surrounding sentences?\n\n"
        "MAPPING GUIDELINES:\n"
        "- 'background': Only for introductory context or disciplinary knowledge (rare)\n"
        "- 'summary': For overview statements, general trends, and key patterns\n"
        "- 'results': For specific data presentation, numbers, percentages, and direct comparisons\n"
        "- 'reference_explanation': For detailed analysis, trend explanations, and comparative discussions\n"
        "- 'comment': For interpretations, conclusions, and analytical insights\n\n"
        "ACCURACY FOCUS:\n"
        "- Be PRECISE: Only map to nodes that truly match the sentence's primary function\n"
        "- Avoid over-mapping: Don't assign sentences to multiple nodes unless truly relevant\n"
        "- Consider context: Early sentences are likely introduction/overview, later sentences analysis/interpretation\n"
        "- Focus on MAIN purpose: Ignore secondary details and focus on the sentence's core function\n\n"
        "INSTRUCTION: Return JSON with exactly this shape: {\n"
        "  \"mappings\": [\n"
        "    {\"sentence_index\": <int>, \"primary_node\": <string|null>, \"node_ids\": [<string>...], \"scores\": {<node_id>: <float 0-1>...}}\n"
        "  ]\n"
        "}\n"
        "Return ONLY JSON."
    )
    return [
        {"role": "system", "content": PROMPT_SYSTEM},
        {"role": "user", "content": user_content},
    ]

# ------------------ LLM Call ------------------

def _call_chat(messages: List[Dict[str, str]], model: str, temperature: float, max_tokens: int) -> str:
    client = get_deepseek_client()
    chat = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        extra_body=get_deepseek_extra_body(),
    )
    return chat.choices[0].message.content if chat.choices else ""

# ------------------ JSON Parsing & Fallback ------------------

def _strip_json(text: str) -> str:
    if not text:
        return ""
    # Remove code fences if present
    text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"```$", "", text.strip())
    # Find first '{' and last '}'
    first = text.find('{')
    last = text.rfind('}')
    if first != -1 and last != -1 and last > first:
        return text[first:last+1]
    return text

def _compute_zero_overlap_nodes(sentences: List[SentenceInfo], nodes: List[NodeInfo]) -> List[MissingNodeInfo]:
    """Fallback: nodes whose title tokens never appear in any sentence -> missing."""
    def tokenize(s: str) -> List[str]:
        return re.findall(r"[A-Za-z]+", s.lower())
    all_sentence_tokens = set()
    for s in sentences:
        all_sentence_tokens.update(tokenize(s.text))
    missing: List[MissingNodeInfo] = []
    for n in nodes:
        tokens = set(tokenize(n.title or ""))
        if tokens and not (tokens & all_sentence_tokens):
            missing.append(MissingNodeInfo(id=n.id, title=n.title, reason="No lexical overlap with any sentence"))
    return missing

def _validate_mapping_quality(mappings: List[SentenceNodeMapping], sentences: List[SentenceInfo], nodes: List[NodeInfo]) -> List[SentenceNodeMapping]:
    """Validate and improve mapping quality by checking for common issues."""
    improved_mappings = []
    
    for mapping in mappings:
        sentence = sentences[mapping.sentence_index]
        text = sentence.text.lower()
        
        # Check for over-mapping (too many nodes assigned)
        if len(mapping.node_ids) > 2:
            # Keep only the highest scoring nodes
            sorted_nodes = sorted(mapping.scores.items(), key=lambda x: x[1], reverse=True)
            mapping.node_ids = [node_id for node_id, score in sorted_nodes[:2]]
            mapping.primary_node = mapping.node_ids[0] if mapping.node_ids else None
        
        # Check for under-mapping (no nodes assigned when there should be)
        if not mapping.node_ids and any(keyword in text for keyword in ["chart", "graph", "data", "shows", "indicates", "overall", "increased", "decreased"]):
            # Try to find appropriate nodes based on content
            for node in nodes:
                if node.type == "summary" and any(word in text for word in ["overall", "generally", "in general", "in summary"]):
                    mapping.node_ids.append(node.id)
                    mapping.scores[node.id] = 0.7
                    mapping.primary_node = node.id
                elif node.type == "results" and any(word in text for word in ["data", "chart", "graph", "shows", "indicates"]):
                    mapping.node_ids.append(node.id)
                    mapping.scores[node.id] = 0.7
                    mapping.primary_node = node.id
                elif node.type == "comment" and any(word in text for word in ["conclusion", "interpretation", "analysis", "suggests"]):
                    mapping.node_ids.append(node.id)
                    mapping.scores[node.id] = 0.7
                    mapping.primary_node = node.id
        
        # Ensure primary_node is in node_ids
        if mapping.primary_node and mapping.primary_node not in mapping.node_ids:
            mapping.node_ids.append(mapping.primary_node)
            mapping.scores[mapping.primary_node] = mapping.scores.get(mapping.primary_node, 0.8)
        
        improved_mappings.append(mapping)
    
    return improved_mappings

def _create_heuristic_mappings(sentences: List[SentenceInfo], nodes: List[NodeInfo]) -> List[SentenceNodeMapping]:
    """Create heuristic mappings based on IELTS structure detection."""
    mappings: List[SentenceNodeMapping] = []
    ielts_structure = _detect_ielts_structure(sentences)
    
    # Create node type lookup
    node_types = {n.id: n.type for n in nodes}
    
    for i, sentence in enumerate(sentences):
        primary_node = None
        node_ids = []
        scores = {}
        
        # Map based on detected IELTS structure
        if i in ielts_structure["introduction"]:
            # Introduction sentences → background or summary
            for node in nodes:
                if node.type in ["background", "summary"]:
                    node_ids.append(node.id)
                    scores[node.id] = 0.8
                    if not primary_node:
                        primary_node = node.id
        elif i in ielts_structure["overview"]:
            # Overview sentences → summary or results
            for node in nodes:
                if node.type in ["summary", "results"]:
                    node_ids.append(node.id)
                    scores[node.id] = 0.8
                    if not primary_node:
                        primary_node = node.id
        elif i in ielts_structure["body"]:
            # Body sentences → results or reference_explanation
            for node in nodes:
                if node.type in ["results", "reference_explanation"]:
                    node_ids.append(node.id)
                    scores[node.id] = 0.7
                    if not primary_node:
                        primary_node = node.id
        elif i in ielts_structure["conclusion"]:
            # Conclusion sentences → comment
            for node in nodes:
                if node.type == "comment":
                    node_ids.append(node.id)
                    scores[node.id] = 0.8
                    if not primary_node:
                        primary_node = node.id
        else:
            # Fallback: try to match based on content keywords
            text_lower = sentence.text.lower()
            for node in nodes:
                if node.type == "results" and any(word in text_lower for word in ["data", "chart", "graph", "shows", "indicates"]):
                    node_ids.append(node.id)
                    scores[node.id] = 0.6
                    if not primary_node:
                        primary_node = node.id
                elif node.type == "comment" and any(word in text_lower for word in ["overall", "conclusion", "summary", "generally"]):
                    node_ids.append(node.id)
                    scores[node.id] = 0.6
                    if not primary_node:
                        primary_node = node.id
        
        mappings.append(SentenceNodeMapping(
            sentence_index=i,
            primary_node=primary_node,
            node_ids=node_ids,
            scores=scores
        ))
    
    return mappings

def _build_missing_nodes_messages(sentences: List[SentenceInfo], nodes: List[NodeInfo]) -> List[Dict[str,str]]:
    def _esc(val: Optional[str]) -> str:
        if not val:
            return ""
        return val.replace("\"", "\\\"").replace("\n", " ").strip()
    sent_block_lines = [
        '{"index": %d, "text": "%s"}' % (s.index, _esc(s.text))
        for s in sentences
    ]
    sent_block = "[" + ",\n".join(sent_block_lines) + "]"
    node_block_lines = [
        '{"id": "%s", "title": "%s", "type": "%s"}' % (
            n.id, _esc(n.title or ""), _esc(n.type or "")
        ) for n in nodes
    ]
    node_block = "[" + ",\n".join(node_block_lines) + "]"
    system = (
        "ROLE: You assess coverage completeness of flowchart nodes in a student's text.\n"
        "TASK: Identify which nodes are NOT yet expressed in any provided sentence.\n"
        "OUTPUT: Strict JSON only.\n"
        "CRITERIA: A node is missing if its distinctive concept is absent; minor synonyms okay.\n"
        "RETURN FORMAT: {\n  \"missing_nodes\": [ {\"id\": str, \"reason\": str} ... ]\n} (omit nodes that are covered).\n"
        "If all nodes are covered return {\"missing_nodes\": []}."
    )
    user = (
        "NODES:\n" + node_block + "\n\nSENTENCES:\n" + sent_block + "\n\nReturn ONLY JSON." 
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

# ------------------ Public API ------------------

def map_sentences(req: SentenceMappingRequest) -> SentenceMappingResponse:
    if not req.current_text or not req.current_text.strip():
        return SentenceMappingResponse(error="current_text is empty")
    sentences = split_sentences(req.current_text)
    nodes = _extract_nodes(req.flowchart)

    # First: try mapping
    mapping_messages = _build_messages(sentences, nodes)
    raw_mapping = ""
    mapping_json: Dict[str, Any] | None = None
    mapping_ok = False
    model = get_deepseek_model(req.model)
    try:
        raw_mapping = _call_chat(mapping_messages, model, req.temperature or 0.0, req.max_tokens or 600)
        cleaned = _strip_json(raw_mapping)
        if cleaned:
            mapping_json = json.loads(cleaned)
            if isinstance(mapping_json, dict) and isinstance(mapping_json.get("mappings"), list):
                mapping_ok = True
    except Exception:
        mapping_ok = False

    llm_mappings: List[SentenceNodeMapping] = []
    if mapping_ok:
        for item in mapping_json.get("mappings", []):
            try:
                s_idx = int(item.get("sentence_index"))
                if s_idx < 0 or s_idx >= len(sentences):
                    continue
                primary = item.get("primary_node")
                if primary is not None:
                    primary = str(primary)
                node_ids = [str(n) for n in (item.get("node_ids") or []) if any(nn.id == str(n) for nn in nodes)]
                scores_raw = item.get("scores") or {}
                scores: Dict[str, float] = {}
                for k, v in scores_raw.items():
                    try:
                        if any(nn.id == str(k) for nn in nodes):
                            scores[str(k)] = float(v)
                    except Exception:
                        continue
                if primary and primary not in node_ids and primary not in scores:
                    primary = None
                if not node_ids and primary:
                    node_ids = [primary]
                llm_mappings.append(SentenceNodeMapping(
                    sentence_index=s_idx,
                    primary_node=primary,
                    node_ids=node_ids,
                    scores=scores,
                ))
            except Exception:
                continue
        existing_indices = {m.sentence_index for m in llm_mappings}
        for s in sentences:
            if s.index not in existing_indices:
                llm_mappings.append(SentenceNodeMapping(sentence_index=s.index, primary_node=None, node_ids=[], scores={}))
        llm_mappings.sort(key=lambda m: m.sentence_index)
        
        # Validate and improve mapping quality
        validated_mappings = _validate_mapping_quality(llm_mappings, sentences, nodes)
        
        # Handle parent-child relationships: add child sentences to parent nodes
        _add_parent_child_relationships(validated_mappings, nodes)
        
        debug = {
            "model": model,
            "temperature": req.temperature,
            "sentence_count": len(sentences),
            "node_count": len(nodes),
            "mapping_parse_ok": True,
            "missing_nodes_ai_ok": None,
            "fallback_reason": None,
            "raw_mapping_chars": len(raw_mapping or ""),
            "quality_validation": True,
        }
        return SentenceMappingResponse(sentences=sentences, nodes=nodes, mappings=validated_mappings, missing_nodes=[], debug=debug)

    # LLM mapping failed: try heuristic fallback
    print("LLM mapping failed, trying heuristic fallback...")
    heuristic_mappings = _create_heuristic_mappings(sentences, nodes)
    
    # Validate and improve heuristic mappings too
    validated_heuristic_mappings = _validate_mapping_quality(heuristic_mappings, sentences, nodes)
    
    # Handle parent-child relationships for heuristic mappings too
    _add_parent_child_relationships(validated_heuristic_mappings, nodes)
    
    # Check for missing nodes using heuristic approach
    missing_nodes = _compute_zero_overlap_nodes(sentences, nodes)
    
    debug = {
        "model": model,
        "temperature": req.temperature,
        "sentence_count": len(sentences),
        "node_count": len(nodes),
        "mapping_parse_ok": False,
        "missing_nodes_ai_ok": False,
        "fallback_reason": "heuristic_ielts_structure",
        "raw_mapping_chars": len(raw_mapping or ""),
        "raw_missing_chars": 0,
        "quality_validation": True,
    }
    return SentenceMappingResponse(sentences=sentences, nodes=nodes, mappings=validated_heuristic_mappings, missing_nodes=missing_nodes, debug=debug)


def _add_parent_child_relationships(mappings: List[SentenceNodeMapping], nodes: List[NodeInfo]) -> None:
    """Add parent-child relationships: when child nodes are mapped to sentences, 
    also add those sentences to their parent nodes.
    
    Specifically: if sentences are mapped to 'summary', 'results', or 'reference_explanation' nodes,
    also add them to the 'presentation' parent node.
    
    NOTE: This function is now disabled to prevent double-counting in presentation node.
    The presentation node should only count sentences directly mapped to it, not child nodes.
    """
    # DISABLED: This function was causing presentation node to count child node sentences
    # which led to incorrect sentence counts. Presentation should only count direct mappings.
    pass
