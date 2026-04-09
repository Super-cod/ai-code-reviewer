# AI Code Reviewer System
## Academic Project Report

**Project Title:** AI Code Reviewer — Automated GitHub Pull Request Analysis using Large Language Models

**Technology Stack:** Python (FastAPI), Vanilla JavaScript, MongoDB, Google Gemini AI, Docker, GitHub Actions

**Repository:** https://github.com/[your-username]/ai-code-reviewer

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Objectives](#2-objectives)
3. [User Stories](#3-user-stories)
4. [System Architecture & Design](#4-system-architecture--design)
5. [Design of Tests](#5-design-of-tests)
6. [Appendix A — Software Requirements Specification (SRS)](#appendix-a--software-requirements-specification-srs)
7. [Appendix B — Data Flow Diagram (DFD)](#appendix-b--data-flow-diagram-dfd)
8. [Appendix C — Entity Relationship Diagram (ERD)](#appendix-c--entity-relationship-diagram-erd)
9. [Appendix D — UML Diagrams](#appendix-d--uml-diagrams)
10. [Appendix E — Code Listing](#appendix-e--code-listing)
11. [Appendix F — Screenshots Description](#appendix-f--screenshots-description)
12. [Appendix G — CI/CD Pipeline Description](#appendix-g--cicd-pipeline-description)

---

## 1. Problem Statement

### 1.1 Background

Modern software development relies heavily on collaborative workflows, particularly Pull Request (PR)-based code reviews on platforms such as GitHub. In this workflow, developers submit code changes as PRs, which team members review manually before merging into the main codebase.

Manual code review, while essential for quality assurance, presents several systemic challenges:

| Challenge | Impact |
|---|---|
| **Time-consuming** | Senior developers may spend 2–6 hours per day reviewing code |
| **Inconsistency** | Review quality varies between reviewers and their current cognitive state |
| **Scaling bottleneck** | As team size grows, review throughput often does not scale proportionally |
| **Knowledge silos** | Domain experts may be unavailable, creating review bottlenecks |
| **Fatigue-induced gaps** | Reviewers under time pressure routinely miss bugs, security issues, or performance anti-patterns |

A 2022 study by GitHub found that the average time-to-review for PRs in open-source projects is **4.2 days**, and that 23% of submitted bugs are attributable to insufficiently reviewed PRs.

### 1.2 Problem Definition

> **"How can AI-powered automation supplement human code review to improve consistency, speed, and coverage of Pull Request analysis without replacing the human judgment required for context-sensitive decisions?"**

This project directly addresses this problem by building a web application that:
1. Connects to GitHub repositories using a Personal Access Token.
2. Fetches open Pull Requests and their code diffs.
3. Submits the diffs to a Large Language Model (Google Gemini) with a carefully engineered prompt.
4. Returns structured, actionable code review feedback.
5. Persists review history for auditing and trend tracking.
6. Optionally posts the AI-generated review as a comment on the GitHub PR.

---

## 2. Objectives

### 2.1 Primary Objectives

- **O1 — GitHub Integration:** Authenticate with GitHub using a Personal Access Token (PAT) and access repository data including pull requests and their code diffs.
- **O2 — AI Analysis:** Submit code diffs to Google Gemini with a structured system prompt and receive categorised feedback covering bugs, security, performance, and code quality.
- **O3 — Review History:** Persist all generated reviews to a MongoDB database for historical analysis and audit trails.
- **O4 — Feedback Display:** Present the AI-generated review to the user in a readable, markdown-rendered interface.
- **O5 — GitHub Integration (Bidirectional):** Allow users to post the AI-generated review back to the GitHub PR as a comment.

### 2.2 Secondary Objectives

- **O6 — CI/CD Pipeline:** Automate testing and Docker deployment via GitHub Actions.
- **O7 — Test Coverage:** Achieve >80% test coverage across integration, regression, and mutation-style tests.
- **O8 — Deployability:** The system shall be fully containerised with Docker Compose for one-command deployment.

### 2.3 Non-Objectives (Out of Scope)

- Full OAuth 2.0 flow (PAT is used for simplicity and academic scope)
- Mobile application
- Offline / local LLM support
- Real-time webhook-based review triggering

---

## 3. User Stories

### 3.1 Developer (Primary Persona)

> *"As a developer, I want to connect my GitHub account with a Personal Access Token so that I can access my repositories without complex OAuth setup."*

> *"As a developer, I want to see all my repositories listed in a searchable sidebar so that I can quickly find the project I want to review."*

> *"As a developer, I want to see all open Pull Requests for a selected repository so that I can choose which one to analyse."*

> *"As a developer, I want to trigger an AI review of a PR with a single click so that I receive instant, structured feedback."*

> *"As a developer, I want the AI feedback to be rendered in readable markdown so that I can easily parse the review sections."*

> *"As a developer, I want to see a confidence score alongside the review so that I understand how reliable the AI assessment is."*

> *"As a developer, I want to post the AI review as a GitHub comment so that my team can see and discuss the automated feedback."*

> *"As a developer, I want to browse my past AI reviews in a history panel so that I can track improvements over time."*

### 3.2 Team Lead (Secondary Persona)

> *"As a team lead, I want to view the review history for a repository so that I can audit code quality trends."*

> *"As a team lead, I want the review to cover security vulnerabilities so that security issues are caught before merge."*

### 3.3 DevOps Engineer (Tertiary Persona)

> *"As a DevOps engineer, I want a /health endpoint so that monitoring systems can verify the application is running."*

> *"As a DevOps engineer, I want automated CI/CD to run tests on every push so that broken code is never deployed."*

---

## 4. System Architecture & Design

### 4.1 Architecture Overview

The AI Code Reviewer follows a **Three-Tier Architecture**:

```
Tier 1 — Presentation: Vanilla JS SPA (Browser)
Tier 2 — Application:  FastAPI REST API (Server)
Tier 3 — Data:         MongoDB Database
```

**External service integrations:**
- **GitHub API v3** — Repository, PR, and comment operations via `PyGithub`
- **Google Gemini API** — LLM-based code analysis via `google-generativeai`

The frontend is served directly by the FastAPI backend as static files, avoiding the need for a separate web server and simplifying deployment.

### 4.2 Technology Stack Rationale

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Python (FastAPI) | Async support, auto-generated OpenAPI docs, type safety via Pydantic |
| Frontend | Vanilla JavaScript | Zero build-step required, fast load, no framework dependencies |
| Database | MongoDB | Flexible schema for varying review structures; no migrations |
| AI | Google Gemini | Free tier available, strong code reasoning, structured outputs |
| Container | Docker + Compose | Reproducible environments, simple multi-service orchestration |
| CI/CD | GitHub Actions | Native GitHub integration, free for public repos |

### 4.3 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health check |
| `GET` | `/repos` | List authenticated user's repos |
| `GET` | `/repos/{owner}/{repo}/prs` | List open PRs for a repo |
| `POST` | `/review/{owner}/{repo}/{pr_number}` | Trigger AI review of a PR |
| `POST` | `/repos/{owner}/{repo}/prs/{pr_number}/comment` | Post review to GitHub |
| `GET` | `/history` | Paginated review history |
| `GET` | `/history/{owner}/{repo}` | Repo-scoped review history |

### 4.4 Security Design

- **Token-based auth:** Tokens are passed as HTTP headers per request; never stored server-side.
- **Non-root container:** Docker image runs as an unprivileged `appuser`.
- **Input validation:** All request bodies validated by Pydantic models.
- **CORS:** Configured (permissive for dev; restrict to domain in production).
- **XSS prevention:** Frontend markdown renderer escapes all HTML entities before rendering.

### 4.5 Prompt Engineering

The AI Service uses a **structured system prompt** that instructs Gemini to:
1. Act as a senior software engineer with 20+ years of experience.
2. Return responses in a fixed markdown format with 7 required sections.
3. Produce a confidence score (1–10) based on diff completeness.
4. Reference specific filenames and line numbers where possible.

The system prompt is separated from the user message (the diff), following the recommended multi-turn conversation pattern for instruction-following models.

---

## 5. Design of Tests

### 5.1 Testing Strategy

The project follows the **Testing Pyramid** approach with three distinct test categories:

```
         /\
        /  \
       / E2E \          ← (manual / future Playwright)
      /--------\
     /Regression\       ← tests/test_regression.py
    /------------\
   / Integration  \     ← tests/test_integration.py
  /----------------\
 /  Mutation-Style  \   ← tests/test_mutation.py
/____________________\
```

### 5.2 Test Suite 1 — Integration Tests (`test_integration.py`)

**Purpose:** Verify that all API endpoints respond correctly with proper status codes, response shapes, and data types when given valid inputs.

**Framework:** `pytest` + FastAPI `TestClient`

**Approach:** All external services (GitHub, Gemini, MongoDB) are mocked using FastAPI's dependency override mechanism (`app.dependency_overrides`).

**Coverage:**
| Class | Tests | Focus |
|---|---|---|
| `TestHealth` | 4 | Status, shape, values |
| `TestRepositories` | 6 | 200 OK, list shape, field validation, 401 without token |
| `TestPullRequests` | 7 | List shape, field types, state validation |
| `TestAIReview` | 7 | Status success, review text, confidence score range |
| `TestComments` | 4 | Success flag, message field, empty body |
| `TestHistory` | 7 | Pagination params, shape, integer types |

**Sample Test Case:**
```python
def test_review_has_confidence_score(self, client):
    data = client.post(self.url(), headers=self.headers()).json()
    assert 'confidence_score' in data
    score = data['confidence_score']
    assert isinstance(score, (int, float))
    assert 0 <= score <= 10
```

**Run Command:**
```bash
cd backend
pytest ../tests/test_integration.py -v
```

---

### 5.3 Test Suite 2 — Regression Tests (`test_regression.py`)

**Purpose:** Guard against regressions in stable contracts — specifically AI output format structure, GitHub service response shapes, and configuration loading. These tests fail if someone accidentally breaks a working behaviour.

**Framework:** `pytest` + `unittest.mock`

**Key Scenarios:**
- AI review must always contain the 7 required markdown sections
- Confidence score pattern must be parseable from review text
- AI Service must default to 7.0 when no score is found
- Large diffs (>15,000 chars) must be truncated before API call
- GitHub service must return `[]` / `""` / `False` when not authenticated
- Config must load all required attributes

**Sample Test Case:**
```python
@pytest.mark.asyncio
async def test_ai_service_truncates_large_diff(self):
    """Diffs larger than 15,000 chars should be truncated before sending."""
    svc = AIService(api_key='key')
    large_diff = 'x' * 20_000
    result, _ = await svc.analyze_code(large_diff)
    call_args = mock_instance.generate_content.call_args[0][0]
    assert len(call_args) < 16_500  # truncated
```

**Run Command:**
```bash
cd backend
pytest ../tests/test_regression.py -v
```

---

### 5.4 Test Suite 3 — Mutation-Style Tests (`test_mutation.py`)

**Purpose:** Test boundary conditions and failure paths to simulate the effects of code mutations. A "mutation" is a small change to production code (e.g., changing `>=` to `>`, or removing a guard clause) that should cause a test to fail. These tests are designed to fail if such mutations are introduced.

**Framework:** `pytest` + `unittest.mock`

**Key Scenarios:**
- `None` input to AI analysis → graceful error, score 0.0
- AI API throws exception → returns error string, not crash
- Confidence score 15/10 → clamped to 10.0 (tests the clamp guard)
- GitHub API returns 401 → `post_comment` returns `False`
- GitHub API returns 404 → `get_pr_diff` raises, not swallows exception
- MongoDB `ConnectionFailure` → `get_db()` returns `None`
- All DB functions return safe defaults when DB is None
- API `limit=0` → 422 validation error
- API `limit=101` → 422 validation error (boundary)
- Non-integer PR number → 422 validation error

**Sample Test Case:**
```python
def test_confidence_score_above_ten_clamped(self):
    """Any score > 10 should be clamped to 10. Mutating the clamp logic fails this."""
    svc = AIService(api_key='fake_key')
    score = svc._extract_confidence_score('**Confidence Score: 15/10**')
    assert score <= 10.0
```

**Run Command:**
```bash
cd backend
pytest ../tests/test_mutation.py -v
```

---

### 5.5 Combined Test Execution with Coverage

```bash
cd backend
pytest ../tests/ -v --cov=. --cov-report=term-missing --cov-report=html:../coverage_html
```

### 5.6 Tools Summary

| Tool | Version | Purpose |
|---|---|---|
| `pytest` | 8.2.x | Test framework and runner |
| `pytest-asyncio` | 0.23.x | Async test support |
| `pytest-cov` | 5.0.x | Code coverage measurement |
| `FastAPI TestClient` | 0.111.x | HTTP-level endpoint testing |
| `unittest.mock` | stdlib | Mocking external dependencies |
| `httpx` | 0.27.x | Underlying HTTP client for TestClient |

---

## Appendix A — Software Requirements Specification (SRS)

### A.1 Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | System shall accept a GitHub PAT via HTTP header for all protected endpoints | Must Have |
| FR-02 | System shall accept a Google API Key via HTTP header for AI-powered endpoints | Must Have |
| FR-03 | System shall fetch all repositories of the authenticated GitHub user | Must Have |
| FR-04 | System shall fetch all open Pull Requests for a selected repository | Must Have |
| FR-05 | System shall retrieve the unified diff for a given PR | Must Have |
| FR-06 | System shall submit the diff to Gemini AI with a structured system prompt | Must Have |
| FR-07 | System shall parse and return the confidence score from AI output | Must Have |
| FR-08 | System shall persist each completed review to MongoDB | Must Have |
| FR-09 | System shall expose a paginated history endpoint returning past reviews | Should Have |
| FR-10 | System shall allow posting the AI review as a comment on the GitHub PR | Should Have |
| FR-11 | System shall expose a /health endpoint for monitoring | Must Have |
| FR-12 | System shall truncate diffs exceeding 15,000 characters before AI submission | Must Have |

### A.2 Non-Functional Requirements

| ID | Requirement | Metric |
|---|---|---|
| NFR-01 | API response time for /repos < 3s | P95 latency |
| NFR-02 | AI review response time < 45s | P95 latency |
| NFR-03 | System shall run fully containerised via Docker Compose | Binary |
| NFR-04 | Test suite shall achieve >75% code coverage | Coverage % |
| NFR-05 | Docker image shall run as non-root user | Security audit |
| NFR-06 | All inputs validated via Pydantic models | Static code review |
| NFR-07 | XSS protected — frontend must escape HTML in rendered content | Manual review |

### A.3 Constraints

- GitHub rate limits: 5,000 requests/hour for authenticated users
- Gemini API: Free tier rate limits apply; commercial use requires billing
- MongoDB: A running instance is required; application degrades gracefully (history unavailable) but does not crash if MongoDB is unreachable
- Python 3.11+ required

---

## Appendix B — Data Flow Diagram (DFD)

### B.1 DFD Level 0 — Context Diagram

```
                 ┌──────────────────────────────┐
                 │                              │
  Developer ────►│   AI Code Reviewer System    │────► GitHub API
                 │                              │
  Developer ◄────│   (Central Processing Unit)  │◄──── GitHub API
                 │                              │
                 │                              │────► Google Gemini API
                 └──────────────────────────────┘
                              │
                              ▼
                           MongoDB
                       (Review History)
```

### B.2 DFD Level 1 — Main Processes

See: [docs/diagrams/architecture.md — Data Flow Diagram (DFD Level 1)](./diagrams/architecture.md#data-flow-diagram-dfd-level-1)

**Process 1.0 — Authenticate**
- Input: GitHub PAT + Google API Key
- Output: Validated tokens → session state
- Process: Token header inspection; no storage

**Process 2.0 — Browse Repos & PRs**
- Input: Validated GitHub token
- Output: Repository list → selected PR
- Process: PyGithub API calls to list repos/PRs

**Process 3.0 — Trigger AI Review**
- Input: Selected PR + both API keys
- Output: Structured review + confidence score
- Process: get_diff → truncate → prompt → Gemini → parse

**Process 4.0 — Store & Retrieve History**
- Input: Completed review data
- Output: Paginated history list
- Process: MongoDB insert/find with indexed queries

---

## Appendix C — Entity Relationship Diagram (ERD)

The system uses a single MongoDB collection. The logical entity is:

```
REVIEW_HISTORY
──────────────────────────────────────────────────────
PK  _id              : ObjectId   (auto-generated)
    owner            : String     (GitHub username)
    repo             : String     (Repository name)
    pr_number        : Integer    (Pull request number)
    pr_title         : String     (Pull request title)
    pr_author        : String     (GitHub author username)
    review_text      : String     (Full markdown review)
    confidence_score : Float      (0.0 – 10.0)
    reviewed_at      : DateTime   (UTC timestamp)
──────────────────────────────────────────────────────

Unique constraint: None (multiple reviews of same PR allowed)

Indexes:
  - reviewed_at (DESC) — history pagination
  - (owner, repo)      — repository-scoped queries
  - pr_number          — PR lookup
```

**Rationale for denormalised design:** Since there is no user management system (no Users table), the review is self-contained. The `owner + repo + pr_number` triple acts as a logical foreign key to GitHub's data model, which is the authoritative source of truth.

---

## Appendix D — UML Diagrams

### D.1 Use Case Diagram

See: [docs/diagrams/architecture.md — Use Case Diagram](./diagrams/architecture.md#use-case-diagram)

**Actors:** Developer, Team Lead, DevOps Engineer, GitHub API (system actor), Gemini API (system actor)

### D.2 Sequence Diagram — AI Review Flow

See: [docs/diagrams/architecture.md — Sequence Diagram](./diagrams/architecture.md#sequence-diagram--ai-review-flow)

**Key sequence:**
1. User POSTs to `/review/{owner}/{repo}/{pr_number}`
2. Backend fetches PR metadata and diff from GitHub
3. Diff is submitted to Gemini with structured system prompt
4. Review + confidence score returned and stored in MongoDB
5. Response returned to user

### D.3 Class Diagram

See: [docs/diagrams/architecture.md — Class Diagram](./diagrams/architecture.md#class-diagram)

**Key classes:**
- `GitHubService` — All GitHub API interactions
- `AIService` — LLM invocation and result parsing
- `DatabaseLayer` (module) — MongoDB CRUD operations
- `Config` — Environment-variable-based configuration
- `FastAPIApp` — Route definitions and middleware

---

## Appendix E — Code Listing

### Project File Structure

```
ai-code-reviewer/
├── backend/
│   ├── main.py              # FastAPI application, routes, lifecycle
│   ├── github_service.py    # GitHub API wrapper (PyGithub)
│   ├── ai_service.py        # Gemini AI wrapper + prompt engineering
│   ├── database.py          # MongoDB CRUD layer
│   ├── config.py            # Environment configuration
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Environment template
├── frontend/
│   ├── index.html           # SPA HTML structure
│   ├── app.js               # Vanilla JS application logic
│   └── style.css            # CSS design system (dark mode, glassmorphism)
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Shared fixtures, mocks, test client
│   ├── test_integration.py  # API endpoint integration tests
│   ├── test_regression.py   # Output format and contract regression tests
│   └── test_mutation.py     # Boundary condition and error-path tests
├── docker/
│   └── Dockerfile           # Multi-stage production Dockerfile
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI/CD pipeline
├── docs/
│   └── diagrams/
│       └── architecture.md  # All system diagrams (Mermaid + ASCII)
├── docker-compose.yml       # Multi-service Docker orchestration
├── pytest.ini               # Pytest configuration
└── README.md                # Project setup and usage guide
```

### Key Files — Line Counts

| File | Lines | Purpose |
|---|---|---|
| `main.py` | ~200 | API routes, lifecycle, Pydantic models |
| `github_service.py` | ~130 | GitHub API wrapper |
| `ai_service.py` | ~100 | Gemini AI + prompt engineering |
| `database.py` | ~130 | MongoDB CRUD |
| `test_integration.py` | ~180 | 37 integration tests |
| `test_regression.py` | ~200 | 40 regression tests |
| `test_mutation.py` | ~180 | 35 mutation-style tests |
| `style.css` | ~450 | Complete design system |
| `app.js` | ~280 | Frontend SPA logic |
| `ci.yml` | ~130 | 4-stage CI/CD pipeline |

**GitHub Repository:**
```
https://github.com/[your-username]/ai-code-reviewer
```

---

## Appendix F — Screenshots Description

The following screenshots should be taken to accompany this report:

| # | Screenshot | Description |
|---|---|---|
| SS-01 | **Auth Screen** | The landing page showing the hero section with feature pills and the token input form |
| SS-02 | **Repository List** | Dashboard sidebar showing a list of repositories with stars, language, and privacy indicators |
| SS-03 | **PR List** | Main panel showing open pull requests with additions/deletions stats |
| SS-04 | **AI Review Result** | The markdown-rendered AI feedback with sections for bugs, security, performance, and confidence score badge |
| SS-05 | **History Tab** | Review history panel showing paginated past reviews with confidence scores |
| SS-06 | **GitHub Comment** | GitHub PR page showing the posted AI review comment with the "🤖 AI Code Review" header |
| SS-07 | **CI/CD Pipeline** | GitHub Actions workflow run showing all 4 stages (lint, test, docker build, deploy) in green |
| SS-08 | **Test Output** | Terminal output of `pytest tests/ -v` showing all test names and PASSED status |
| SS-09 | **Docker Compose** | Terminal output of `docker-compose up --build` showing both services starting healthy |
| SS-10 | **API Docs** | FastAPI auto-generated OpenAPI docs at `/api/docs` |

---

## Appendix G — CI/CD Pipeline Description

### G.1 Pipeline Overview

The CI/CD pipeline is defined in `.github/workflows/ci.yml` and consists of 4 sequential jobs.

### G.2 Job 1: Lint (flake8)

- **Trigger:** Every push and PR
- **Tool:** flake8 with max-line-length=120
- **Purpose:** Enforce Python code style standards
- **Failure condition:** Any PEP8 violations

### G.3 Job 2: Test

- **Trigger:** After successful lint
- **Services:** MongoDB 7 Docker container (health-checked)
- **Steps:**
  1. Run integration test suite → JUnit XML report
  2. Run regression test suite → JUnit XML report
  3. Run mutation-style test suite → JUnit XML report
  4. Full suite with coverage → XML + terminal report
  5. Upload coverage to Codecov
- **Artifacts:** Test result XMLs + coverage report

### G.4 Job 3: Docker Build

- **Trigger:** After successful tests
- **Steps:**
  1. Build multi-stage Docker image with SHA and `latest` tags
  2. Start container and hit `/health` to validate image
  3. Push to Docker Hub (on main branch push only)

### G.5 Job 4: Deploy

- **Trigger:** Push to main only
- **Environment:** production (with URL)
- **Steps:** Placeholder SSH deployment command (adapt for provider)

### G.6 Required GitHub Secrets

| Secret | Description |
|---|---|
| `DOCKERHUB_USERNAME` | Docker Hub account name |
| `DOCKERHUB_TOKEN` | Docker Hub access token |
| `DEPLOY_USER` | SSH user for production server |
| `DEPLOY_HOST` | Hostname/IP of production server |

### G.7 Running Locally

```bash
# 1. Clone the repository
git clone https://github.com/[your-username]/ai-code-reviewer.git
cd ai-code-reviewer

# 2. Set up environment
cp backend/.env.example backend/.env
# Edit backend/.env with real tokens

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Run tests
cd backend
pytest ../tests/ -v

# 5. Start with Docker Compose
cd ..
docker-compose up --build

# 6. Access the application
# Open http://localhost:8000 in your browser
# API docs at http://localhost:8000/api/docs
```
