import logging
import os
import re
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth
import database as db
from ai_service import AIService
from code_fetcher import fetch_repo_files, parse_github_url
from config import config
from github_service import GitHubService
from indexer import analyze_codebase
from local_repo import checkout_pr, clone_or_refresh_repo, collect_repo_files

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Code Reviewer",
    description="GitHub PR review with AI summary + deep repository analysis.",
    version="4.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)
if os.path.isdir(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

app.include_router(auth.router)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    logger.info("Starting AI Code Reviewer v4...")
    db.init_db()


@app.on_event("shutdown")
async def on_shutdown():
    db.close_db()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AnalyseRequest(BaseModel):
    repo_url: str
    gemini_key: Optional[str] = None   # optional override; falls back to .env

class PasteAnalyseRequest(BaseModel):
    code: str
    filename: str = "snippet.py"
    gemini_key: Optional[str] = None

class AnalyseResponse(BaseModel):
    status: str
    analysis_id: Optional[int] = None
    repo_name: str = ""
    files_analyzed: int = 0
    report: str = ""
    confidence_score: float = 0.0
    overall_score:   float = 0.0


class CommentRequest(BaseModel):
    comment: str

class ChatRequest(BaseModel):
    query: str

class ReviewResponse(BaseModel):
    status: str
    review_id: Optional[int] = None
    owner: str
    repo: str
    pr_number: int
    pr_title: str
    review: str
    deep_analysis_report: str
    confidence_score: float
    overall_score: float
    files_indexed: int
    repo_path: str
    executive_summary: str
    issue_counts: Dict[str, int]
    report_pages: Dict[str, str]
    top_findings: List[str]
    page_documentation: Dict[str, Dict[str, str]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_overall_score(text: str) -> float:
    m = re.search(r'Overall Score[:\s*]+(\d+(?:\.\d+)?)\s*/\s*10', text, re.IGNORECASE)
    return min(10.0, max(0.0, float(m.group(1)))) if m else 0.0

def _get_api_key(override: Optional[str]) -> str:
    key = (override or "").strip() or config.GOOGLE_API_KEY
    if not key:
        raise HTTPException(
            status_code=400,
            detail="Google Gemini API key required. Set GOOGLE_API_KEY in .env or pass gemini_key in the request body."
        )
    return key


def _extract_section(report: str, heading: str) -> str:
    pattern = rf"##\s+{re.escape(heading)}\n([\s\S]*?)(?=\n##\s|$)"
    m = re.search(pattern, report)
    return m.group(1).strip() if m else ""

def _extract_subsection(text: str, heading: str) -> str:
    pattern = rf"(?:###?\s+{re.escape(heading)}|\*\*{re.escape(heading)}\*\*:?)[\s\n]+([\s\S]*?)(?=\n###|\n\*\*|\n##|$)"
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _extract_issue_counts(text: str) -> Dict[str, int]:
    return {
        "critical": len(re.findall(r"\bCRITICAL\b", text, flags=re.IGNORECASE)),
        "high": len(re.findall(r"\bHIGH\b", text, flags=re.IGNORECASE)),
        "medium": len(re.findall(r"\bMEDIUM\b", text, flags=re.IGNORECASE)),
        "low": len(re.findall(r"\bLOW\b", text, flags=re.IGNORECASE)),
        "security_mentions": len(re.findall(r"security|auth|token|injection|xss|csrf", text, flags=re.IGNORECASE)),
        "performance_mentions": len(re.findall(r"performance|latency|memory|cpu|slow|bottleneck", text, flags=re.IGNORECASE)),
    }


def _build_report_pages(deep_report: str, pr_review: str) -> Dict[str, str]:
    return {
        "executive": _extract_section(deep_report, "📋 Executive Summary") or deep_report[:2500],
        "landscape": _extract_section(deep_report, "🧭 System Landscape"),
        "architecture": _extract_section(deep_report, "🏗️ Architecture Deep Dive"),
        "security": _extract_section(deep_report, "🔐 Security Assessment"),
        "performance": _extract_section(deep_report, "⚙️ Performance & Scalability"),
        "reliability": _extract_section(deep_report, "🧪 Reliability & Testing Posture"),
        "quality": _extract_section(deep_report, "🧹 Code Quality & Maintainability"),
        "dependencies": _extract_section(deep_report, "📦 Dependency & Supply Chain Review"),
        "findings": _extract_section(deep_report, "📍 File-Level Findings Matrix"),
        "roadmap": _extract_section(deep_report, "🗺️ Multi-Phase Remediation Roadmap"),
        "report_story": _extract_section(deep_report, "🧩 Cross-Page Traceability Map"),
        "pr_review": pr_review,
        "full_report": deep_report,
    }


def _extract_top_findings(text: str) -> List[str]:
    bullets = re.findall(r"^[-*]\s+(.+)$", text, flags=re.MULTILINE)
    numbered = re.findall(r"^\d+\.\s+(.+)$", text, flags=re.MULTILINE)
    candidates = bullets + numbered
    return [c.strip() for c in candidates[:10]]


def _first_nonempty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _short_excerpt(text: str, max_chars: int = 520) -> str:
    if not text:
        return ""
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "..."


def _build_page_documentation(
    pages: Dict[str, str],
    issue_counts: Dict[str, int],
    owner: str,
    repo: str,
    pr_number: int,
) -> Dict[str, Dict[str, str]]:
    critical = issue_counts.get("critical", 0)
    high = issue_counts.get("high", 0)
    medium = issue_counts.get("medium", 0)

    docs: Dict[str, Dict[str, str]] = {}
    for key, content in pages.items():
        if not (content or "").strip():
            continue

        title = key.replace("_", " ").title()
        excerpt = _short_excerpt(content)
        docs[key] = {
            "title": f"{title} Documentation",
            "what_is_happening": _first_nonempty(
                _short_excerpt(_extract_subsection(content, "What is happening"), 1200),
                excerpt,
                "This section describes the current implementation state and runtime behavior."
            ),
            "what_is_wrong": _first_nonempty(
                _short_excerpt(_extract_subsection(content, "What is wrong"), 1200),
                "The section contains the observed risks, design debt, or defects extracted from AI analysis."
            ),
            "why_it_matters": _first_nonempty(
                _short_excerpt(_extract_subsection(content, "Why it matters"), 1200),
                f"Severity profile currently shows CRITICAL={critical}, HIGH={high}, MEDIUM={medium}; this directly affects release readiness and operational risk."
            ),
            "recommended_actions": _first_nonempty(
                _short_excerpt(_extract_subsection(content, "What to do now"), 1200),
                "Use the remediation roadmap and top findings to schedule immediate fixes, tests, and verification gates."
            ),
            "cross_links": (
                f"Connected pages: executive, architecture, security, findings, roadmap. "
                f"Scope: {owner}/{repo} PR #{pr_number}."
            ),
        }

    # Global overview card to connect all pages into one storyline.
    docs["report_story"] = {
        "title": "Connected Report Story",
        "what_is_happening": (
            "The report is organized from context to action: executive summary -> system/architecture -> risk domains -> findings matrix -> roadmap."
        ),
        "what_is_wrong": (
            f"Current risk profile indicates CRITICAL={critical}, HIGH={high}, MEDIUM={medium}. "
            "Higher severities should block release until mitigated."
        ),
        "why_it_matters": (
            "Disconnected findings increase rework and slow incident response. This connected view links cause, impact, and fixes page by page."
        ),
        "recommended_actions": (
            "Start with critical/high items, validate with targeted tests, then execute the phased roadmap and track closure metrics in history."
        ),
        "cross_links": f"Repository scope: {owner}/{repo}; PR scope: #{pr_number}.",
    }

    return docs


def _resolve_github_token(request: Request, x_github_token: Optional[str]) -> str:
    if x_github_token and x_github_token.strip():
        return x_github_token.strip()
    return auth.get_github_token_from_session(request)


def _resolve_gemini_key(request: Request, x_google_api_key: Optional[str]) -> str:
    if x_google_api_key and x_google_api_key.strip():
        return x_google_api_key.strip()
    return auth.get_gemini_key_from_session(request)


def get_github_service(
    request: Request,
    x_github_token: Optional[str] = Header(default=None, alias="X-Github-Token"),
) -> GitHubService:
    token = _resolve_github_token(request, x_github_token)
    service = GitHubService(token=token)
    if not service.gh:
        raise HTTPException(status_code=401, detail="Invalid GitHub token.")
    return service


def get_ai_service(
    request: Request,
    x_google_api_key: Optional[str] = Header(default=None, alias="X-Google-Api-Key"),
) -> AIService:
    key = _resolve_gemini_key(request, x_google_api_key)
    service = AIService(api_key=key)
    if not service.model:
        raise HTTPException(status_code=401, detail="Gemini API key is missing or invalid.")
    return service


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def index():
    f = os.path.join(frontend_path, "login.html")
    return FileResponse(f) if os.path.exists(f) else JSONResponse({"api": "AI Code Reviewer v4"})


@app.get("/login", include_in_schema=False)
async def login_page():
    f = os.path.join(frontend_path, "login.html")
    return FileResponse(f) if os.path.exists(f) else JSONResponse({"api": "AI Code Reviewer v4"})


@app.get("/dashboard", include_in_schema=False)
async def dashboard_page(request: Request):
    try:
        auth.get_session(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=302)
    f = os.path.join(frontend_path, "dashboard.html")
    return FileResponse(f) if os.path.exists(f) else JSONResponse({"api": "AI Code Reviewer v4"})


@app.get("/health", tags=["System"])
async def health():
    db_ok = False
    try:
        db.count_analyses(); db_ok = True
    except Exception:
        pass
    return {
        "status": "healthy",
        "db_connected": db_ok,
        "version": "4.0.0",
        "db_backend": "SQLAlchemy",
    }


@app.get("/repos", tags=["GitHub"])
async def list_repositories(github: GitHubService = Depends(get_github_service)):
    try:
        return github.get_user_repos()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch repositories: {exc}")


@app.get("/repos/{owner}/{repo}/prs", tags=["GitHub"])
async def list_pull_requests(owner: str, repo: str, github: GitHubService = Depends(get_github_service)):
    try:
        return github.get_pull_requests(owner, repo)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch pull requests: {exc}")


@app.post("/review/{owner}/{repo}/{pr_number}", response_model=ReviewResponse, tags=["Review"])
async def review_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    github: GitHubService = Depends(get_github_service),
    ai: AIService = Depends(get_ai_service),
):
    try:
        pr_meta = github.get_pr_details(owner, repo, pr_number)
        pr_diff = github.get_pr_diff(owner, repo, pr_number)
        if not pr_diff.strip():
            raise HTTPException(status_code=422, detail="PR diff is empty; nothing to review.")

        repo_path = ""
        files = []
        deep_report = "Deep repository analysis could not be generated."
        deep_confidence = 0.0

        try:
            repo_path = clone_or_refresh_repo(owner, repo, token=github.token)
            checkout_pr(repo_path, pr_number)
            files = collect_repo_files(repo_path)
        except Exception as clone_exc:
            logger.warning("Local clone/index failed, continuing with PR diff review: %s", clone_exc)

        analysis_key = getattr(ai, "api_key", "") or config.GOOGLE_API_KEY
        if files and analysis_key:
            try:
                deep_report, deep_confidence = await analyze_codebase(
                    files=files,
                    api_key=analysis_key,
                    repo_name=f"{owner}/{repo}",
                    use_index=config.USE_VECTOR_INDEX,
                )
            except Exception as deep_exc:
                logger.warning("Deep analysis failed, returning PR-only review: %s", deep_exc)

        pr_review, pr_confidence = await ai.analyze_code(pr_diff)

        overall_score = _extract_overall_score(deep_report)
        combined_report = (
            f"# PR Review\n\n{pr_review}\n\n"
            f"# Deep Repository Analysis\n\n{deep_report}"
        )
        confidence_score = max(pr_confidence, deep_confidence)
        report_pages = _build_report_pages(deep_report, pr_review)
        issue_counts = _extract_issue_counts(combined_report)
        top_findings = _extract_top_findings(combined_report)
        executive_summary = report_pages.get("executive", "")
        page_documentation = _build_page_documentation(
            pages=report_pages,
            issue_counts=issue_counts,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
        )

        review_id = db.save_review(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            pr_title=pr_meta.get("title", f"PR #{pr_number}"),
            pr_author=pr_meta.get("author", "unknown"),
            review_text=combined_report,
            confidence_score=confidence_score,
            overall_score=overall_score,
        )

        return ReviewResponse(
            status="success",
            review_id=review_id,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            pr_title=pr_meta.get("title", f"PR #{pr_number}"),
            review=pr_review,
            deep_analysis_report=deep_report,
            confidence_score=confidence_score,
            overall_score=overall_score,
            files_indexed=len(files),
            repo_path=repo_path,
            executive_summary=executive_summary,
            issue_counts=issue_counts,
            report_pages=report_pages,
            top_findings=top_findings,
            page_documentation=page_documentation,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("PR review failed")
        raise HTTPException(status_code=500, detail=f"Review failed: {exc}")


@app.post("/repos/{owner}/{repo}/prs/{pr_number}/comment", tags=["GitHub"])
async def post_pr_comment(
    owner: str,
    repo: str,
    pr_number: int,
    body: CommentRequest,
    github: GitHubService = Depends(get_github_service),
):
    success = github.post_comment(owner, repo, pr_number, body.comment)
    return {
        "success": success,
        "message": "Comment posted." if success else "Failed to post comment.",
    }


# ── Chat with Codebase (Semantic Search) ──────────────────────────────────

@app.post("/chat/{owner}/{repo}", tags=["Chat"])
async def chat_with_repo(
    owner: str,
    repo: str,
    body: ChatRequest,
    github: GitHubService = Depends(get_github_service),
    ai: AIService = Depends(get_ai_service),
):
    try:
        from local_repo import clone_or_refresh_repo, collect_repo_files
        from indexer import query_codebase

        # Ensure repo is locally cached using github token
        repo_path = clone_or_refresh_repo(owner, repo, token=github.token)
        files = collect_repo_files(repo_path)

        if not files:
            raise HTTPException(status_code=404, detail="No source files found locally. Make sure you run an analysis first.")

        analysis_key = getattr(ai, "api_key", "") or config.GOOGLE_API_KEY
        if not analysis_key:
            raise HTTPException(status_code=401, detail="Gemini key missing.")

        response = await query_codebase(
            files=files,
            query=body.query,
            api_key=analysis_key,
            repo_name=f"{owner}/{repo}",
            use_index=config.USE_VECTOR_INDEX,
        )
        return {"response": response}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}")


# ── Analyse a GitHub Repo ──────────────────────────────────────────────────

@app.post("/analyse/repo", response_model=AnalyseResponse, tags=["Analysis"])
async def analyse_repo(body: AnalyseRequest):
    """
    Fetch all code files from a public GitHub repo, build a LlamaIndex
    vector index with Gemini embeddings, and generate a full audit report.
    """
    api_key = _get_api_key(body.gemini_key)

    # Parse URL
    try:
        owner, repo = parse_github_url(body.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    repo_name = f"{owner}/{repo}"
    logger.info("📦 Analysing %s …", repo_name)

    # Fetch files
    try:
        files = await fetch_repo_files(
            owner, repo,
            github_token=config.GITHUB_TOKEN or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {e}")

    if not files:
        raise HTTPException(
            status_code=422,
            detail="No analysable source files found in this repository."
        )

    # Analyse
    try:
        report, confidence = await analyze_codebase(
            files=files,
            api_key=api_key,
            repo_name=repo_name,
            use_index=config.USE_VECTOR_INDEX,
        )
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis error: {e}")

    overall = _extract_overall_score(report)

    # Persist
    analysis_id = db.save_analysis(
        source_url=body.repo_url,
        owner=owner,
        repo=repo,
        repo_name=repo_name,
        files_analyzed=len(files),
        report_text=report,
        confidence_score=confidence,
        overall_score=overall,
    )

    return AnalyseResponse(
        status="success",
        analysis_id=analysis_id,
        repo_name=repo_name,
        files_analyzed=len(files),
        report=report,
        confidence_score=confidence,
        overall_score=overall,
    )


# ── Analyse Pasted Code ────────────────────────────────────────────────────

@app.post("/analyse/paste", response_model=AnalyseResponse, tags=["Analysis"])
async def analyse_paste(body: PasteAnalyseRequest):
    """Analyse a single snippet of code pasted directly by the user."""
    api_key = _get_api_key(body.gemini_key)
    files = [{"path": body.filename, "content": body.code, "size": len(body.code)}]

    report, confidence = await analyze_codebase(
        files=files,
        api_key=api_key,
        repo_name=body.filename,
        use_index=False,  # direct Gemini for single snippets
    )
    overall = _extract_overall_score(report)

    analysis_id = db.save_analysis(
        source_url="paste",
        owner="",
        repo="",
        repo_name=body.filename,
        files_analyzed=1,
        report_text=report,
        confidence_score=confidence,
        overall_score=overall,
    )

    return AnalyseResponse(
        status="success",
        analysis_id=analysis_id,
        repo_name=body.filename,
        files_analyzed=1,
        report=report,
        confidence_score=confidence,
        overall_score=overall,
    )


# ── History ───────────────────────────────────────────────────────────────

@app.get("/history", tags=["History"])
async def get_history(
    limit: int = Query(default=20, ge=1, le=100),
    skip:  int = Query(default=0,  ge=0),
):
    rows = db.get_review_history(limit=limit, skip=skip)
    total = db.count_total_reviews()
    lite = [{k: v for k, v in r.items() if k != "report_text"} for r in rows]
    return {"total": total, "limit": limit, "skip": skip, "reviews": lite}


@app.get("/history/review/{review_id}", tags=["History"])
async def get_review(review_id: int):
    row = db.get_analysis_by_id(review_id)
    if not row:
        raise HTTPException(status_code=404, detail="Review not found.")
    return row


@app.get("/history/{owner}/{repo}", tags=["History"])
async def get_repo_history(owner: str, repo: str):
    rows = db.get_reviews_for_repo(owner=owner, repo=repo, limit=100, skip=0)
    return {
        "owner": owner,
        "repo": repo,
        "reviews": rows,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
