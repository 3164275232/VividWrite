from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import json
from typing import Optional, Tuple
from next_sentence import (
    NextSentenceRequest,
    NextSentenceResponse,
    generate_next_sentence,
)
from bar import GraphGenerator as BarGraphGenerator
from pie import GraphGenerator as PieGraphGenerator
from sentence_mapping import (
    SentenceMappingRequest,
    SentenceMappingResponse,
    map_sentences,
)
from deplot_extractor import extract_table_from_image_deplot
from sample_essay import router as sample_essay_router
from revision_review import router as revision_review_router

app = FastAPI()

# Include modular routers
app.include_router(sample_essay_router)
app.include_router(revision_review_router)

# Allow CORS from frontend dev server (Vite default 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建静态文件目录
os.makedirs("generated_charts", exist_ok=True)
os.makedirs("uploaded_images", exist_ok=True)
os.makedirs("user_data", exist_ok=True)  # NEW root for per-user data

# 挂载静态文件服务
app.mount("/charts", StaticFiles(directory="generated_charts"), name="charts")
app.mount("/uploads", StaticFiles(directory="uploaded_images"), name="uploads")

# ---- 健康检查（可选）----
@app.get("/health")
def health():
    return {"status": "ok"}

# ---- Example frontend GET endpoint ----
@app.get("/api/hello")
def hello():
    return {"message": "Hello from Python FastAPI!"}

# ---- Example: parameterized GET ----
@app.get("/api/greet")
def greet(name: str = "Anonymous"):
    return {"greeting": f"Hello, {name}!"}

# ---- 示例：POST JSON ----
class EchoIn(BaseModel):
    text: str

class EchoOut(BaseModel):
    length: int
    upper: str

@app.post("/api/echo", response_model=EchoOut)
def echo(payload: EchoIn):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="text cannot be empty")
    return {"length": len(payload.text), "upper": payload.text.upper()}

# ---- 图表分析API ----
class ChartAnalysisRequest(BaseModel):
    chart_type: str  # "bar" or "pie"
    requirement: str
    student_answer: str
    deplot_text: str  # renamed from deplot_data for consistency with next-sentence
    image_path: Optional[str] = None

class ChartAnalysisResponse(BaseModel):
    success: bool
    chart_data: Optional[dict] = None
    chart_url: Optional[str] = None
    revision_suggestions: Optional[list] = None
    error: Optional[str] = None

"""Next sentence endpoint imports models & logic from next_sentence.py"""

@app.post("/api/analyze-chart", response_model=ChartAnalysisResponse)
def analyze_chart(request: ChartAnalysisRequest):
    try:
        # Select proper generator based on chart type
        if request.chart_type == "bar":
            generator = BarGraphGenerator()
        elif request.chart_type == "pie":
            generator = PieGraphGenerator()
        else:
            raise HTTPException(status_code=400, detail="Unsupported chart type")
        
        # 生成图表
        result = generator.call_gpt_and_generate(
            initial_instruction="Analyze the student's answer and generate visual feedback",
            requirement=request.requirement,
            student_answer=request.student_answer,
            image_path=request.image_path,
            output_format="json",
            output_path=f"generated_charts/{request.chart_type}_chart_{generator.data_counter}.png",
            deplot_txt=request.deplot_text
        )
        
        if "error" in result:
            return ChartAnalysisResponse(
                success=False,
                error=result["error"]
            )
        
        # 生成修订建议
        revision_suggestions = generate_revision_suggestions(result, request.student_answer)
        
        # 生成图表URL
        chart_url = f"/charts/{request.chart_type}_chart_{generator.data_counter}.png"
        
        return ChartAnalysisResponse(
            success=True,
            chart_data=result,
            chart_url=chart_url,
            revision_suggestions=revision_suggestions
        )
        
    except Exception as e:
        return ChartAnalysisResponse(
            success=False,
            error=str(e)
        )

def generate_revision_suggestions(chart_data: dict, student_answer: str) -> list:
    """Generate revision suggestions based on chart data and student answer."""
    suggestions = []
    
    # Check data completeness
    if chart_data.get("chart_type") == "pie":
        total_percentage = sum(chart_data.get("series", [{}])[0].get("values", []))
        if total_percentage < 100:
            suggestions.append({
                "type": "data_completeness",
                "message": f"Data incomplete: total percentage is {total_percentage}%, consider adding the missing portions",
                "severity": "medium"
            })
    
    # Check estimated values
    estimated_values = chart_data.get("style", {}).get("estimated_values", [])
    if estimated_values:
        suggestions.append({
            "type": "data_accuracy",
            "message": f"Detected {len(estimated_values)} estimated value(s); provide more precise data if possible",
            "severity": "low"
        })
    
    # Check multi-series structure clarity
    if chart_data.get("chart_type") == "bar":
        series_count = len(chart_data.get("series", []))
        if series_count > 1:
            suggestions.append({
                "type": "structure",
                "message": f"Chart contains {series_count} data series; compare them more clearly in your description",
                "severity": "low"
            })
    
    # Check length requirement
    if len(student_answer.split()) < 150:
        suggestions.append({
            "type": "length",
            "message": "Answer may be under 150 words; add more details and comparisons",
            "severity": "medium"
        })
    
    return suggestions


@app.post("/api/next-sentence", response_model=NextSentenceResponse)
def next_sentence(req: NextSentenceRequest):
    try:
        # req.deplot_text (optional): textual chart extraction now incorporated into prompt
        return generate_next_sentence(req)
    except Exception as e:
        return NextSentenceResponse(error=str(e))

@app.post("/api/map-sentences", response_model=SentenceMappingResponse)
def map_sentences_endpoint(req: SentenceMappingRequest):
    """Map each sentence in current_text to relevant flowchart nodes.

    Returns sentence list with character offsets and mapping objects. Falls back
    to heuristic mapping if LLM JSON cannot be parsed.
    """
    try:
        return map_sentences(req)
    except Exception as e:
        return SentenceMappingResponse(error=str(e))

# ---- DePlot image data extraction API ----
@app.post("/api/deplot-extract")
async def deplot_extract(image: UploadFile = File(...)):
    """Receive chart image, run DePlot model to extract underlying table text.

    Returns:
        {"extracted_text": str, "image_id": str, "filename": str}
    Newlines are encoded as <0x0A> for compatibility with existing frontend / next-sentence prompt formatting.
    """
    try:
        # Ensure upload directory exists
        upload_folder = "uploaded_images"
        os.makedirs(upload_folder, exist_ok=True)
        import uuid
        file_extension = image.filename.split('.')[-1] if '.' in image.filename else 'png'
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        image_path = os.path.join(upload_folder, unique_filename)
    # Persist uploaded file
        with open(image_path, "wb") as f:
            f.write(await image.read())
    # Invoke DePlot
        raw_text = extract_table_from_image_deplot(image_path) or ""
    # Normalize newlines -> <0x0A> (keep consistent with frontend hard-coded examples)
        normalized = raw_text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<0x0A>')
        return {
            "extracted_text": normalized,
            "image_id": unique_filename,
            "filename": image.filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DePlot extraction failed: {e}")

# ---- 示例：上传文件（前端 <input type="file">）----
@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    # 这里只演示接收，不落盘；真实业务按需处理
    content = await file.read()
    return {"filename": file.filename, "size": len(content)}

# ---- Chart analysis API with image upload ----
@app.post("/api/analyze-chart-with-image", response_model=ChartAnalysisResponse)
async def analyze_chart_with_image(
    image: UploadFile = File(...),
    chart_type: str = Form(...),
    requirement: str = Form(...),
    student_answer: str = Form(...),
    deplot_text: Optional[str] = Form(None),  # new preferred field
    deplot_data: Optional[str] = Form(None),  # backward compatibility
):
    try:
    # Save uploaded image
        upload_folder = "uploaded_images"
        os.makedirs(upload_folder, exist_ok=True)
        
    # Generate unique filename
        import uuid
        file_extension = image.filename.split('.')[-1] if '.' in image.filename else 'png'
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        image_path = os.path.join(upload_folder, unique_filename)
        
    # Write image file to disk
        with open(image_path, "wb") as buffer:
            content = await image.read()
            buffer.write(content)
        
    # Select generator based on chart type
        if chart_type == "bar":
            generator = BarGraphGenerator()
        elif chart_type == "pie":
            generator = PieGraphGenerator()
        else:
            raise HTTPException(status_code=400, detail="Unsupported chart type")
        
        # 生成图表
        # choose available textual data (prefer new name)
        _txt = deplot_text if (deplot_text and deplot_text.strip()) else (deplot_data or "")
        result = generator.call_gpt_and_generate(
            initial_instruction="Analyze the student's answer and generate visual feedback",
            requirement=requirement,
            student_answer=student_answer,
            image_path=image_path,
            output_format="json",
            output_path=f"generated_charts/{chart_type}_chart_{generator.data_counter}.png",
            deplot_txt=_txt
        )
        
        if "error" in result:
            return ChartAnalysisResponse(
                success=False,
                error=result["error"]
            )
        
        # 生成修订建议
        revision_suggestions = generate_revision_suggestions(result, student_answer)
        
        # 生成图表URL
        chart_url = f"/charts/{chart_type}_chart_{generator.data_counter}.png"
        
        return ChartAnalysisResponse(
            success=True,
            chart_data=result,
            chart_url=chart_url,
            revision_suggestions=revision_suggestions
        )
        
    except Exception as e:
        return ChartAnalysisResponse(
            success=False,
            error=str(e)
        )

@app.post("/api/save-final-image")
async def save_final_image(username: str = Form(...), image: UploadFile = File(...)):
    """Persist the final accepted image when user enters drafting stage.
    Stores under user_data/<username>/drafting_image_<timestamp>.<ext>
    Returns saved path relative to server root.
    """
    try:
        if not username.strip():
            raise HTTPException(status_code=400, detail="username required")
        import time, uuid
        safe_user = username.strip().replace('..', '_').replace('/', '_').replace('\\', '_')
        user_dir = os.path.join('user_data', safe_user)
        os.makedirs(user_dir, exist_ok=True)
        # keep single newest? we store with timestamp so history retained
        ext = image.filename.split('.')[-1] if '.' in image.filename else 'png'
        fname = f"drafting_image_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}" 
        path = os.path.join(user_dir, fname)
        with open(path, 'wb') as f:
            f.write(await image.read())
        return {"success": True, "path": path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RevisionTextIn(BaseModel):
    username: str
    text: str

class RevisionTextOut(BaseModel):
    success: bool
    path: str | None = None
    error: str | None = None

@app.post("/api/save-revision-text", response_model=RevisionTextOut)
async def save_revision_text(payload: RevisionTextIn):
    """Save full text when user clicks Analyze Text during revision stage.
    File: user_data/<username>/revision_<timestamp>.txt
    """
    try:
        if not payload.username.strip():
            return RevisionTextOut(success=False, error="username required")
        safe_user = payload.username.strip().replace('..', '_').replace('/', '_').replace('\\', '_')
        user_dir = os.path.join('user_data', safe_user)
        os.makedirs(user_dir, exist_ok=True)
        import time
        fname = f"revision_{int(time.time())}.txt"
        path = os.path.join(user_dir, fname)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(payload.text or '')
        return RevisionTextOut(success=True, path=path)
    except Exception as e:
        return RevisionTextOut(success=False, error=str(e))

