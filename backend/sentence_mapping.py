"""Backward-compatible adapter for the structure feedback orchestrator.

New clients should call ``/api/analyze-structure``. Existing callers of
``/api/map-sentences`` keep the original response fields and also receive the
new paragraph mappings, integrated feedback, and agent trace.
"""
from structure_feedback_agents import (
    MissingNodeInfo,
    NodeInfo,
    ParagraphInfo,
    ParagraphMapping,
    SentenceInfo,
    SentenceNodeMapping,
    StructureAnalysisRequest,
    StructureAnalysisResponse,
    StructureFeedbackOrchestrator,
    extract_nodes as _extract_nodes,
    split_paragraphs_and_sentences,
    split_sentences,
)


SentenceMappingRequest = StructureAnalysisRequest
SentenceMappingResponse = StructureAnalysisResponse


def map_sentences(req: SentenceMappingRequest) -> SentenceMappingResponse:
    """Run the Task 1 multi-agent pipeline through the legacy function name."""
    return StructureFeedbackOrchestrator(
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    ).analyze(req)


__all__ = [
    "MissingNodeInfo",
    "NodeInfo",
    "ParagraphInfo",
    "ParagraphMapping",
    "SentenceInfo",
    "SentenceMappingRequest",
    "SentenceMappingResponse",
    "SentenceNodeMapping",
    "_extract_nodes",
    "map_sentences",
    "split_paragraphs_and_sentences",
    "split_sentences",
]
