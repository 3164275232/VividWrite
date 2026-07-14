import sys
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from deplot_extractor import extract_table_from_image_deplot
from hybrid_feedback import HybridFeedbackService
from next_sentence import NextSentenceRequest, NextSentenceResponse, generate_next_sentence
from paths import CHARTS_DIR, UPLOADS_DIR, ensure_runtime_directories
from revision_review import router as revision_review_router
from sample_essay import router as sample_essay_router
from sentence_mapping import SentenceMappingRequest, SentenceMappingResponse, map_sentences
from storage import (
    relative_runtime_path,
    save_uploaded_file,
    save_user_image,
    save_user_revision,
)


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

ensure_runtime_directories()

app = FastAPI(title="VividWrite API", version="0.2.0")
app.include_router(sample_essay_router)
app.include_router(revision_review_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/charts", StaticFiles(directory=CHARTS_DIR), name="charts")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


class ChartAnalysisResponse(BaseModel):
    success: bool
    chart_data: Optional[dict] = None
    chart_url: Optional[str] = None
    revision_suggestions: Optional[list] = None
    error: Optional[str] = None


class RevisionTextIn(BaseModel):
    username: str
    text: str


class RevisionTextOut(BaseModel):
    success: bool
    path: str | None = None
    error: str | None = None


def generate_revision_suggestions(chart_data: dict, student_answer: str) -> list[dict]:
    records = chart_data.get("records") if isinstance(chart_data.get("records"), list) else []
    suggestions = []

    missing_count = sum(1 for record in records if record.get("missing"))
    if missing_count:
        suggestions.append({
            "type": "data_completeness",
            "message": f"Your answer leaves {missing_count} item(s) from the original chart unspecified.",
            "severity": "medium",
        })

    estimated_count = sum(1 for record in records if record.get("estimated"))
    if estimated_count:
        suggestions.append({
            "type": "data_accuracy",
            "message": f"The visual feedback contains {estimated_count} inferred value(s); use exact figures where possible.",
            "severity": "low",
        })

    series_count = len({record.get("series") for record in records if record.get("series")})
    if series_count > 1:
        suggestions.append({
            "type": "structure",
            "message": f"The chart contains {series_count} series; make their comparisons explicit.",
            "severity": "low",
        })

    if len(student_answer.split()) < 150:
        suggestions.append({
            "type": "length",
            "message": "Answer may be under 150 words; add more details and comparisons",
            "severity": "medium",
        })
    return suggestions


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/next-sentence", response_model=NextSentenceResponse)
def next_sentence(request: NextSentenceRequest):
    try:
        return generate_next_sentence(request)
    except Exception as exc:
        return NextSentenceResponse(error=str(exc))


@app.post("/api/map-sentences", response_model=SentenceMappingResponse)
def map_sentences_endpoint(request: SentenceMappingRequest):
    try:
        return map_sentences(request)
    except Exception as exc:
        return SentenceMappingResponse(error=str(exc))


@app.post("/api/deplot-extract")
async def deplot_extract(
    image: UploadFile = File(...),
    chart_type: Optional[str] = Form(None),
):
    try:
        image_path = await save_uploaded_file(image, UPLOADS_DIR)
        raw_text = await run_in_threadpool(
            extract_table_from_image_deplot,
            str(image_path),
            chart_type,
        ) or ""
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<0x0A>")
        return {
            "extracted_text": normalized,
            "image_id": image_path.name,
            "filename": image.filename,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DePlot extraction failed: {exc}") from exc


@app.post("/api/analyze-chart-with-image", response_model=ChartAnalysisResponse)
async def analyze_chart_with_image(
    image: UploadFile = File(...),
    chart_type: str = Form(...),
    requirement: str = Form(...),
    student_answer: str = Form(...),
    deplot_text: Optional[str] = Form(None),
    deplot_data: Optional[str] = Form(None),
):
    try:
        image_path = await save_uploaded_file(image, UPLOADS_DIR)
        extracted_text = deplot_text if deplot_text and deplot_text.strip() else (deplot_data or "")
        service = HybridFeedbackService(CHARTS_DIR)
        result, filename = await run_in_threadpool(
            service.generate,
            chart_type=chart_type,
            requirement=requirement,
            student_answer=student_answer,
            deplot_text=extracted_text,
            image_path=str(image_path),
        )
        return ChartAnalysisResponse(
            success=True,
            chart_data=result,
            chart_url=f"/charts/{filename}",
            revision_suggestions=generate_revision_suggestions(result, student_answer),
        )
    except Exception as exc:
        return ChartAnalysisResponse(success=False, error=str(exc))


@app.post("/api/save-final-image")
async def save_final_image(username: str = Form(...), image: UploadFile = File(...)):
    try:
        path = await save_user_image(username, image)
        return {"success": True, "path": relative_runtime_path(path)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/save-revision-text", response_model=RevisionTextOut)
def save_revision_text(payload: RevisionTextIn):
    try:
        path = save_user_revision(payload.username, payload.text)
        return RevisionTextOut(success=True, path=relative_runtime_path(path))
    except ValueError as exc:
        return RevisionTextOut(success=False, error=str(exc))
    except Exception as exc:
        return RevisionTextOut(success=False, error=str(exc))
