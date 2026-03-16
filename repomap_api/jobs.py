from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from repomap_api.schemas import AnalyzeJobResponse, AnalyzeResponse
from repomap_api.service import analyze_remote_repository


@dataclass(slots=True)
class AnalysisJob:
    id: str
    repo_url: str
    branch: str | None
    status: str = "queued"
    progress: int = 0
    stage: str | None = "queued"
    cached: bool = False
    result: AnalyzeResponse | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_schema(self) -> AnalyzeJobResponse:
        return AnalyzeJobResponse(
            id=self.id,
            repo_url=self.repo_url,
            branch=self.branch,
            status=self.status,
            progress=self.progress,
            stage=self.stage,
            cached=self.cached,
            result=self.result,
            error=self.error,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class AnalysisJobManager:
    def __init__(self, max_workers: int = 2, job_ttl_seconds: int = 7200) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="repomap-job")
        self._job_ttl_seconds = job_ttl_seconds
        self._jobs: dict[str, AnalysisJob] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        repo_url: str,
        branch: str | None,
        clone_dir: str | None,
        cache_dir: str | None,
        cache_ttl_seconds: int,
    ) -> AnalyzeJobResponse:
        job = AnalysisJob(id=uuid.uuid4().hex, repo_url=repo_url, branch=branch)
        with self._lock:
            self._purge_expired_locked()
            self._jobs[job.id] = job
        self._executor.submit(
            self._run_job,
            job.id,
            repo_url,
            branch,
            clone_dir,
            cache_dir,
            cache_ttl_seconds,
        )
        return job.to_schema()

    def get(self, job_id: str) -> AnalyzeJobResponse | None:
        with self._lock:
            self._purge_expired_locked()
            job = self._jobs.get(job_id)
            return job.to_schema() if job else None

    def _run_job(
        self,
        job_id: str,
        repo_url: str,
        branch: str | None,
        clone_dir: str | None,
        cache_dir: str | None,
        cache_ttl_seconds: int,
    ) -> None:
        self._update(job_id, status="running", progress=5, stage="queued")
        try:
            result = analyze_remote_repository(
                repo_url=repo_url,
                branch=branch,
                clone_dir=clone_dir,
                cache_dir=cache_dir,
                cache_ttl_seconds=cache_ttl_seconds,
                progress_callback=lambda stage, progress: self._on_progress(job_id, stage, progress),
            )
        except Exception as error:  # noqa: BLE001
            self._update(job_id, status="failed", progress=100, stage="failed", error=str(error))
            return

        cached = False
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            cached = job.cached

        self._update(
            job_id,
            status="completed",
            progress=100,
            stage="completed",
            result=result,
            cached=cached,
        )

    def _on_progress(self, job_id: str, stage: str, progress: int) -> None:
        updates: dict[str, object] = {
            "stage": stage,
            "progress": progress,
        }
        if stage == "cache_hit":
            updates["cached"] = True
            updates["status"] = "running"
        elif stage != "completed":
            updates["status"] = "running"
        self._update(job_id, **updates)

    def _update(self, job_id: str, **updates: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for key, value in updates.items():
                setattr(job, key, value)
            job.updated_at = time.time()

    def _purge_expired_locked(self) -> None:
        if self._job_ttl_seconds <= 0:
            return
        now = time.time()
        expired_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job.status in {"completed", "failed"} and now - job.updated_at > self._job_ttl_seconds
        ]
        for job_id in expired_ids:
            self._jobs.pop(job_id, None)


_JOB_MANAGER: AnalysisJobManager | None = None
_JOB_MANAGER_LOCK = threading.Lock()


def get_job_manager(max_workers: int = 2, job_ttl_seconds: int = 7200) -> AnalysisJobManager:
    global _JOB_MANAGER
    with _JOB_MANAGER_LOCK:
        if _JOB_MANAGER is None:
            _JOB_MANAGER = AnalysisJobManager(max_workers=max_workers, job_ttl_seconds=job_ttl_seconds)
        return _JOB_MANAGER
