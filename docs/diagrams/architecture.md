# System Architecture — AI Code Reviewer

## High-Level Architecture

```mermaid
graph TB
    subgraph Client["Client (Browser)"]
        UI["Vanilla JS SPA<br/>index.html + app.js"]
    end

    subgraph Backend["Backend (FastAPI — Python)"]
        API["REST API<br/>/repos /prs /review /history"]
        GH["GitHub Service<br/>PyGithub"]
        AI["AI Service<br/>Google Gemini"]
        DB_L["Database Layer<br/>pymongo"]
    end

    subgraph Storage["Storage"]
        MONGO[("MongoDB<br/>review_history")]
    end

    subgraph External["External Services"]
        GITHUB["GitHub API<br/>repos · PRs · diffs · comments"]
        GEMINI["Google Gemini API<br/>gemini-3-flash-preview"]
    end

    subgraph DevOps["DevOps Layer"]
        DOCKER["Docker Compose<br/>backend + mongo"]
        CI["GitHub Actions<br/>lint → test → build → deploy"]
    end

    UI -->|HTTP/JSON| API
    API --> GH
    API --> AI
    API --> DB_L
    GH -->|PyGithub| GITHUB
    AI -->|REST| GEMINI
    DB_L --> MONGO
    DOCKER -.->|hosts| Backend
    DOCKER -.->|hosts| Storage
    CI -.->|builds & tests| DOCKER
```

---

## Component Layer Diagram

```
┌─────────────────────────────────────────────────────┐
│                  PRESENTATION LAYER                  │
│   Browser SPA (HTML + CSS + Vanilla JS)              │
│   ├── Auth Form (Token input)                        │
│   ├── Repository Browser + Search                    │
│   ├── Pull Request List (with stats)                 │
│   ├── AI Review Panel (Markdown rendered)            │
│   └── Review History (paginated)                     │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP/JSON
┌──────────────────────▼──────────────────────────────┐
│                   API GATEWAY LAYER                  │
│   FastAPI Application (main.py)                      │
│   ├── CORS Middleware                                │
│   ├── Static File Server (frontend/)                 │
│   ├── Dependency Injection (tokens)                  │
│   └── Request/Response Validation (Pydantic)         │
└───────┬──────────────┬────────────────┬─────────────┘
        │              │                │
┌───────▼────┐  ┌──────▼──────┐ ┌──────▼──────────────┐
│  GitHub    │  │  AI Service  │ │  Database Layer      │
│  Service   │  │ (ai_service) │ │  (database.py)       │
│            │  │              │ │                      │
│ PyGithub   │  │ Gemini API   │ │ pymongo              │
│ OAuth/PAT  │  │ Prompt Eng.  │ │ CRUD Operations      │
│ REST calls │  │ Confidence   │ │ Index Management     │
└────────────┘  └─────────────┘ └──────────────────────┘
        │              │                │
┌───────▼────────────────────────────────▼─────────────┐
│              EXTERNAL DEPENDENCIES                    │
│  GitHub REST API v3    Google Gemini API  MongoDB 7   │
└──────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram (DFD Level 1)

```mermaid
flowchart LR
    USER([User])
    
    P1[1.0<br/>Authenticate]
    P2[2.0<br/>Browse Repos & PRs]
    P3[3.0<br/>Trigger AI Review]
    P4[4.0<br/>Store & Retrieve<br/>History]
    
    GH_API[(GitHub API)]
    GEMINI_API[(Gemini API)]
    DB[(MongoDB)]
    
    USER -->|PAT + API Key| P1
    P1 -->|Validated Token| P2
    P2 <-->|get_repos / get_prs| GH_API
    P2 -->|Selected PR| P3
    P3 -->|get_pr_diff| GH_API
    GH_API -->|diff text| P3
    P3 -->|diff prompt| GEMINI_API
    GEMINI_API -->|review markdown| P3
    P3 -->|review + score| P4
    P4 <-->|read/write reviews| DB
    P4 -->|rendered feedback| USER
    P3 -->|post comment| GH_API
```

---

## Entity Relationship Diagram (MongoDB Schema)

```
┌────────────────────────────────────────────────────┐
│                  review_history                     │
├────────────────────────────────────────────────────┤
│  _id              ObjectId (auto)   PRIMARY KEY     │
│  owner            String            GitHub username │
│  repo             String            Repo name       │
│  pr_number        Integer           PR number       │
│  pr_title         String            PR title text   │
│  pr_author        String            GitHub username │
│  review_text      String            Markdown text   │
│  confidence_score Float             0.0 – 10.0      │
│  reviewed_at      DateTime (UTC)    Timestamp       │
├────────────────────────────────────────────────────┤
│  Indexes:                                           │
│    reviewed_at DESC  (sort by newest)               │
│    owner + repo      (repo-scoped queries)          │
│    pr_number         (PR lookup)                    │
└────────────────────────────────────────────────────┘
```

---

## Sequence Diagram — AI Review Flow

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant API as FastAPI Backend
    participant GH as GitHub Service
    participant AI as AI Service (Gemini)
    participant DB as MongoDB

    U->>API: POST /review/{owner}/{repo}/{pr_number}
    Note right of U: Headers: X-Github-Token, X-Google-Api-Key
    
    API->>GH: get_pr_details(owner, repo, pr_number)
    GH-->>API: {title, author, ...}
    
    API->>GH: get_pr_diff(owner, repo, pr_number)
    GH-->>API: unified_diff_string
    
    API->>AI: analyze_code(diff_text)
    Note right of AI: Structured prompt with<br/>system instructions
    AI-->>API: (review_markdown, confidence_score)
    
    API->>DB: save_review(owner, repo, pr, title, author, review, score)
    DB-->>API: review_id
    
    API-->>U: {status: "success", review, confidence_score, review_id}
    
    U->>API: POST /repos/{owner}/{repo}/prs/{pr}/comment
    API->>GH: post_comment(owner, repo, pr, body)
    GH-->>API: True
    API-->>U: {success: true}
```

---

## Use Case Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    AI Code Reviewer System               │
│                                                         │
│  ┌──────────┐                                           │
│  │          │──── Connect with GitHub Token ────────→  │
│  │          │──── Browse Repositories ─────────────→   │
│  │          │──── Select Repository ────────────────→  │
│  │ Developer│──── View Open Pull Requests ──────────→  │
│  │  (Actor) │──── Trigger AI Review ────────────────→  │
│  │          │──── View AI Feedback ──────────────────→ │
│  │          │──── Post Comment to GitHub ────────────→ │
│  │          │──── Browse Review History ─────────────→ │
│  └──────────┘                                           │
│                                                         │
│  ┌──────────┐                                           │
│  │          │──── Monitor Health Endpoint ───────────→ │
│  │  DevOps  │──── View API Documentation ────────────→ │
│  │  (Actor) │──── Run Docker Compose ────────────────→ │
│  └──────────┘                                           │
└─────────────────────────────────────────────────────────┘
```

---

## Class Diagram

```mermaid
classDiagram
    class GitHubService {
        -token: str
        -gh: Github
        +get_user_repos() List~Dict~
        +get_pull_requests(owner, repo) List~Dict~
        +get_pr_details(owner, repo, pr_number) Dict
        +get_pr_diff(owner, repo, pr_number) str
        +post_comment(owner, repo, pr_number, body) bool
    }

    class AIService {
        -api_key: str
        -model: GenerativeModel
        +analyze_code(diff_text) Tuple~str, float~
        -_extract_confidence_score(text) float
    }

    class DatabaseLayer {
        <<module>>
        +get_db() Database
        +save_review(owner, repo, pr_number, ...) str
        +get_review_history(limit, skip) List~Dict~
        +get_reviews_for_repo(owner, repo) List~Dict~
        +count_total_reviews() int
        +close_db() void
    }

    class FastAPIApp {
        <<FastAPI>>
        +GET /health
        +GET /repos
        +GET /repos/owner/repo/prs
        +POST /review/owner/repo/pr
        +POST /repos/owner/repo/prs/pr/comment
        +GET /history
        +GET /history/owner/repo
    }

    class Config {
        +GITHUB_TOKEN: str
        +GOOGLE_API_KEY: str
        +GITHUB_CLIENT_ID: str
        +GITHUB_CLIENT_SECRET: str
        +MONGO_URI: str
        +MONGO_DB_NAME: str
        +APP_ENV: str
    }

    FastAPIApp --> GitHubService : depends on
    FastAPIApp --> AIService : depends on
    FastAPIApp --> DatabaseLayer : calls
    GitHubService --> Config : reads
    AIService --> Config : reads
    DatabaseLayer --> Config : reads
```
