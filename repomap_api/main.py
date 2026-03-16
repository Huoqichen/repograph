from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from repomap_api.config import get_settings
from repomap_api.jobs import get_job_manager
from repomap_api.schemas import AnalyzeJobResponse, AnalyzeRequest, AnalyzeResponse, BranchListResponse
from repomap_api.service import analyze_remote_repository
from repomap.repository import list_remote_branches

settings = get_settings()
job_manager = get_job_manager(
    max_workers=settings.max_async_workers,
    job_ttl_seconds=settings.job_ttl_seconds,
)
app = FastAPI(
    title="repomap API",
    description="Analyze a GitHub repository and return an interactive architecture graph model.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in settings.cors_origins else settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/branches", response_model=BranchListResponse)
def branches(repo_url: str = Query(..., description="GitHub repository URL.")) -> BranchListResponse:
    if "github.com/" not in repo_url:
        raise HTTPException(status_code=400, detail="Only GitHub repository URLs are supported.")

    try:
        default_branch, branch_names = list_remote_branches(repo_url)
        return BranchListResponse(default_branch=default_branch, branches=branch_names)
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Branch lookup failed: {error}") from error


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    repo_url = str(payload.repo_url)
    if "github.com/" not in repo_url:
        raise HTTPException(status_code=400, detail="Only GitHub repository URLs are supported.")

    try:
        return analyze_remote_repository(
            repo_url=repo_url,
            branch=payload.branch,
            clone_dir=settings.clone_dir,
            cache_dir=settings.cache_dir,
            cache_ttl_seconds=settings.cache_ttl_seconds,
        )
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Analysis failed: {error}") from error


@app.post("/api/analyze/jobs", response_model=AnalyzeJobResponse, status_code=202)
def submit_analysis_job(payload: AnalyzeRequest) -> AnalyzeJobResponse:
    repo_url = str(payload.repo_url)
    if "github.com/" not in repo_url:
        raise HTTPException(status_code=400, detail="Only GitHub repository URLs are supported.")

    return job_manager.submit(
        repo_url=repo_url,
        branch=payload.branch,
        clone_dir=settings.clone_dir,
        cache_dir=settings.cache_dir,
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )


@app.get("/api/analyze/jobs/{job_id}", response_model=AnalyzeJobResponse)
def get_analysis_job(job_id: str) -> AnalyzeJobResponse:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found.")
    return job
