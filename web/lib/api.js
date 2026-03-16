export async function fetchArchitecture(repoUrl, branch, onProgress) {
  if (!repoUrl.includes("github.com/")) {
    throw new Error("Please enter a valid GitHub repository URL. / 请输入有效的 GitHub 仓库地址。");
  }

  const submitResponse = await fetch("/api/analyze/jobs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      repo_url: repoUrl,
      branch: branch || null
    })
  });

  const submittedJob = await submitResponse.json().catch(() => ({}));
  if (!submitResponse.ok) {
    throw new Error(submittedJob.detail || "Failed to analyze repository. / 仓库分析失败。");
  }

  onProgress?.(submittedJob);
  let currentJob = submittedJob;

  while (currentJob.status === "queued" || currentJob.status === "running") {
    await sleep(1200);
    const jobResponse = await fetch(`/api/analyze/jobs/${currentJob.id}`, {
      cache: "no-store"
    });
    const jobPayload = await jobResponse.json().catch(() => ({}));
    if (!jobResponse.ok) {
      throw new Error(jobPayload.detail || "Failed to analyze repository. / 仓库分析失败。");
    }
    currentJob = jobPayload;
    onProgress?.(currentJob);
  }

  if (currentJob.status !== "completed" || !currentJob.result) {
    throw new Error(currentJob.error || "Failed to analyze repository. / 仓库分析失败。");
  }

  return currentJob.result;
}

export async function fetchBranches(repoUrl) {
  if (!repoUrl.includes("github.com/")) {
    return { default_branch: null, branches: [] };
  }

  const params = new URLSearchParams({ repo_url: repoUrl });
  const response = await fetch(`/api/branches?${params.toString()}`, {
    cache: "no-store"
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to load branches. / 分支加载失败。");
  }

  return payload;
}

function sleep(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
