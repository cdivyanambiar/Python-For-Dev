import logging
from contextlib import asynccontextmanager
from threading import Lock
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import DB_PATH, DOCS_PATH, MODEL_PATH
from app.database import initialize_database
from app.model import OllamaModel
from app.retrieval import DocumentIndex
from app.workflow import CopilotWorkflow

logger = logging.getLogger(__name__)
jobs: dict[str, dict] = {}
jobs_lock = Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database(DB_PATH)
    app.state.workflow = CopilotWorkflow(OllamaModel(), DocumentIndex(DOCS_PATH, MODEL_PATH), DB_PATH)
    yield


app = FastAPI(title="Switch Copilot Prototype", lifespan=lifespan)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def process_job(job_id: str, question: str, workflow: CopilotWorkflow) -> None:
    try:
        result = workflow.run(question)
        job = {"status": "completed", "result": result}
    except Exception:
        logger.exception("Job %s failed", job_id)
        job = {"status": "failed", "error": "Processing failed. Check the server logs for details."}
    with jobs_lock:
        jobs[job_id] = job


@app.post("/questions", status_code=202)
def submit_question(body: Question, request: Request, background_tasks: BackgroundTasks):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be blank.")
    job_id = str(uuid4())
    with jobs_lock:
        jobs[job_id] = {"status": "pending"}
    background_tasks.add_task(process_job, job_id, question, request.app.state.workflow)
    return {"job_id": job_id, "status": "pending"}


@app.get("/questions/{job_id}")
def get_question(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"job_id": job_id, **job}
