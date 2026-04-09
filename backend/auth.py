"""
auth.py
-------
GitHub OAuth 2.0 flow + signed session cookie management.

Flow:
  1. GET /auth/github        → redirect user to GitHub login
    2. GET /auth/github/callback → exchange code → store signed cookie → redirect to /dashboard
  3. GET /auth/status        → return current user info from session (no GitHub call)
  4. GET /auth/me            → return full GitHub user profile (requires valid session)
  5. POST /auth/set-gemini-key → store Gemini API key in session
  6. GET /auth/logout        → clear cookie → redirect to /

Session cookie: "ai_reviewer_session"
Payload: { "github_token": str, "gemini_key": str | None }
"""

import logging
import httpx
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel

from config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

COOKIE_NAME = "ai_reviewer_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7   # 7 days

_signer = URLSafeTimedSerializer(config.SECRET_KEY, salt="ai-code-reviewer-session")


def _sign(payload: dict) -> str:
    return _signer.dumps(payload)


def _unsign(token: str) -> dict:
    """Raises HTTPException 401 on invalid / expired token."""
    try:
        return _signer.loads(token, max_age=COOKIE_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Session expired. Please login again.")
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid session. Please login again.")


def get_session(request: Request) -> dict:
    """Read and validate the session cookie. Returns payload dict."""
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated. Please login with GitHub.")
    return _unsign(raw)


def get_github_token_from_session(request: Request) -> str:
    """Extract the GitHub token from the session cookie."""
    session = get_session(request)
    token = session.get("github_token")
    if not token:
        raise HTTPException(status_code=401, detail="GitHub token not found in session.")
    return token


def get_gemini_key_from_session(request: Request) -> str:
    """Get Gemini key: session → env config."""
    try:
        session = get_session(request)
        key = session.get("gemini_key") or config.GOOGLE_API_KEY
    except HTTPException:
        key = config.GOOGLE_API_KEY
    if not key:
        raise HTTPException(
            status_code=401,
            detail="Gemini API key not set. Go to Settings and enter your key.",
        )
    return key


def _set_session_cookie(response: Response, payload: dict) -> None:
    signed = _sign(payload)
    response.set_cookie(
        key=COOKIE_NAME,
        value=signed,
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_SCOPE = "repo read:user"


@router.get("/github", summary="Redirect to GitHub OAuth login")
def github_login():
    """Step 1 — redirect the user to GitHub's OAuth consent screen."""
    if not config.GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.",
        )
    params = (
        f"client_id={config.GITHUB_CLIENT_ID}"
        f"&redirect_uri={config.GITHUB_REDIRECT_URI}"
        f"&scope={GITHUB_SCOPE.replace(' ', '%20')}"
    )
    return RedirectResponse(f"{GITHUB_AUTHORIZE_URL}?{params}", status_code=302)


@router.get("/github/callback", summary="GitHub OAuth callback")
async def github_callback(code: str = None, error: str = None):
    """Step 2 — exchange code for access token, set session cookie."""
    if error or not code:
        return RedirectResponse("/login?auth_error=access_denied", status_code=302)

    # Exchange code → access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": config.GITHUB_CLIENT_ID,
                "client_secret": config.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": config.GITHUB_REDIRECT_URI,
            },
            timeout=10,
        )

    data = token_resp.json()
    access_token = data.get("access_token")
    if not access_token:
        logger.error("OAuth token exchange failed: %s", data)
        return RedirectResponse("/login?auth_error=token_exchange_failed", status_code=302)

    # Build session payload
    payload = {
        "github_token": access_token,
        "gemini_key": config.GOOGLE_API_KEY or None,   # pre-populate from server config
    }

    # Redirect to dashboard
    redirect = RedirectResponse("/dashboard", status_code=302)
    _set_session_cookie(redirect, payload)
    logger.info("OAuth login successful — session cookie set.")
    return redirect


@router.get("/status", summary="Check authentication status")
async def auth_status(request: Request):
    """
    Returns session info without calling GitHub API.
    Used by the frontend to determine if the user is logged in.
    """
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return JSONResponse({"authenticated": False})
    try:
        session = _unsign(raw)
        has_gemini = bool(session.get("gemini_key"))
        return JSONResponse({
            "authenticated": True,
            "has_gemini_key": has_gemini,
        })
    except HTTPException:
        return JSONResponse({"authenticated": False})


@router.get("/me", summary="Get current GitHub user profile")
async def get_me(request: Request):
    """Return the authenticated user's GitHub profile."""
    token = get_github_token_from_session(request)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GITHUB_USER_URL,
            headers={"Authorization": f"token {token}", "Accept": "application/json"},
            timeout=10,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch GitHub profile.")
    user = resp.json()
    return {
        "login": user.get("login"),
        "name": user.get("name") or user.get("login"),
        "avatar_url": user.get("avatar_url"),
        "public_repos": user.get("public_repos"),
        "html_url": user.get("html_url"),
    }


class GeminiKeyRequest(BaseModel):
    gemini_key: str


@router.post("/set-gemini-key", summary="Store Gemini API key in session")
async def set_gemini_key(body: GeminiKeyRequest, request: Request, response: Response):
    """Store / update the Gemini API key inside the existing session cookie."""
    session = get_session(request)
    session["gemini_key"] = body.gemini_key.strip()
    _set_session_cookie(response, session)
    return {"success": True, "message": "Gemini API key saved to session."}


@router.get("/logout", summary="Logout — clear session")
def logout():
    redirect = RedirectResponse("/login", status_code=302)
    redirect.delete_cookie(COOKIE_NAME, path="/")
    return redirect
