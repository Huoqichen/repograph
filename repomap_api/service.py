from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Callable

from repomap.analyzer import analyze_repository
from repomap.graph import build_architecture_map, build_dependency_graph, graph_to_mermaid
from repomap.repository import cleanup_clone, clone_repository, detect_git_branch
from repomap_api.schemas import AnalyzeResponse, GraphStats

ProgressCallback = Callable[[str, int], None]


def analyze_remote_repository(
    repo_url: str,
    branch: str | None = None,
    clone_dir: str | None = None,
    cache_dir: str | None = None,
    cache_ttl_seconds: int = 86400,
    progress_callback: ProgressCallback | None = None,
) -> AnalyzeResponse:
    cloned_path: Path | None = None
    temporary_clone = False
    cache_path = _cache_path_for_request(repo_url, branch, cache_dir)
    cached_response = _read_cached_response(cache_path, cache_ttl_seconds)
    if cached_response is not None:
        _notify_progress(progress_callback, "cache_hit", 100)
        return cached_response

    try:
        _notify_progress(progress_callback, "cloning", 15)
        target_dir = Path(clone_dir).expanduser() if clone_dir else None
        cloned_path, temporary_clone = clone_repository(repo_url, clone_root=target_dir, branch=branch)
        detected_branch = branch or detect_git_branch(cloned_path)
        _notify_progress(progress_callback, "analyzing", 55)
        analysis = analyze_repository(cloned_path, repo_url, default_branch=detected_branch)
        _notify_progress(progress_callback, "building_graph", 78)
        graph = build_dependency_graph(analysis)
        architecture_map = build_architecture_map(analysis, graph)
        mermaid = graph_to_mermaid(graph)

        response = AnalyzeResponse(
            architecture_map=architecture_map,
            mermaid=mermaid,
            stats=GraphStats(
                nodes=graph.number_of_nodes(),
                edges=graph.number_of_edges(),
                layers=len(analysis.architecture_layers),
            ),
        )
        _notify_progress(progress_callback, "caching", 92)
        _write_cached_response(cache_path, response)
        _notify_progress(progress_callback, "completed", 100)
        return response
    finally:
        if cloned_path and temporary_clone:
            cleanup_clone(cloned_path.parent)


def _notify_progress(progress_callback: ProgressCallback | None, stage: str, progress: int) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, progress)


def _cache_path_for_request(repo_url: str, branch: str | None, cache_dir: str | None) -> Path:
    base_dir = Path(cache_dir).expanduser() if cache_dir else Path(__file__).resolve().parents[1] / ".codex-temp-cache" / "analysis-cache"
    request_key = hashlib.sha256(f"{repo_url}::{branch or ''}".encode("utf-8")).hexdigest()
    return base_dir / f"{request_key}.json"


def _read_cached_response(cache_path: Path, ttl_seconds: int) -> AnalyzeResponse | None:
    if not cache_path.exists():
        return None
    if ttl_seconds > 0:
        age_seconds = time.time() - cache_path.stat().st_mtime
        if age_seconds > ttl_seconds:
            return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return AnalyzeResponse.model_validate(payload)


def _write_cached_response(cache_path: Path, response: AnalyzeResponse) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(response.model_dump_json(indent=2), encoding="utf-8")
