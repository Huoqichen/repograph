<div align="center">
  <h1>repomap</h1>
  <p><strong>Turn any GitHub repository into an architecture diagram.</strong></p>
  <p>
    Analyze GitHub repositories with a Python engine, FastAPI backend, and Next.js + D3.js web UI.
  </p>
  <p>
    <a href="https://github.com/Huoqichen/repograph/stargazers"><img src="https://img.shields.io/github/stars/Huoqichen/repograph?style=flat-square" alt="Stars" /></a>
    <a href="https://github.com/Huoqichen/repograph/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License" /></a>
    <img src="https://img.shields.io/badge/platform-Python%20%7C%20Web-green?style=flat-square" alt="Platform" />
  </p>
  <p>
    <a href="./README.md">English</a> |
    <a href="./docs/README.zh-CN.md">简体中文</a>
  </p>
</div>

---

## Introduction

`repomap` is a repository architecture explorer built around a Python analysis engine, a FastAPI backend, and a Next.js + D3.js frontend. It clones a GitHub repository, scans the source tree, detects dependencies, infers architecture layers, and renders the result as a folder tree, a JSON graph, a Mermaid diagram, and an interactive web graph.

It is designed for developers who want to understand an unfamiliar codebase quickly without manually tracing imports, packages, and directory structure.

## Features

- Analyze GitHub repositories from both CLI and Web UI
- Automatically detect Python, JavaScript, and Go
- Parse dependencies and build graphs with `networkx`
- Infer top-level architecture layers:
  `Frontend`, `Backend`, `Database`, `Infrastructure`, `Shared`
- Export folder tree, JSON, and Mermaid output
- Render an interactive graph in the browser with D3.js
- Proxy frontend requests through Next.js to avoid common local `Failed to fetch` issues
- Support `allowedDevOrigins` for LAN-based Next.js development
- Provide production-ready deployment files for Vercel and Docker

## Demo

CLI:

```bash
repomap https://github.com/user/repo
repomap https://github.com/user/repo --branch main
repomap https://github.com/user/repo --json-out architecture.json --mermaid-out architecture.mmd
```

Web:

```bash
cp .env.api.example .env
uvicorn repomap_api.main:app --reload --host 0.0.0.0 --port 8000

cd web
cp .env.example .env.local
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

How it works:

```mermaid
flowchart LR
    A["GitHub URL"] --> B["Clone repository"]
    B --> C["Scan folder structure"]
    C --> D["Detect languages"]
    D --> E["Parse imports and packages"]
    E --> F["Build dependency graph"]
    F --> G["Infer architecture layers"]
    G --> H["Tree view"]
    G --> I["JSON output"]
    G --> J["Mermaid output"]
    G --> K["Interactive web graph"]
```

## Installation

Requirements:

- Python 3.11+
- Git
- Node.js 20+

Install Python dependencies:

```bash
python -m pip install -e .
```

Install frontend dependencies:

```bash
cd web
npm install
```

## Usage

CLI usage:

```bash
repomap https://github.com/user/repo
```

CLI options:

```text
repomap [OPTIONS] REPO_URL

Arguments:
  REPO_URL

Options:
  --branch TEXT
  --clone-dir PATH
  --json-out PATH
  --mermaid-out PATH
  --keep-clone
  --help
```

Web environment example:

```env
REPOMAP_API_URL=http://127.0.0.1:8000
ALLOWED_DEV_ORIGINS=localhost,127.0.0.1,192.168.164.1
```

## Example Output

Folder tree:

```text
repo
├── api
│   ├── handlers.py
│   └── routes.py
├── core
│   ├── service.py
│   └── utils.py
├── db
│   ├── models.py
│   └── migrations
└── web
    ├── components
    └── app.tsx
```

JSON:

```json
{
  "primary_language": "Python",
  "architecture_layers": [
    { "name": "Frontend", "module_count": 6 },
    { "name": "Backend", "module_count": 18 },
    { "name": "Database", "module_count": 4 }
  ]
}
```

Mermaid:

```mermaid
flowchart LR
    subgraph Frontend["Frontend"]
        UI["web/app"]
    end
    subgraph Backend["Backend"]
        API["api.routes"]
        CORE["core.service"]
    end
    subgraph Database["Database"]
        DB["db.models"]
    end
    UI --> API
    API --> CORE
    CORE --> DB
```

## Architecture

Project layout:

```text
repomap/
├── repomap/        # Core analysis engine
├── repomap_api/    # FastAPI backend
├── web/            # Next.js + D3.js frontend
├── docs/           # Localized documentation
├── Dockerfile.api
└── docker-compose.yml
```

System flow:

```mermaid
flowchart LR
    USER["Browser / CLI User"] --> WEB["Next.js Web UI"]
    USER --> CLI["repomap CLI"]
    WEB --> PROXY["Next.js /api/analyze proxy"]
    PROXY --> API["FastAPI backend"]
    CLI --> ENGINE["Python analysis engine"]
    API --> ENGINE
    ENGINE --> GIT["GitHub repository"]
```

Key modules:

- `repomap/`: repository scanning, parsing, layer inference, graph generation
- `repomap_api/`: HTTP API for analysis
- `web/`: interactive frontend
- `web/app/api/analyze/route.js`: same-origin proxy route for local and production web usage
- `docs/README.zh-CN.md`: Simplified Chinese documentation

## Deployment

Frontend on Vercel:

1. Import the repository into Vercel
2. Set `Root Directory` to `web`
3. Set `REPOMAP_API_URL` to your backend API URL
4. Deploy

Backend with Docker:

```bash
docker build -f Dockerfile.api -t repomap-api .
docker run --rm -p 8000:8000 --env-file .env repomap-api
```

Full stack with Docker Compose:

```bash
docker compose up --build
```

## Contributing

Contributions are welcome. Good next steps include:

- more language support
- stronger monorepo dependency resolution
- caching and background jobs for large repositories
- graph filtering, search, and layout improvements

---

## Documentation Languages

- [English](./README.md)
- [简体中文](./docs/README.zh-CN.md)

## Star History

<p align="center">
  <img src="./public/repomap.png" alt="repomap icon" width="28" />
  <strong>Star History</strong>
</p>

<p align="center">
  <a href="https://star-history.com/#Huoqichen/repograph&Date">
    <img src="https://api.star-history.com/svg?repos=Huoqichen/repograph&type=Date" alt="Star History Chart" />
  </a>
</p>
