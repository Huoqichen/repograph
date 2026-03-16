"use client";

import { startTransition, useEffect, useMemo, useState } from "react";
import { GraphCanvas } from "./graph-canvas";
import { MermaidPreview } from "./mermaid-preview";
import { fetchArchitecture, fetchBranches } from "../lib/api";

const copy = {
  zh: {
    brand: "repomap",
    title: "仓库架构图",
    repoPlaceholder: "GitHub 仓库地址",
    branchPlaceholder: "分支",
    branchAuto: "默认分支",
    branchLoading: "加载分支中",
    submit: "开始分析",
    loading: "分析中",
    graphTitle: "Graph",
    filterTitle: "筛选",
    layoutTitle: "布局",
    layoutForce: "力导向",
    layoutLayered: "分层",
    layoutRadial: "环形",
    searchPlaceholder: "搜索模块 / 路径",
    allLayers: "全部层级",
    allLanguages: "全部语言",
    visible: "显示",
    primary: "语言",
    nodes: "节点",
    edges: "连线",
    layers: "层级",
    detailsTitle: "模块",
    detailsEmpty: "选择节点",
    openSource: "源码",
    internal: "内部依赖",
    external: "外部依赖",
    none: "无",
    listTitle: "Modules",
    mermaidTitle: "Mermaid",
    mermaidCodeTitle: "源码",
    mermaidFallback: "Mermaid 渲染失败，下面保留源码。",
    treeTitle: "Tree",
    languageZh: "中文",
    languageEn: "EN",
    invalidRepo: "请输入有效的 GitHub 仓库地址。",
    backendUnreachable: "后端 API 无法访问，请先启动 Python API。",
    analyzeFailed: "仓库分析失败。",
    branchFailed: "分支读取失败。",
    jobQueued: "任务已排队",
    jobCloning: "正在克隆",
    jobAnalyzingStage: "正在解析",
    jobGraph: "正在构图",
    jobCaching: "正在缓存",
    jobRunning: "正在分析",
    jobCached: "命中缓存",
    jobCompleted: "分析完成"
  },
  en: {
    brand: "repomap",
    title: "Repository Map",
    repoPlaceholder: "GitHub repository URL",
    branchPlaceholder: "Branch",
    branchAuto: "Default branch",
    branchLoading: "Loading branches",
    submit: "Analyze",
    loading: "Analyzing",
    graphTitle: "Graph",
    filterTitle: "Filters",
    layoutTitle: "Layout",
    layoutForce: "Force",
    layoutLayered: "Layered",
    layoutRadial: "Radial",
    searchPlaceholder: "Search modules / paths",
    allLayers: "All layers",
    allLanguages: "All languages",
    visible: "Visible",
    primary: "Language",
    nodes: "Nodes",
    edges: "Edges",
    layers: "Layers",
    detailsTitle: "Module",
    detailsEmpty: "Select a node",
    openSource: "Source",
    internal: "Internal",
    external: "External",
    none: "None",
    listTitle: "Modules",
    mermaidTitle: "Mermaid",
    mermaidCodeTitle: "Source",
    mermaidFallback: "Mermaid rendering failed. The source is still available below.",
    treeTitle: "Tree",
    languageZh: "中文",
    languageEn: "EN",
    invalidRepo: "Please enter a valid GitHub repository URL.",
    backendUnreachable: "Backend API is unreachable. Start the Python API first.",
    analyzeFailed: "Repository analysis failed.",
    branchFailed: "Failed to load branches.",
    jobQueued: "Queued",
    jobCloning: "Cloning",
    jobAnalyzingStage: "Analyzing",
    jobGraph: "Building graph",
    jobCaching: "Caching",
    jobRunning: "Analyzing",
    jobCached: "Cache hit",
    jobCompleted: "Completed"
  }
};

export function RepoWorkbench() {
  const [locale, setLocale] = useState("zh");
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [branches, setBranches] = useState([]);
  const [defaultBranch, setDefaultBranch] = useState("");
  const [result, setResult] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [layerFilter, setLayerFilter] = useState("all");
  const [languageFilter, setLanguageFilter] = useState("all");
  const [layoutMode, setLayoutMode] = useState("force");
  const [jobStatus, setJobStatus] = useState(null);
  const [error, setError] = useState("");
  const [branchError, setBranchError] = useState("");
  const [isPending, setIsPending] = useState(false);
  const [isBranchLoading, setIsBranchLoading] = useState(false);

  const t = copy[locale];
  const architecture = result?.architecture_map;
  const nodes = architecture?.graph?.nodes ?? [];
  const edges = architecture?.graph?.edges ?? [];
  const layers = architecture?.architecture_layers ?? [];
  const modules = architecture?.modules ?? [];

  const selectedModule = useMemo(
    () => modules.find((module) => module.id === selectedNode?.id) ?? null,
    [modules, selectedNode]
  );

  const availableLayers = useMemo(() => layers.map((layer) => layer.name), [layers]);
  const availableLanguages = useMemo(
    () => Array.from(new Set(modules.map((module) => module.language))).sort(),
    [modules]
  );

  const filteredNodes = useMemo(() => {
    const term = searchQuery.trim().toLowerCase();
    return nodes.filter((node) => {
      const matchesLayer = layerFilter === "all" || node.layer === layerFilter;
      const matchesLanguage = languageFilter === "all" || node.language === languageFilter;
      const matchesSearch =
        !term ||
        node.label.toLowerCase().includes(term) ||
        node.path.toLowerCase().includes(term) ||
        node.language.toLowerCase().includes(term);
      return matchesLayer && matchesLanguage && matchesSearch;
    });
  }, [languageFilter, layerFilter, nodes, searchQuery]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map((node) => node.id)), [filteredNodes]);
  const filteredEdges = useMemo(
    () => edges.filter((edge) => filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)),
    [edges, filteredNodeIds]
  );
  useEffect(() => {
    if (!filteredNodes.length) {
      setSelectedNode(null);
      return;
    }
    if (!selectedNode || !filteredNodeIds.has(selectedNode.id)) {
      setSelectedNode(filteredNodes[0]);
    }
  }, [filteredNodeIds, filteredNodes, selectedNode]);

  useEffect(() => {
    let cancelled = false;
    const normalized = repoUrl.trim();

    setBranch("");
    setBranches([]);
    setDefaultBranch("");
    setBranchError("");

    if (!normalized.includes("github.com/")) {
      setIsBranchLoading(false);
      return undefined;
    }

    setIsBranchLoading(true);
    const timer = window.setTimeout(async () => {
      try {
        const payload = await fetchBranches(normalized);
        if (cancelled) {
          return;
        }
        setBranches(payload.branches ?? []);
        setDefaultBranch(payload.default_branch ?? "");
      } catch (requestError) {
        if (!cancelled) {
          setBranchError(localizeBranchError(requestError, locale));
        }
      } finally {
        if (!cancelled) {
          setIsBranchLoading(false);
        }
      }
    }, 350);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [locale, repoUrl]);

  async function handleAnalyze(nextRepoUrl = repoUrl, nextBranch = branch) {
    setIsPending(true);
    setError("");
    setJobStatus(null);

    try {
      const response = await fetchArchitecture(nextRepoUrl.trim(), nextBranch || undefined, (job) => {
        setJobStatus(job);
      });
      startTransition(() => {
        setResult(response);
        setSelectedNode(response.architecture_map.graph.nodes[0] ?? null);
        setJobStatus((currentJob) =>
          currentJob
            ? { ...currentJob, status: "completed", progress: 100, stage: "completed" }
            : currentJob
        );
      });
    } catch (requestError) {
      setError(localizeError(requestError, locale));
    } finally {
      setIsPending(false);
    }
  }

  function onSubmit(event) {
    event.preventDefault();
    void handleAnalyze();
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <span className="brand-mark">{t.brand}</span>
        <div className="lang-switch" role="tablist" aria-label="Language switch">
          <button
            type="button"
            className={locale === "zh" ? "lang-button is-active" : "lang-button"}
            onClick={() => setLocale("zh")}
          >
            {copy.zh.languageZh}
          </button>
          <button
            type="button"
            className={locale === "en" ? "lang-button is-active" : "lang-button"}
            onClick={() => setLocale("en")}
          >
            {copy.en.languageEn}
          </button>
        </div>
      </header>

      <section className="hero-panel hero-minimal">
        <h1>{t.title}</h1>
      </section>

      <section className="panel input-panel">
        <form onSubmit={onSubmit}>
          <div className="form-grid compact-grid">
            <div className="field field-wide">
              <input
                id="repo-url"
                type="url"
                placeholder={t.repoPlaceholder}
                value={repoUrl}
                onChange={(event) => setRepoUrl(event.target.value)}
                required
              />
            </div>
            <div className="field field-branch">
              <select
                id="branch"
                value={branch}
                onChange={(event) => setBranch(event.target.value)}
                disabled={isBranchLoading || (!defaultBranch && branches.length === 0)}
              >
                <option value="">
                  {isBranchLoading
                    ? t.branchLoading
                    : defaultBranch
                      ? `${t.branchAuto} · ${defaultBranch}`
                      : t.branchPlaceholder}
                </option>
                {branches.map((branchName) => (
                  <option key={branchName} value={branchName}>
                    {branchName}
                  </option>
                ))}
              </select>
            </div>
            <button className="submit-button" type="submit" disabled={isPending}>
              {isPending ? t.loading : t.submit}
            </button>
          </div>
        </form>

        {error || branchError ? <p className="status-line">{error || branchError}</p> : null}
        {!error && !branchError && isPending && jobStatus ? (
          <p className="status-line status-line-neutral">{formatJobStatus(jobStatus, locale)}</p>
        ) : null}
      </section>

      {architecture ? (
        <section className="results-grid">
          <article className="panel graph-panel">
            <header className="graph-header compact-header">
              <h2>{t.graphTitle}</h2>
              <div className="stat-row">
                <span className="stat-pill">
                  {t.primary}: {architecture.primary_language ?? t.none}
                </span>
                <span className="stat-pill">
                  {t.nodes}: {result.stats.nodes}
                </span>
                <span className="stat-pill">
                  {t.edges}: {result.stats.edges}
                </span>
                <span className="stat-pill">
                  {t.layers}: {layers.length}
                </span>
                <span className="stat-pill">
                  {t.visible}: {filteredNodes.length}
                </span>
              </div>
            </header>

            <GraphCanvas
              nodes={filteredNodes}
              edges={filteredEdges}
              onSelect={setSelectedNode}
              selectedNodeId={selectedNode?.id}
              layoutMode={layoutMode}
            />

            <footer className="graph-toolbar">
              <span>{architecture.repository_url}</span>
              <span>{architecture.default_branch ?? defaultBranch ?? t.none}</span>
            </footer>
          </article>

          <aside className="sidebar">
            <section className="panel side-section">
              <h3>{t.filterTitle}</h3>
              <div className="filter-grid">
                <input
                  className="filter-input"
                  type="search"
                  placeholder={t.searchPlaceholder}
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                />
                <select className="filter-select" value={layerFilter} onChange={(event) => setLayerFilter(event.target.value)}>
                  <option value="all">{t.allLayers}</option>
                  {availableLayers.map((layerName) => (
                    <option key={layerName} value={layerName}>
                      {layerName}
                    </option>
                  ))}
                </select>
                <select
                  className="filter-select"
                  value={languageFilter}
                  onChange={(event) => setLanguageFilter(event.target.value)}
                >
                  <option value="all">{t.allLanguages}</option>
                  {availableLanguages.map((languageName) => (
                    <option key={languageName} value={languageName}>
                      {languageName}
                    </option>
                  ))}
                </select>
                <select className="filter-select" value={layoutMode} onChange={(event) => setLayoutMode(event.target.value)}>
                  <option value="force">
                    {t.layoutTitle}: {t.layoutForce}
                  </option>
                  <option value="layered">
                    {t.layoutTitle}: {t.layoutLayered}
                  </option>
                  <option value="radial">
                    {t.layoutTitle}: {t.layoutRadial}
                  </option>
                </select>
              </div>
            </section>

            <section className="panel side-section">
              <h3>{t.detailsTitle}</h3>
              {selectedNode && selectedModule ? (
                <div className="module-card" data-active="true">
                  <h4>{selectedNode.label}</h4>
                  <div className="module-meta">
                    <span>{selectedNode.language}</span>
                    <span>{selectedNode.layer}</span>
                  </div>
                  <div className="detail-pairs">
                    <span>
                      {t.internal}: {selectedModule.internal_dependencies.length}
                    </span>
                    <span>
                      {t.external}: {selectedModule.external_dependencies.length}
                    </span>
                  </div>
                  {selectedNode.url ? (
                    <a href={selectedNode.url} target="_blank" rel="noreferrer">
                      {t.openSource}
                    </a>
                  ) : null}
                </div>
              ) : (
                <p>{t.detailsEmpty}</p>
              )}
            </section>

            <section className="panel side-section">
              <h3>{t.listTitle}</h3>
              <div className="module-list">
                {filteredNodes.slice(0, 16).map((node) => (
                  <div className="module-card" data-active={selectedNode?.id === node.id} key={node.id}>
                    <button type="button" onClick={() => setSelectedNode(node)}>
                      <h4>{node.label}</h4>
                      <div className="module-meta">
                        <span>{node.language}</span>
                        <span>{node.layer}</span>
                      </div>
                    </button>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel side-section">
              <h3>{t.treeTitle}</h3>
              <div className="tree-list">
                <TreeNode node={architecture.folder_tree} />
              </div>
            </section>

            <section className="panel side-section">
              <h3>{t.mermaidTitle}</h3>
              <div className="mermaid-stack">
                <div className="mermaid-stack-preview">
                  <MermaidPreview chart={result.mermaid} fallbackLabel={t.mermaidFallback} />
                </div>
                <details className="mermaid-source" open>
                  <summary>{t.mermaidCodeTitle}</summary>
                  <pre className="code-block">{result.mermaid}</pre>
                </details>
              </div>
            </section>
          </aside>
        </section>
      ) : null}
    </main>
  );
}

function TreeNode({ node }) {
  if (!node) {
    return null;
  }

  const children = Array.isArray(node.children) ? node.children : [];
  return (
    <div className="tree-node">
      <strong>{node.name}</strong>
      {children.length ? (
        <ul>
          {children.slice(0, 24).map((child) => (
            <li key={`${node.name}-${child.name}`}>
              {child.type === "directory" ? <TreeNode node={child} /> : <span>{child.name}</span>}
            </li>
          ))}
          {children.length > 24 ? <li>… {children.length - 24} more</li> : null}
        </ul>
      ) : null}
    </div>
  );
}

function localizeError(error, locale) {
  const message = error instanceof Error ? error.message : "";
  if (message.includes("valid GitHub")) {
    return copy[locale].invalidRepo;
  }
  if (message.includes("Backend API is unreachable") || message.includes("后端 API 无法访问")) {
    return copy[locale].backendUnreachable;
  }
  return message || copy[locale].analyzeFailed;
}

function localizeBranchError(error, locale) {
  const message = error instanceof Error ? error.message : "";
  if (message.includes("Backend API is unreachable") || message.includes("后端 API 无法访问")) {
    return copy[locale].backendUnreachable;
  }
  return message || copy[locale].branchFailed;
}

function formatJobStatus(job, locale) {
  const t = copy[locale];
  const labels = {
    queued: t.jobQueued,
    cloning: t.jobCloning,
    analyzing: t.jobAnalyzingStage,
    building_graph: t.jobGraph,
    caching: t.jobCaching,
    running: t.jobRunning,
    cache_hit: t.jobCached,
    completed: t.jobCompleted
  };

  const stageLabel = labels[job.stage] || labels[job.status] || job.stage || job.status;
  const suffix = typeof job.progress === "number" ? ` · ${job.progress}%` : "";
  return `${stageLabel}${job.cached ? ` · ${t.jobCached}` : ""}${suffix}`;
}
