"""
conftest.py
-----------
Shared pytest fixtures. External services (GitHub, Gemini) are mocked.
Database uses SQLite in-memory via SQLAlchemy (replaces MongoDB mock).
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Make backend importable
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

# ---------------------------------------------------------------------------
# Force SQLite for tests (overrides Neon URL before any import reads config)
# ---------------------------------------------------------------------------
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reviews.db')
os.environ.setdefault('GITHUB_TOKEN', 'test_github_token')
os.environ.setdefault('GOOGLE_API_KEY', 'test_google_api_key')
os.environ.setdefault('APP_ENV', 'test')


# ---------------------------------------------------------------------------
# Mock Data
# ---------------------------------------------------------------------------

MOCK_REPOS = [
    {
        'id': 1,
        'name': 'my-repo',
        'full_name': 'testuser/my-repo',
        'owner': 'testuser',
        'description': 'A test repository',
        'url': 'https://github.com/testuser/my-repo',
        'stars': 42,
        'language': 'Python',
        'private': False,
    }
]

MOCK_PRS = [
    {
        'id': 101,
        'number': 5,
        'title': 'Add user authentication',
        'author': 'devuser',
        'author_avatar': 'https://avatars.githubusercontent.com/u/1',
        'state': 'open',
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-16T08:00:00',
        'url': 'https://github.com/testuser/my-repo/pull/5',
        'additions': 120,
        'deletions': 30,
        'changed_files': 4,
        'base_branch': 'main',
        'head_branch': 'feature/auth',
        'body': 'Adds JWT-based authentication.',
    }
]

MOCK_DIFF = """--- a/auth.py
+++ b/auth.py
Status: modified | +10 additions / -2 deletions
@@ -1,5 +1,13 @@
+import jwt
+import os
+
 def authenticate(username, password):
-    return True
+    if username == 'admin' and password == os.getenv('ADMIN_PASS'):
+        token = jwt.encode({'user': username}, 'secret', algorithm='HS256')
+        return token
+    return None
"""

MOCK_REVIEW_TEXT = """## 🔍 Summary
This PR adds JWT-based authentication. The approach is functional but has security concerns.

## 🐛 Bugs & Logic Errors
No bugs detected.

## 🔒 Security Issues
- Hardcoded 'secret' as the JWT signing key is dangerous.
- Timing-attack risk on password comparison.

## ⚡ Performance
✅ No performance concerns found.

## 📐 Code Quality & Best Practices
- Separate auth logic into a dedicated service class.

## ✅ Positives
- Good use of environment variables for sensitive config.

## 📋 Action Items
1. Replace hardcoded 'secret' with a secure env variable.
2. Use `hmac.compare_digest` for password comparison.

---
**Confidence Score: 8/10**
"""


# ---------------------------------------------------------------------------
# Autouse: patch database layer for all tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    """
    Replace all database.py calls with in-memory stubs so tests never
    touch Neon or any real PostgreSQL instance.
    """
    import database as db_module

    monkeypatch.setattr(db_module, 'init_db', lambda: True)
    monkeypatch.setattr(db_module, 'close_db', lambda: None)
    monkeypatch.setattr(
        db_module, 'save_review',
        lambda **kw: 42,   # fake int PK
    )
    monkeypatch.setattr(
        db_module, 'get_review_history',
        lambda **kw: [
            {
                'id': 1,
                'owner': 'testuser',
                'repo': 'my-repo',
                'pr_number': 5,
                'pr_title': 'Add user authentication',
                'pr_author': 'devuser',
                'review_text': MOCK_REVIEW_TEXT,
                'confidence_score': 8.0,
                'reviewed_at': datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc).isoformat(),
            }
        ],
    )
    monkeypatch.setattr(
        db_module, 'get_reviews_for_repo',
        lambda **kw: [
            {
                'id': 1,
                'owner': 'testuser',
                'repo': 'my-repo',
                'pr_number': 5,
                'pr_title': 'Add user authentication',
                'pr_author': 'devuser',
                'review_text': MOCK_REVIEW_TEXT,
                'confidence_score': 8.0,
                'reviewed_at': datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc).isoformat(),
            }
        ],
    )
    monkeypatch.setattr(db_module, 'count_total_reviews', lambda: 1)


# ---------------------------------------------------------------------------
# Service mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_github_service():
    svc = MagicMock()
    svc.get_user_repos.return_value = MOCK_REPOS
    svc.get_pull_requests.return_value = MOCK_PRS
    svc.get_pr_details.return_value = {
        'id': 101, 'number': 5, 'title': 'Add user authentication',
        'author': 'devuser', 'state': 'open',
        'created_at': '2024-01-15T10:00:00',
        'url': 'https://github.com/testuser/my-repo/pull/5',
        'additions': 120, 'deletions': 30, 'changed_files': 4,
    }
    svc.get_pr_diff.return_value = MOCK_DIFF
    svc.post_comment.return_value = True
    return svc


@pytest.fixture
def mock_ai_service():
    svc = MagicMock()
    svc.analyze_code = AsyncMock(return_value=(MOCK_REVIEW_TEXT, 8.0))
    return svc


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------

@pytest.fixture
def client(mock_github_service, mock_ai_service):
    from fastapi.testclient import TestClient
    from main import app, get_github_service, get_ai_service

    app.dependency_overrides[get_github_service] = lambda: mock_github_service
    app.dependency_overrides[get_ai_service] = lambda: mock_ai_service

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
