import sys
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auth import authentication_middleware, router as auth_router
from deplot_extractor import extract_table_from_image_deplot
from hybrid_feedback import HybridFeedbackService
from move_feedback import move_catalog
from next_sentence import NextSentenceRequest, NextSentenceResponse, generate_next_sentence
from paths import CHARTS_DIR, UPLOADS_DIR, ensure_runtime_directories
from revision_review import router as revision_review_router
from sample_essay import SampleEssayResponse, router as sample_essay_router
from spatial_sample_essay import generate_spatial_sample_essay
from storage import (
    relative_runtime_path,
    save_uploaded_file,
    save_user_image,
    save_user_revision,
)
from task_image_detection import (
    HIGH_CONFIDENCE_THRESHOLD,
    SPATIAL_TASK_TYPES,
    STATISTICAL_TASK_TYPES,
    SUPPORTED_TASK_TYPES,
    TaskImageDetectionError,
    classify_task_image,
)


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

ensure_runtime_directories()

app = FastAPI(title="VividWrite API", version="0.2.0")
app.include_router(auth_router)
app.include_router(sample_essay_router)
app.include_router(revision_review_router)
app.middleware("http")(authentication_middleware)
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


class TaskImagePreparationResponse(BaseModel):
    success: bool
    image_id: str | None = None
    filename: str | None = None
    task_type: str
    confidence: float
    detection_source: str
    needs_confirmation: bool
    deplot_text: str | None = None
    error: str | None = None


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

    move_feedback = chart_data.get("move_feedback")
    assessments = (
        move_feedback.get("assessments")
        if isinstance(move_feedback, dict)
        else None
    )
    if isinstance(assessments, list):
        for assessment in assessments:
            if not isinstance(assessment, dict) or assessment.get("status") != "developing":
                continue
            suggestions.append({
                "type": assessment.get("code", "rhetorical_move"),
                "message": assessment.get("hint") or "Review how this rhetorical move supports the report.",
                "severity": "medium",
            })
    else:
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

    incorrect_count = sum(1 for record in records if record.get("incorrect"))
    if incorrect_count and not isinstance(assessments, list):
        suggestions.append({
            "type": "data_accuracy",
            "message": f"Your answer contains {incorrect_count} pie-chart value(s) that differ from the original chart.",
            "severity": "high",
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


def _normalize_deplot_response_text(raw_text: str) -> str:
    return raw_text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<0x0A>")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/move-framework")
def move_framework() -> dict:
    return move_catalog()


def _attach_move_visual_urls(chart_data: dict) -> None:
    feedback = chart_data.get("move_feedback")
    assessments = feedback.get("assessments") if isinstance(feedback, dict) else None
    if not isinstance(assessments, list):
        return
    for assessment in assessments:
        visual = assessment.get("visual") if isinstance(assessment, dict) else None
        filename = visual.get("image_filename") if isinstance(visual, dict) else None
        if filename:
            visual["image_url"] = f"/charts/{filename}"


@app.post("/api/next-sentence", response_model=NextSentenceResponse)
def next_sentence(request: NextSentenceRequest):
    try:
        return generate_next_sentence(request)
    except Exception as exc:
        return NextSentenceResponse(error=str(exc))


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
        normalized = _normalize_deplot_response_text(raw_text)
        return {
            "extracted_text": normalized,
            "image_id": image_path.name,
            "filename": image.filename,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DePlot extraction failed: {exc}") from exc


@app.post("/api/prepare-task-image", response_model=TaskImagePreparationResponse)
async def prepare_task_image(
    image: UploadFile = File(...),
    chart_type: str = Form("auto"),
    extract_deplot: bool = Form(False),
):
    image_path = await save_uploaded_file(image, UPLOADS_DIR)
    selected_type = (chart_type or "auto").strip().lower()

    if selected_type != "auto":
        task_type = selected_type if selected_type in SUPPORTED_TASK_TYPES else "unknown"
        needs_confirmation = task_type == "unknown"
        deplot_text = None
        if extract_deplot and task_type in STATISTICAL_TASK_TYPES:
            try:
                raw_text = await run_in_threadpool(
                    extract_table_from_image_deplot,
                    str(image_path),
                    task_type,
                ) or ""
                deplot_text = _normalize_deplot_response_text(raw_text)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"DePlot extraction failed: {exc}") from exc
        return TaskImagePreparationResponse(
            success=True,
            image_id=image_path.name,
            filename=image.filename,
            task_type=task_type,
            confidence=1.0 if not needs_confirmation else 0.0,
            detection_source="manual",
            needs_confirmation=needs_confirmation,
            deplot_text=deplot_text,
        )

    try:
        classification = await run_in_threadpool(classify_task_image, str(image_path))
    except TaskImageDetectionError as exc:
        return TaskImagePreparationResponse(
            success=True,
            image_id=image_path.name,
            filename=image.filename,
            task_type="unknown",
            confidence=0.0,
            detection_source="qwen-vision-error",
            needs_confirmation=True,
            deplot_text=None,
            error=str(exc),
        )

    task_type = classification.task_type
    needs_confirmation = (
        task_type == "unknown"
        or classification.confidence < HIGH_CONFIDENCE_THRESHOLD
        or task_type not in (STATISTICAL_TASK_TYPES | SPATIAL_TASK_TYPES)
    )
    deplot_text = None
    if extract_deplot and not needs_confirmation and task_type in STATISTICAL_TASK_TYPES:
        try:
            raw_text = await run_in_threadpool(
                extract_table_from_image_deplot,
                str(image_path),
                task_type,
            ) or ""
            deplot_text = _normalize_deplot_response_text(raw_text)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"DePlot extraction failed: {exc}") from exc

    return TaskImagePreparationResponse(
        success=True,
        image_id=image_path.name,
        filename=image.filename,
        task_type=task_type,
        confidence=classification.confidence,
        detection_source=classification.detection_source,
        needs_confirmation=needs_confirmation,
        deplot_text=deplot_text,
        error=None if not needs_confirmation else classification.reason or None,
    )


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
        _attach_move_visual_urls(result)
        return ChartAnalysisResponse(
            success=True,
            chart_data=result,
            chart_url=f"/charts/{filename}",
            revision_suggestions=generate_revision_suggestions(result, student_answer),
        )
    except Exception as exc:
        return ChartAnalysisResponse(success=False, error=str(exc))


@app.post("/api/generate-spatial-sample-essay", response_model=SampleEssayResponse)
async def spatial_sample_essay(
    image: UploadFile = File(...),
    chart_type: str = Form(...),
    requirement: str = Form(""),
    min_words: int = Form(150),
):
    try:
        image_path = await save_uploaded_file(image, UPLOADS_DIR)
        return await run_in_threadpool(
            generate_spatial_sample_essay,
            image_path=image_path,
            chart_type=chart_type,
            requirement=requirement,
            min_words=min_words,
        )
    except Exception as exc:
        return SampleEssayResponse(success=False, error=str(exc))


@app.post("/api/save-final-image")
async def save_final_image(
    request: Request,
    username: str = Form(...),
    image: UploadFile = File(...),
):
    try:
        authenticated_user = getattr(request.state, "username", None)
        path = await save_user_image(authenticated_user or username, image)
        return {"success": True, "path": relative_runtime_path(path)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/save-revision-text", response_model=RevisionTextOut)
def save_revision_text(request: Request, payload: RevisionTextIn):
    try:
        authenticated_user = getattr(request.state, "username", None)
        path = save_user_revision(authenticated_user or payload.username, payload.text)
        return RevisionTextOut(success=True, path=relative_runtime_path(path))
    except ValueError as exc:
        return RevisionTextOut(success=False, error=str(exc))
    except Exception as exc:
        return RevisionTextOut(success=False, error=str(exc))
