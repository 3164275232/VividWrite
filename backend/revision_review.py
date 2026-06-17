from fastapi import APIRouter
from pydantic import BaseModel
import re
from typing import Optional, Dict, List, Any

router = APIRouter()

# ---------------- Revision Review (Vocabulary / Grammar / Coherence + Overall) -----------------
class RevisionReviewIn(BaseModel):
    text: str
    flowchart: dict | None = None
    deplot_text: Optional[str] = None
    # mode retained for compatibility but only 'llm' is honored now
    mode: str | None = None

class RevisionReviewOut(BaseModel):
    success: bool
    overall: dict | None = None  # {vocabulary:{}, grammar:{}, coherence:{}, summary:str}
    suggestions: list | None = None  # flattened suggestions (legacy + convenience)
    suggestions_by_category: Dict[str, List[dict]] | None = None  # new grouped structure {vocabulary:[...], grammar:[...], coherence:[...]}
    error: str | None = None
    prompt_used: str | None = None  # for debugging future LLM integration (optional)
    used_model: str | None = None

WEAK_WORDS = ["very", "really", "a lot", "many", "nice", "good", "bad", "big", "small"]
COHESIVE_MARKERS = ["however", "therefore", "moreover", "overall", "in conclusion", "furthermore", "consequently"]

def _char_ranges(text: str, pattern: str):
    for m in re.finditer(pattern, text, flags=re.IGNORECASE):
        yield (m.start(), m.end())

def heuristic_revision_review(payload: RevisionReviewIn) -> RevisionReviewOut:  # Deprecated path
    return RevisionReviewOut(success=False, error="Heuristic mode disabled; provide OPENAI_API_KEY for LLM review.")


def call_llm_revision_review(payload: RevisionReviewIn) -> RevisionReviewOut:
    """Invoke OpenAI (or compatible) model to produce structured JSON.
    Expected JSON structure now supports grouped categories and per-suggestion single excerpt + replacement:
    {
      overall: { vocabulary:{score,comment}, grammar:{score,comment}, coherence:{score,comment}, summary: str },
      suggestions_by_category: { vocabulary:[Suggestion], grammar:[Suggestion], coherence:[Suggestion] },
      suggestions: [Suggestion]? // optional flat list (legacy)
    }
    Suggestion = {
        id: string,
        category?: 'vocabulary'|'grammar'|'coherence',
        message: string,
        severity: 'low'|'medium'|'high',
        excerpt: string,          # verbatim span from original text
        replacement: string,      # proposed improved wording (single replacement for that excerpt)
        note?: string
    }
    Backend resolves excerpt -> character range (range / ranges[0]).
    """
    import os, json, re as _re
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return RevisionReviewOut(success=False, error="Missing OPENAI_API_KEY environment variable.")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        system_prompt = (
            "You are an IELTS Task 1 writing reviewer. Return STRICT JSON ONLY — no prose outside JSON. "
            "SCHEMA: {overall:{vocabulary:{score,comment}, grammar:{score,comment}, coherence:{score,comment}, summary:string}, suggestions_by_category:{vocabulary:[Suggestion], grammar:[Suggestion], coherence:[Suggestion]}, suggestions:[Suggestion]?}. "
            "Suggestion = {id:string, message:string, severity:'low'|'medium'|'high', category?:'vocabulary'|'grammar'|'coherence', excerpt:string, replacement:string, note?:string}. "
            "IMPORTANT: Each suggestion should focus on ONE specific issue but can provide MULTIPLE improvement points within that issue. "
            "For example, if a sentence has both vocabulary and grammar issues, create separate suggestions for each. "
            "If a paragraph has multiple problems, create multiple suggestions rather than combining them.\n"
            "EXCERPT RULE: 'excerpt' must be a verbatim contiguous substring from the essay (identical casing, punctuation, spacing). Do NOT fabricate/paraphrase/alter.\n"
            "REPLACEMENT RULE: Keep same grammatical role and tense unless improvement requires minimal adjustment. Avoid adding new facts. If issue is structural (e.g., long sentence), replacement may show a refined shorter clause or a corrected form; still reflect only the selected excerpt span.\n"
            "Holistic / paragraph-level feedback must still pick one representative sentence or phrase as excerpt.\n"
            "Do NOT output character indices; backend will locate them.\n"
            "QUALITY ADAPTATION: Weaker writing → more suggestions (3-5 per category); strong writing → only 2–3 high-impact refinements per category (avoid repetition). Each suggestion must target a distinct issue.\n"
            "SEVERITY: 'high' only for errors that significantly harm meaning, accuracy, or task fulfillment.\n"
            "ID: concise unique token. Message: actionable, specific. Note: optional extra context.\n"
            "SCORING: 5.0–9.0 in 0.5 steps; align score and comment.\n"
            "OVERALL.summary INSTRUCTION: Instead of a narrative summary, output 3–6 numbered structural improvement recommendations (no leading prose) focusing ONLY on global organization. Format: \"1) <issue> – <actionable structural fix>\". Each item should reference flowchart node titles (if provided) or inferred logical parts (e.g., 'overview', 'body 1', 'body 2'). Cover: missing / under-developed elements, ordering / progression, balance (length or detail), cohesion / transitions, redundancy. Do not restate data details; give structural change guidance. If structure is already strong, provide 2–3 fine‑grained refinement points.\n"
            "OUTPUT: exactly one valid JSON object. No commentary outside JSON."
        )
        user_payload = {
            "text": payload.text,
            "flowchart": payload.flowchart,
            "deplot_text": payload.deplot_text,
        }
        completion = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"DATA:\n{json.dumps(user_payload, ensure_ascii=False)}"}
            ],
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        print(f"AI model raw response: {content}")
        data = json.loads(content)
        print(f"Parsed JSON data: {json.dumps(data, indent=2, ensure_ascii=False)}")
        # ----- Reconcile grouped + flat suggestions -----
        suggestions: List[Dict[str, Any]] = []
        grouped: Dict[str, List[dict]] | None = None
        raw_grouped = data.get("suggestions_by_category")
        if isinstance(raw_grouped, dict):
            # copy only expected categories; keep others but don't lose data
            grouped = {}
            for cat, arr in raw_grouped.items():
                if isinstance(arr, list):
                    grouped[cat] = arr
            # inject expected categories if missing
            for required_cat in ("vocabulary", "grammar", "coherence"):
                grouped.setdefault(required_cat, [])
            # flatten
            for cat, arr in grouped.items():
                for item in arr:
                    if not isinstance(item, dict):
                        continue
                    item.setdefault("category", cat)
                    suggestions.append(item)
        # If also a legacy flat list is provided, merge (avoid duplicate ids)
        legacy_list = data.get("suggestions")
        if isinstance(legacy_list, list):
            seen_ids = {s.get("id") for s in suggestions if isinstance(s, dict)}
            for item in legacy_list:
                if not isinstance(item, dict):
                    continue
                if item.get("id") in seen_ids:
                    continue
                suggestions.append(item)
        # fall back: if neither present
        if not suggestions:
            suggestions = []
        # If grouped structure absent, reconstruct based on flattened suggestions' category
        if grouped is None:
            grouped = {"vocabulary": [], "grammar": [], "coherence": []}
            for s in suggestions:
                cat = s.get("category")
                if cat in grouped:
                    grouped[cat].append(s)
        raw_text = payload.text
        used_spans: list[tuple[int,int]] = []  # to reduce heavy overlap across suggestions

        def span_overlaps(a_start: int, a_end: int) -> bool:
            for b_start, b_end in used_spans:
                # allow small overlaps (<3 chars) to not block minor punctuation reuse
                intersection = min(a_end, b_end) - max(a_start, b_start)
                if intersection > 2:
                    return True
            return False

        def register_span(st: int, ed: int):
            used_spans.append((st, ed))

        # Precompute normalized version of raw text for fuzzy fallback
        def normalize_spaces(s: str) -> str:
            return re.sub(r"\s+", " ", s.strip())

        raw_text_norm = normalize_spaces(raw_text).lower()
        # Map from normalized window to original indices is non-trivial; we'll fuzzy locate then refine by approximate original substring search.

        for s in suggestions:
            # Accept unified model: either 'excerpt' (preferred) or 'excerpts' (array) or legacy keys.
            excerpt_value = None
            if isinstance(s.get("excerpt"), str):
                excerpt_value = s.get("excerpt")
            else:
                ex_list = s.get("excerpts")
                if isinstance(ex_list, str):
                    excerpt_value = ex_list
                elif isinstance(ex_list, list) and ex_list:
                    excerpt_value = ex_list[0]
                else:
                    legacy_txt = s.get("text") or s.get("snippet") or s.get("excerpt")
                    if isinstance(legacy_txt, str):
                        excerpt_value = legacy_txt
            if not excerpt_value or not isinstance(excerpt_value, str) or not excerpt_value.strip():
                s["no_range"] = True
                # normalize outward shape
                s["excerpts"] = [excerpt_value] if excerpt_value else []
                continue
            candidate = excerpt_value
            stripped = candidate.strip()
            if raw_text.find(candidate) == -1 and raw_text.find(stripped) != -1:
                candidate = stripped
            # direct search (non-overlapping requirement maintained)
            search_start = 0
            found_idx = -1
            while True:
                idx = raw_text.find(candidate, search_start)
                if idx == -1:
                    break
                span = (idx, idx + len(candidate))
                if not span_overlaps(*span):
                    found_idx = idx
                    break
                else:
                    search_start = idx + 1
            span_dict = None
            if found_idx != -1:
                st, ed = found_idx, found_idx + len(candidate)
                span_dict = {"start": st, "end": ed}
                register_span(st, ed)
            else:
                # fuzzy fallback
                cand_norm = normalize_spaces(candidate).lower()
                if len(cand_norm) >= 3:
                    norm_idx = raw_text_norm.find(cand_norm)
                    if norm_idx != -1:
                        best_span = None
                        approx_len = max(len(candidate) - 4, len(cand_norm))
                        max_window = min(len(raw_text), approx_len + 20)
                        anchor = re.escape(cand_norm[:3])
                        for m in re.finditer(anchor, raw_text, flags=re.IGNORECASE):
                            base_start = m.start()
                            for extra in range(0, 25):
                                end_pos = base_start + approx_len + extra
                                if end_pos > len(raw_text):
                                    break
                                window = raw_text[base_start:end_pos]
                                if normalize_spaces(window).lower() == cand_norm:
                                    if not span_overlaps(base_start, end_pos):
                                        best_span = (base_start, end_pos)
                                        break
                            if best_span:
                                break
                        if best_span:
                            st, ed = best_span
                            span_dict = {"start": st, "end": ed, "fuzzy": True}
                            register_span(st, ed)
            if span_dict is None:
                s["no_range"] = True
            else:
                s["ranges"] = [span_dict]
                s["range"] = span_dict
            # normalize excerpt fields for output consistency
            s["excerpt"] = excerpt_value
            s["excerpts"] = [excerpt_value]

        overall = data.get("overall")
        # --- Post-process overall.summary to ensure one recommendation per line ---
        if overall and isinstance(overall, dict):
            summary_val = overall.get("summary")
            if isinstance(summary_val, str):
                raw_summary = summary_val.strip()
                # If already contains newlines, keep but normalize multiple blank lines
                import re as _re2
                if '\n' not in raw_summary:
                    # Attempt to split enumerated items like: 1) ... 2) ... 3) ...
                    parts = _re2.split(r'(\d+\)\s*)', raw_summary)
                    lines = []
                    i = 0
                    while i < len(parts):
                        token = parts[i]
                        if _re2.fullmatch(r'\d+\)\s*', token):
                            enumerator = token.strip() + ' '
                            content = ''
                            if i + 1 < len(parts):
                                content = parts[i+1].strip()
                            if content:
                                lines.append(f"{enumerator}{content}")
                            else:
                                lines.append(enumerator.rstrip())
                            i += 2
                        else:
                            # Leading text without enumerator: include as its own line if meaningful
                            stripped = token.strip()
                            if stripped:
                                lines.append(stripped)
                            i += 1
                    if lines:
                        raw_summary = '\n'.join(lines)
                else:
                    # Normalize existing lines: remove excessive spaces
                    raw_summary = '\n'.join([l.strip() for l in raw_summary.splitlines() if l.strip()])
                overall['summary'] = raw_summary
        print(f"Final suggestions count: {len(suggestions)}")
        print(f"Suggestions by category: {json.dumps({k: len(v) for k, v in (grouped or {}).items()}, ensure_ascii=False)}")
        return RevisionReviewOut(success=True, overall=overall, suggestions=suggestions, suggestions_by_category=grouped, prompt_used=system_prompt, used_model=model)
    except Exception as e:
        return RevisionReviewOut(success=False, error=f"LLM failed: {e}")

@router.post("/api/revision-review", response_model=RevisionReviewOut)
def revision_review(payload: RevisionReviewIn):
    mode = (payload.mode or "auto").lower()
    # Always force LLM path; heuristic disabled.
    return call_llm_revision_review(payload)
