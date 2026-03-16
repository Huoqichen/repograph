from fastapi.testclient import TestClient
from pathlib import Path

from repomap_api.main import app
from repomap_api.schemas import AnalyzeResponse, GraphStats
from repomap_api.service import analyze_remote_repository


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_branches_endpoint(monkeypatch) -> None:
    def fake_list_remote_branches(repo_url: str) -> tuple[str | None, list[str]]:
        assert repo_url == "https://github.com/Huoqichen/repomap"
        return "main", ["main", "dev"]

    monkeypatch.setattr("repomap_api.main.list_remote_branches", fake_list_remote_branches)

    response = client.get("/api/branches", params={"repo_url": "https://github.com/Huoqichen/repomap"})

    assert response.status_code == 200
    assert response.json() == {
        "default_branch": "main",
        "branches": ["main", "dev"],
    }


def test_analyze_remote_repository_uses_cache(tmp_path: Path, monkeypatch) -> None:
    calls = {"count": 0}

    def fake_clone_repository(repo_url: str, clone_root=None, branch=None):
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        return repo_path, True

    def fake_detect_git_branch(repo_path: Path):
        return "main"

    def fake_analyze_repository(repo_path: Path, repo_url: str, default_branch: str | None = None):
        calls["count"] += 1
        return type(
            "FakeAnalysis",
            (),
            {
                "repository_url": repo_url,
                "root_path": repo_path,
                "default_branch": default_branch,
                "tree": {"name": "repo", "type": "directory", "children": []},
                "modules": [],
                "detected_languages": [],
                "primary_language": None,
                "architecture_layers": [],
            },
        )()

    def fake_build_dependency_graph(_analysis):
        class FakeGraph:
            def number_of_nodes(self):
                return 0

            def number_of_edges(self):
                return 0

        return FakeGraph()

    def fake_build_architecture_map(analysis, _graph):
        return {
            "repository_url": analysis.repository_url,
            "root_path": str(analysis.root_path),
            "default_branch": analysis.default_branch,
            "primary_language": analysis.primary_language,
            "detected_languages": [],
            "architecture_layers": [],
            "folder_tree": analysis.tree,
            "modules": [],
            "graph": {"nodes": [], "edges": []},
        }

    monkeypatch.setattr("repomap_api.service.clone_repository", fake_clone_repository)
    monkeypatch.setattr("repomap_api.service.detect_git_branch", fake_detect_git_branch)
    monkeypatch.setattr("repomap_api.service.analyze_repository", fake_analyze_repository)
    monkeypatch.setattr("repomap_api.service.build_dependency_graph", fake_build_dependency_graph)
    monkeypatch.setattr("repomap_api.service.build_architecture_map", fake_build_architecture_map)
    monkeypatch.setattr("repomap_api.service.graph_to_mermaid", lambda _graph: "flowchart LR")

    cache_dir = tmp_path / "cache"
    response_one = analyze_remote_repository(
        repo_url="https://github.com/Huoqichen/repomap",
        branch="main",
        cache_dir=str(cache_dir),
        cache_ttl_seconds=3600,
    )
    response_two = analyze_remote_repository(
        repo_url="https://github.com/Huoqichen/repomap",
        branch="main",
        cache_dir=str(cache_dir),
        cache_ttl_seconds=3600,
    )

    assert isinstance(response_one, AnalyzeResponse)
    assert isinstance(response_two, AnalyzeResponse)
    assert response_one.stats == GraphStats(nodes=0, edges=0, layers=0)
    assert calls["count"] == 1


def test_async_analysis_job_endpoint(monkeypatch) -> None:
    fake_result = AnalyzeResponse(
        architecture_map={
            "repository_url": "https://github.com/Huoqichen/repomap",
            "root_path": "/tmp/repo",
            "default_branch": "main",
            "primary_language": "Python",
            "detected_languages": [],
            "architecture_layers": [],
            "folder_tree": {"name": "repo", "type": "directory", "children": []},
            "modules": [],
            "graph": {"nodes": [], "edges": []},
        },
        mermaid="flowchart LR",
        stats=GraphStats(nodes=0, edges=0, layers=0),
    )

    class FakeManager:
        def submit(self, repo_url, branch, clone_dir, cache_dir, cache_ttl_seconds):
            assert repo_url == "https://github.com/Huoqichen/repomap"
            assert branch == "main"
            return {
                "id": "job-1",
                "repo_url": repo_url,
                "branch": branch,
                "status": "queued",
                "progress": 0,
                "stage": "queued",
                "cached": False,
                "result": None,
                "error": None,
                "created_at": 1.0,
                "updated_at": 1.0,
            }

        def get(self, job_id):
            if job_id != "job-1":
                return None
            return {
                "id": "job-1",
                "repo_url": "https://github.com/Huoqichen/repomap",
                "branch": "main",
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "cached": True,
                "result": fake_result.model_dump(),
                "error": None,
                "created_at": 1.0,
                "updated_at": 2.0,
            }

    monkeypatch.setattr("repomap_api.main.job_manager", FakeManager())

    submit_response = client.post(
        "/api/analyze/jobs",
        json={"repo_url": "https://github.com/Huoqichen/repomap", "branch": "main"},
    )
    job_response = client.get("/api/analyze/jobs/job-1")

    assert submit_response.status_code == 202
    assert submit_response.json()["status"] == "queued"
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"
    assert job_response.json()["cached"] is True
