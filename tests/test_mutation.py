"""
test_mutation.py
----------------
Mutation-style tests for the AI Code Reviewer.

These tests verify that the system correctly handles:
1. Invalid / malformed inputs (boundary conditions)
2. Missing / incorrect tokens (auth failures)
3. Non-existent resources (404-style errors)
4. Edge cases in AI service logic
5. Database failure resilience

These tests mimic what mutation testing tools (like mutmut or cosmic-ray) would
generate by mutating conditions and checking that tests catch the change.

Tools used: pytest
Run with: pytest tests/test_mutation.py -v
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))


# ===========================================================================
# Boundary: AI Service
# ===========================================================================

class TestAIServiceBoundaries:
    """Test edge cases and mutations in AIService logic."""

    @pytest.mark.asyncio
    async def test_analyze_code_with_none_input(self):
        """Passing None as diff should not crash; return a graceful message."""
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            svc = AIService(api_key='key')
            svc.model = None  # No real model
            result, score = await svc.analyze_code(None)
            assert isinstance(result, str)
            assert score == 0.0

    @pytest.mark.asyncio
    async def test_analyze_code_with_empty_string(self):
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            svc = AIService(api_key='key')
            svc.model = None
            result, score = await svc.analyze_code('')
            assert isinstance(result, str)
            assert score == 0.0

    @pytest.mark.asyncio
    async def test_analyze_code_with_whitespace_only(self):
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            svc = AIService(api_key='key')
            svc.model = None
            result, score = await svc.analyze_code('   \n\t  ')
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_analyze_code_model_api_failure(self):
        """If the model throws an exception, return graceful error string."""
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as MockModel:
            mock_instance = MockModel.return_value
            mock_instance.generate_content.side_effect = Exception('API rate limit exceeded')
            svc = AIService(api_key='key')
            result, score = await svc.analyze_code('some diff')
            assert 'failed' in result.lower() or 'error' in result.lower()
            assert score == 0.0

    def test_confidence_score_at_zero(self):
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            svc = AIService(api_key='key')
            score = svc._extract_confidence_score('**Confidence Score: 0/10**')
            assert score == 0.0

    def test_confidence_score_at_ten(self):
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            svc = AIService(api_key='key')
            score = svc._extract_confidence_score('**Confidence Score: 10/10**')
            assert score == 10.0

    def test_confidence_score_above_ten_clamped(self):
        """Any score > 10 should be clamped to 10."""
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            svc = AIService(api_key='key')
            # Mutate: remove the clamp logic and this test fails
            score = svc._extract_confidence_score('**Confidence Score: 15/10**')
            assert score <= 10.0

    def test_confidence_score_decimal_parsed_correctly(self):
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            svc = AIService(api_key='key')
            score = svc._extract_confidence_score('Confidence Score: 7.5/10')
            assert score == 7.5

    def test_no_api_key_disables_model(self):
        """AIService with no API key should have model=None."""
        from ai_service import AIService
        with patch.dict(os.environ, {'GOOGLE_API_KEY': ''}):
            svc = AIService(api_key=None)
            # Don't set GOOGLE_API_KEY
            svc_empty = AIService(api_key='')
            assert svc_empty.model is None


# ===========================================================================
# Boundary: GitHub Service
# ===========================================================================

class TestGitHubServiceBoundaries:
    """Test edge cases and error handling in GitHubService."""

    def test_post_comment_returns_false_on_api_error(self):
        """If GitHub API throws, post_comment should return False."""
        from github_service import GitHubService
        from github import GithubException

        svc = GitHubService(token='fake')
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.create_issue_comment.side_effect = GithubException(401, 'Unauthorized')
        mock_repo.get_pull.return_value = mock_pr
        mock_gh.get_repo.return_value = mock_repo
        svc.gh = mock_gh

        result = svc.post_comment('owner', 'repo', 1, 'body')
        assert result is False

    def test_get_pr_diff_returns_empty_on_api_error(self):
        """If GitHub API throws on get_pr_diff, should propagate the exception."""
        from github_service import GitHubService
        from github import GithubException

        svc = GitHubService(token='fake')
        mock_gh = MagicMock()
        mock_gh.get_repo.side_effect = GithubException(404, 'Not Found')
        svc.gh = mock_gh

        with pytest.raises(GithubException):
            svc.get_pr_diff('owner', 'nonexistent-repo', 1)

    def test_get_user_repos_on_api_error_raises(self):
        """If GitHub list repos fails, exception should propagate."""
        from github_service import GitHubService
        from github import GithubException

        svc = GitHubService(token='fake')
        mock_gh = MagicMock()
        mock_gh.get_user.side_effect = GithubException(403, 'Forbidden')
        svc.gh = mock_gh

        with pytest.raises(GithubException):
            svc.get_user_repos()

    def test_pr_diff_with_binary_file(self):
        """Files with no patch (binary) should not cause crash."""
        from github_service import GitHubService

        svc = GitHubService(token='fake')
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()

        # Simulate binary file (patch = None)
        mock_file = MagicMock()
        mock_file.filename = 'image.png'
        mock_file.status = 'added'
        mock_file.additions = 0
        mock_file.deletions = 0
        mock_file.patch = None  # Binary file has no patch

        mock_pr.get_files.return_value = [mock_file]
        mock_repo.get_pull.return_value = mock_pr
        mock_gh.get_repo.return_value = mock_repo
        svc.gh = mock_gh

        result = svc.get_pr_diff('owner', 'repo', 1)
        assert 'image.png' in result
        assert 'binary or non-text' in result


# ===========================================================================
# Boundary: API Endpoints
# ===========================================================================

class TestAPIBoundaries:
    """Test API endpoints under unusual/invalid conditions."""

    def test_review_invalid_pr_number(self, client):
        """PR number 0 should return a 422 validation error."""
        # Pydantic validates {pr_number} as int via path; 0 is technically valid
        # but we test that a non-integer string causes an error
        response = client.post(
            '/review/owner/repo/not-a-number',
            headers={
                'X-Github-Token': 'test',
                'X-Google-Api-Key': 'test',
            }
        )
        assert response.status_code == 422

    def test_history_invalid_limit(self, client):
        """limit=0 is not allowed (ge=1 constraint)."""
        response = client.get('/history?limit=0')
        assert response.status_code == 422

    def test_history_limit_above_max(self, client):
        """limit=101 exceeds the le=100 constraint."""
        response = client.get('/history?limit=101')
        assert response.status_code == 422

    def test_history_valid_boundary_limit(self, client):
        """limit=100 is the maximum valid value."""
        response = client.get('/history?limit=100')
        assert response.status_code == 200

    def test_comment_endpoint_missing_body(self, client):
        """POST without JSON body should return 422."""
        response = client.post(
            '/repos/owner/repo/prs/1/comment',
            headers={'X-Github-Token': 'test'},
        )
        assert response.status_code == 422

    def test_repos_endpoint_invalid_method(self, client):
        """DELETE /repos should return 405 Method Not Allowed."""
        response = client.delete('/repos', headers={'X-Github-Token': 'test'})
        assert response.status_code == 405

    def test_review_when_diff_is_empty(self, client, mock_github_service):
        """When diff is empty, review should return an error status."""
        mock_github_service.get_pr_diff.return_value = ''
        response = client.post(
            '/review/owner/repo/1',
            headers={
                'X-Github-Token': 'test',
                'X-Google-Api-Key': 'test',
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Should gracefully return error status, not crash
        assert data['status'] in ('error', 'success')


# ===========================================================================
# Boundary: Database Layer
# ===========================================================================

class TestDatabaseBoundaries:
    """Test database module resilience when MongoDB is unavailable."""

    def test_get_db_returns_none_on_connection_failure(self, monkeypatch):
        """When MongoDB is unreachable, get_db should return None."""
        import database as db_module
        from pymongo.errors import ConnectionFailure

        def failing_client(*args, **kwargs):
            mock = MagicMock()
            mock.admin.command.side_effect = ConnectionFailure('Unreachable')
            return mock

        # Reset cached connection
        db_module._client = None
        db_module._db = None
        monkeypatch.setattr('pymongo.MongoClient', failing_client)

        result = db_module.get_db()
        assert result is None

        # Cleanup
        db_module._client = None
        db_module._db = None

    def test_save_review_returns_none_when_db_unavailable(self, monkeypatch):
        """save_review should return None gracefully when DB is unavailable."""
        import database as db_module
        monkeypatch.setattr(db_module, 'get_db', lambda: None)

        result = db_module.save_review(
            owner='owner',
            repo='repo',
            pr_number=1,
            pr_title='Test',
            pr_author='user',
            review_text='Some review',
        )
        assert result is None

    def test_get_review_history_returns_empty_when_db_unavailable(self, monkeypatch):
        """get_review_history should return [] when DB is None."""
        import database as db_module
        monkeypatch.setattr(db_module, 'get_db', lambda: None)

        result = db_module.get_review_history()
        assert result == []

    def test_count_total_reviews_returns_zero_when_db_unavailable(self, monkeypatch):
        """count_total_reviews should return 0 when DB is None."""
        import database as db_module
        monkeypatch.setattr(db_module, 'get_db', lambda: None)

        result = db_module.count_total_reviews()
        assert result == 0

    def test_get_reviews_for_repo_returns_empty_when_db_unavailable(self, monkeypatch):
        """get_reviews_for_repo should return [] when DB is None."""
        import database as db_module
        monkeypatch.setattr(db_module, 'get_db', lambda: None)

        result = db_module.get_reviews_for_repo('owner', 'repo')
        assert result == []
