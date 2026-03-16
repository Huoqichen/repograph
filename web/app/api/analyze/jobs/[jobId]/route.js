import { NextResponse } from "next/server";

const API_BASE_URL = process.env.REPOMAP_API_URL || process.env.NEXT_PUBLIC_REPOMAP_API_URL || "http://127.0.0.1:8000";

export async function GET(_request, { params }) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/analyze/jobs/${params.jobId}`, {
      cache: "no-store"
    });
    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      {
        detail:
          "Backend API is unreachable. Start the Python API or set REPOMAP_API_URL correctly. / 后端 API 无法访问，请启动 Python API 或正确配置 REPOMAP_API_URL。"
      },
      { status: 502 }
    );
  }
}
