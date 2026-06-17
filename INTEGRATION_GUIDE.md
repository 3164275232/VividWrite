# VividWrite 2.0 Integration Guide

## Overview

VividWrite 2.0 integrates chart analysis capabilities (from v1.0) and separates feedback into two main parts:

1. **Visual Feedback** – Visualization generated from the student's answer
2. **Revision Suggestions** – Improvement recommendations derived from chart + answer analysis

## Architecture

### Backend (FastAPI)
- **main.py**: Core API server with chart analysis endpoints
- **bar.py**: Bar chart generator (analyzes related student responses)
- **pie.py**: Pie chart generator

### Frontend (React)
- **App.jsx**: Main application component (tabs & interactions)
- **api.js**: API helper functions including chart analysis calls

## New Features

### 1. Chart Analysis API
```
POST /api/analyze-chart
```

**Request Body:**
```json
{
  "chart_type": "bar" | "pie",
  "requirement": "Task requirement text",
  "student_answer": "Student answer raw text",
  "deplot_data": "(optional legacy) extracted chart text",
  "image_path": "(optional)"
}
```

**Response:**
```json
{
  "success": true,
  "chart_data": {"...": "..."},
  "chart_url": "/charts/chart.png",
  "revision_suggestions": [ ... ],
  "error": null
}
```

### 2. Frontend UI Updates

#### Button / View Structure
- **Flowchart**: IELTS Task 1 writing structure guidance
- **Visual Feedback**: Generated chart data & visualization
- **Revision Suggestions**: Analysis-based improvement advice

#### Analyze Button
- Added "Analyze Text" in the writing panel
- Calls backend and displays state/errors

### 3. Revision Suggestion Types

The system can produce suggestions of these categories:

- **Data Completeness** (`data_completeness`)
- **Data Accuracy** (`data_accuracy`)
- **Structure** (`structure`)
- **Length Requirement** (`length`)

## Usage

### 1. Start Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### 2. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

### 3. Workflow
1. Log in
2. Open Flowchart to plan structure
3. Enter student answer
4. (Upload chart image if using image-based analysis)
5. Click "Analyze Text"
6. View Visual Feedback
7. Open Revision Suggestions for improvements

## Configuration

### Environment Variables
- `OPENAI_API_KEY` – Required for GPT-based analysis

### Static Files
- Generated charts saved in `backend/generated_charts/`
- Served via `/charts/`

## Extensibility

### Add a New Chart Type
1. Create a new generator class in `backend/`
2. Add handling logic in `main.py`
3. Update frontend chart type selector

### Customize Suggestions
Modify `generate_revision_suggestions()` to extend logic.

## Notes

1. Ensure OpenAI key configured
2. Chart generation may take several seconds
3. Monitor disk usage for generated images
4. Add robust logging & error handling for production
