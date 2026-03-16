from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AnalyzeRequest(BaseModel):
    repo_url: HttpUrl = Field(description="GitHub repository URL to analyze.")
    branch: str | None = Field(default=None, description="Optional branch name.")


class GraphStats(BaseModel):
    nodes: int
    edges: int
    layers: int


class BranchListResponse(BaseModel):
    default_branch: str | None
    branches: list[str]


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    architecture_map: dict
    mermaid: str
    stats: GraphStats


class AnalyzeJobResponse(BaseModel):
    id: str
    repo_url: HttpUrl
    branch: str | None = None
    status: str
    progress: int = 0
    stage: str | None = None
    cached: bool = False
    result: AnalyzeResponse | None = None
    error: str | None = None
    created_at: float
    updated_at: float
