from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
from github_service import GitHubService
from ai_service import AIService
from config import config

app = FastAPI(title="AI Code Reviewer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(frontend_path, "index.html"))

class Repo(BaseModel):
    id: int
    name: str
    owner: str
    description: Optional[str]

class PullRequest(BaseModel):
    id: int
    number: int
    title: str
    author: str
    state: str
    created_at: str

def get_github_service(x_github_token: Optional[str] = Header(None)):
    token = x_github_token or config.GITHUB_TOKEN
    if not token:
        raise HTTPException(status_code=401, detail="GitHub Token required")
    return GitHubService(token)

def get_ai_service(x_google_api_key: Optional[str] = Header(None)):
    api_key = x_google_api_key or config.GOOGLE_API_KEY
    if not api_key:
        raise HTTPException(status_code=401, detail="Google API Key required")
    return AIService(api_key)


@app.get("/repos", response_model=List[Repo])
async def get_repos(gh: GitHubService = Depends(get_github_service)):
    try:
        return gh.get_user_repos()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/repos/{owner}/{repo}/prs", response_model=List[PullRequest])
async def get_prs(owner: str, repo: str, gh: GitHubService = Depends(get_github_service)):
    try:
        return gh.get_pull_requests(owner, repo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/review/{owner}/{repo}/{pr_number}")
async def review_pr(
    owner: str, 
    repo: str, 
    pr_number: int, 
    gh: GitHubService = Depends(get_github_service),
    ai: AIService = Depends(get_ai_service)
):
    try:
        diff_text = gh.get_pr_diff(owner, repo, pr_number)
        if not diff_text:
            return {"status": "error", "message": "No changes found in this PR."}
        
        review = await ai.analyze_code(diff_text)
        return {"status": "success", "review": review}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/repos/{owner}/{repo}/prs/{pr_number}/comment")
async def post_comment(
    owner: str,
    repo: str,
    pr_number: int,
    body: dict,
    gh: GitHubService = Depends(get_github_service)
):
    try:
        success = gh.post_comment(owner, repo, pr_number, body.get("comment", ""))
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
