# 🤖 AI Code Reviewer

[![CI/CD Pipeline](https://github.com/[your-username]/ai-code-reviewer/actions/workflows/ci.yml/badge.svg)](https://github.com/[your-username]/ai-code-reviewer/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-green.svg)](https://www.sqlalchemy.org/)

> **Automated GitHub Pull Request Analysis using Google Gemini AI.**
> Login with GitHub, select a repository and PR, clone/index code locally, and receive expert-level PR + deep repository review feedback.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🐙 **GitHub Integration** | Login with GitHub OAuth; browse repos and open PRs |
| ⚡ **AI-Powered Reviews** | Structured analysis via Google Gemini (bugs, security, performance, quality) |
| 📥 **Clone + Index Pipeline** | Selected PR is cloned to local workspace and indexed before deep analysis |
| 🧩 **Connected Report Pages** | Every deep report page includes connected documentation: what is happening, what is wrong, impact, and actions |
| 📊 **Confidence Score** | Every review includes a 1–10 reliability score |
| 💬 **Post to GitHub** | One-click: post the AI review as a PR comment |
| 📜 **Review History** | All reviews persisted via SQLAlchemy with pagination |
| 🏥 **Health Endpoint** | `/health` for monitoring and Docker healthchecks |
| 📖 **Auto API Docs** | Swagger UI at `/api/docs` |

---

## 🖼️ Architecture

```
Browser (Vanilla JS SPA)
        │ HTTP/JSON
        ▼
FastAPI Backend ──────── GitHub API (PyGithub)
        │           └─── Google Gemini API
        ▼
        SQLAlchemy DB
(SQLite by default)
```

For full diagrams (DFD, ERD, Sequence, Class, Use Case), see:
📄 [`docs/diagrams/architecture.md`](./docs/diagrams/architecture.md)
📄 [`docs/diagrams/frontend_dashboard_architecture.md`](./docs/diagrams/frontend_dashboard_architecture.md)

---

## 📁 Project Structure

```
ai-code-reviewer/
├── backend/                  # FastAPI application
│   ├── main.py               # Routes, middleware, lifecycle
│   ├── github_service.py     # GitHub API wrapper
│   ├── ai_service.py         # Gemini AI + prompt engineering
│   ├── database.py           # MongoDB CRUD layer
│   ├── config.py             # Environment configuration
│   ├── requirements.txt      # Python dependencies
│   └── .env.example          # Environment variable template
├── frontend/                 # Vanilla JS SPA
│   ├── index.html            # Application structure
│   ├── app.js                # Application logic
│   └── style.css             # Design system (dark mode, glassmorphism)
├── tests/                    # Test suite (112+ test cases)
│   ├── conftest.py           # Shared fixtures and mocks
│   ├── test_integration.py   # API endpoint tests
│   ├── test_regression.py    # Contract regression tests
│   └── test_mutation.py      # Boundary condition tests
├── docker/
│   └── Dockerfile            # Multi-stage production image
├── .github/
│   └── workflows/
│       └── ci.yml            # 4-stage CI/CD pipeline
├── docs/
│   ├── PROJECT_REPORT.md     # Full academic report
│   └── diagrams/
│       └── architecture.md   # All system diagrams
├── docker-compose.yml        # Multi-service orchestration
└── pytest.ini                # Test configuration
```

---

## 🚀 Quick Start

### Option A: Docker Compose (Recommended)

```bash
# 1. Clone
git clone https://github.com/[your-username]/ai-code-reviewer.git
cd ai-code-reviewer

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env — add your tokens

# 3. Run (from project root, not docker/ directory)
docker compose up --build

# 4. Open
# Login:      http://localhost:8000/login
# Dashboard:  http://localhost:8000/dashboard
# API Docs:   http://localhost:8000/api/docs
```

### Option B: Local Development

```bash
# Prerequisites: Python 3.11+

cd ai-code-reviewer

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env

# Run backend
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Open http://localhost:8000
```

---

## 🔑 Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in:

| Variable | Description | Required |
|---|---|---|
| `GITHUB_TOKEN` | Optional fallback PAT for non-session API use | Optional |
| `GOOGLE_API_KEY` | Google AI Studio API Key | ✅ Yes |
| `GITHUB_CLIENT_ID` | GitHub OAuth app client id | ✅ Yes |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth app client secret | ✅ Yes |
| `GITHUB_REDIRECT_URI` | OAuth callback URL (default `http://localhost:8000/auth/github/callback`) | ✅ Yes |
| `DATABASE_URL` | SQLAlchemy connection string (default `sqlite:///./data/ai_code_reviewer.db`) | Optional |
| `ANALYSIS_WORKDIR` | Folder for local cloned repositories (default `./data/repos`) | Optional |
| `APP_ENV` | Environment (`development`/`production`) | Optional |

**Getting tokens:**
- **GitHub PAT:** [github.com/settings/tokens/new](https://github.com/settings/tokens/new) → select `repo` and `read:user`
- **Google API Key:** [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

---

## 🧪 Testing

The project includes **112+ test cases** across 3 test files.

### Run All Tests

```bash
cd backend
pytest ../tests/ -v
```

### Run Individual Suites

```bash
# Integration tests (API endpoints)
pytest ../tests/test_integration.py -v

# Regression tests (contract stability)
pytest ../tests/test_regression.py -v

# Mutation-style tests (boundary conditions)
pytest ../tests/test_mutation.py -v
```

### Run with Coverage

```bash
pytest ../tests/ -v --cov=. --cov-report=term-missing --cov-report=html:../coverage_html
# Open coverage_html/index.html for the coverage report
```

### Test Types Explained

| Type | File | Purpose |
|---|---|---|
| **Integration** | `test_integration.py` | Full HTTP cycle for every endpoint |
| **Regression** | `test_regression.py` | Stability of AI output format and service contracts |
| **Mutation-Style** | `test_mutation.py` | Boundary conditions, error paths, DB failures |

---

## 📡 API Reference

The full interactive API documentation is auto-generated at:
```
http://localhost:8000/api/docs     ← Swagger UI
http://localhost:8000/api/redoc    ← ReDoc
```

### Key Endpoints

```
GET  /health                              → System status
GET  /auth/github                         → GitHub OAuth login redirect
GET  /auth/status                         → Session authentication status
GET  /repos                              → List user's repositories
GET  /repos/{owner}/{repo}/prs           → List open pull requests
POST /review/{owner}/{repo}/{pr_number}  → Trigger PR + deep repository AI review
POST /repos/{owner}/{repo}/prs/{pr}/comment → Post to GitHub
GET  /history                            → Paginated review history
GET  /history/review/{id}                → Review detail
GET  /history/{owner}/{repo}             → Repo-scoped history
```

**Authentication:**
- Preferred: GitHub OAuth session cookie via `/auth/github`
- Optional header fallback: `X-Github-Token` and `X-Google-Api-Key`

### Deep Report Response Model

`POST /review/{owner}/{repo}/{pr_number}` now returns connected documentation payloads:

- `report_pages`: Split report sections used by the dashboard page navigation.
- `page_documentation`: Per-page docs with:
        - `what_is_happening`
        - `what_is_wrong`
        - `why_it_matters`
        - `recommended_actions`
        - `cross_links`
- `issue_counts`: Severity and topical counters.
- `top_findings`: Extracted headline findings for quick triage.

This allows the UI to show a multi-page report where each page is self-documented and connected to the rest of the analysis flow.

---

## 🐳 Docker

### Single Image Build

```bash
docker build -f docker/Dockerfile -t ai-code-reviewer .
docker run -p 8000:8000 \
        -e GITHUB_CLIENT_ID=... \
        -e GITHUB_CLIENT_SECRET=... \
        -e GITHUB_REDIRECT_URI=http://localhost:8000/auth/github/callback \
  -e GOOGLE_API_KEY=... \
        -e DATABASE_URL=sqlite:///./data/ai_code_reviewer.db \
        -e ANALYSIS_WORKDIR=./data/repos \
  ai-code-reviewer
```

### Docker Compose

```bash
docker compose up --build          # Development
docker compose up -d               # Detached mode
docker compose down -v             # Stop and remove volumes
docker compose logs -f backend     # Stream backend logs
```

---

## ⚙️ CI/CD Pipeline

The GitHub Actions pipeline (`.github/workflows/ci.yml`) runs on every push/PR:

```
Push to main/develop
        │
        ▼
[1] 🔍 Lint (flake8)
        │
        ▼
[2] 🧪 Test (pytest)
    ├── Integration Tests
    ├── Regression Tests
    ├── Mutation Tests
    └── Coverage Report → Codecov
        │
        ▼
[3] 🐳 Docker Build + Health Check
    └── Push to Docker Hub (main only)
        │
        ▼
[4] 🚀 Deploy to Production (main only)
```

**Required Secrets (GitHub → Settings → Secrets):**
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

---

## 📚 Documentation

| Document | Location |
|---|---|
| Academic Report (SRS, DFD, ERD, UML) | [`docs/PROJECT_REPORT.md`](./docs/PROJECT_REPORT.md) |
| System Architecture Diagrams | [`docs/diagrams/architecture.md`](./docs/diagrams/architecture.md) |
| API Documentation | `http://localhost:8000/api/docs` |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'feat: add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👥 Team

Built as an academic project demonstrating:
- Full-stack web development
- AI/LLM integration
- CI/CD automation
- Software testing methodologies
- Clean architecture principles