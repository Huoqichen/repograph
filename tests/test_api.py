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
        assert repo_url == "https://github.com/Huoqichen/repograph"
        return "main", ["main", "dev"]

    monkeypatch.setattr("repomap_api.main.list_remote_branches", fake_list_remote_branches)

    response = client.get("/api/branches", params={"repo_url": "https://github.com/Huoqichen/repograph"})

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
