# VividWrite

VividWrite is a research prototype for IELTS Academic Writing Task 1. It turns
the source task image and a student's report into visual and textual feedback.

## Project layout

```text
VividWrite/
|-- backend/                 FastAPI API and model services
|   |-- main.py              HTTP routes only
|   |-- paths.py             Runtime directory definitions
|   |-- storage.py           Upload and user-file persistence
|   |-- hybrid_feedback.py   Statistical/spatial renderer routing
|   |-- chart_*.py           DeepSeek and Vega-Lite statistical pipeline
|   |-- wan_image_renderer.py  Wan map/process pipeline
|   |-- spatial_sample_essay.py  Qwen vision map/process sample essays
|   `-- tests/               Backend unit tests
|-- frontend/                React and Vite application
|   `-- src/
|       |-- api.js           All backend requests
|       |-- utils/           Shared task-type rules
|       `-- *.jsx            UI components
|-- docs/                    Architecture documentation
`-- test_samples/            Manual end-to-end fixtures
```

Runtime files under `backend/uploaded_images`, `backend/generated_charts`, and
`backend/user_data` are intentionally ignored by Git. Existing local files are
not deleted when the application is updated.

## Backend setup

```powershell
cd D:\Study\Research\VividWrite\backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add the DeepSeek and Alibaba Cloud credentials to `backend/.env`, then start:

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The health endpoint is `http://127.0.0.1:8000/health`. API documentation is at
`http://127.0.0.1:8000/docs`.

## Frontend setup

Open a second terminal:

```powershell
cd D:\Study\Research\VividWrite\frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The frontend defaults to the backend at
`http://127.0.0.1:8000`; override it with `VITE_API_BASE` in `frontend/.env`.

## Verification

```powershell
cd backend
.\venv\Scripts\python.exe -m unittest discover -s tests -v

cd ..\frontend
npm run build
npm run lint
```

See `test_samples/TEST_GUIDE.md` for the manual visual-feedback test pack.
