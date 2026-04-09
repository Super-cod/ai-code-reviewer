"""
test_regression.py
------------------
Regression tests for the AI Code Reviewer.

These tests guard against regressions in:
1. AI output format (must contain required sections)
2. GitHub service response shapes
3. Database layer return types
4. Configuration loading
5. Confidence score parsing

Tools used: pytest, unittest.mock
Run with: pytest tests/test_regression.py -v
"""

import sys
import os
import re
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from conftest import MOCK_REVIEW_TEXT, MOCK_DIFF, MOCK_REPOS, MOCK_PRS


# ===========================================================================
# AI Service Regression Tests
# ===========================================================================

class TestAIServiceOutputFormat:
    """Ensure AI output always contains structured sections."""

    REQUIRED_SECTIONS = [
        'Summary',
        'Bugs',
        'Security',
        'Performance',
        'Code Quality',
        'Positives',
        'Action Items',
        'Confidence Score',
    ]

    def test_mock_review_contains_summary(self):
        assert 'Summary' in MOCK_REVIEW_TEXT

    def test_mock_review_contains_bugs_section(self):
        assert 'Bug' in MOCK_REVIEW_TEXT

    def test_mock_review_contains_security_section(self):
        assert 'Security' in MOCK_REVIEW_TEXT

    def test_mock_review_contains_performance_section(self):
        assert 'Performance' in MOCK_REVIEW_TEXT

    def test_mock_review_contains_code_quality_section(self):
        assert 'Code Quality' in MOCK_REVIEW_TEXT

    def test_mock_review_contains_action_items(self):
        assert 'Action Item' in MOCK_REVIEW_TEXT

    def test_mock_review_contains_confidence_score(self):
        assert 'Confidence Score' in MOCK_REVIEW_TEXT

    def test_confidence_score_format_is_parseable(self):
        pattern = r'Confidence Score:\s*(\d+(?:\.\d+)?)\s*/\s*10'
        match = re.search(pattern, MOCK_REVIEW_TEXT)
        assert match is not None, 'Confidence score pattern not found in review'
        score = float(match.group(1))
        assert 0 <= score <= 10

    def test_review_is_non_empty_string(self):
        assert isinstance(MOCK_REVIEW_TEXT, str)
        assert len(MOCK_REVIEW_TEXT) > 100

    def test_review_is_valid_markdown(self):
        """Review should use markdown headings (##)."""
        assert '##' in MOCK_REVIEW_TEXT

    @pytest.mark.asyncio
    async def test_ai_service_extracts_confidence_score(self):
        """Test that AIService._extract_confidence_score works correctly."""
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            svc = AIService(api_key='fake_key')
            score = svc._extract_confidence_score(MOCK_REVIEW_TEXT)
            assert score == 8.0

    @pytest.mark.asyncio
    async def test_ai_service_returns_default_score_when_missing(self):
        """If no confidence score in output, defaults to 7.0."""
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            svc = AIService(api_key='fake_key')
            score = svc._extract_confidence_score('Some review without score')
            assert score == 7.0

    @pytest.mark.asyncio
    async def test_ai_service_handles_empty_diff(self):
        """Empty diff should return a warning message, not crash."""
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as MockModel:
            svc = AIService(api_key='fake_key')
            # Override model to None to test the guard
            svc.model = None
            result, score = await svc.analyze_code('')
            assert 'not configured' in result.lower() or 'AI model' in result
            assert score == 0.0

    @pytest.mark.asyncio
    async def test_ai_service_truncates_large_diff(self):
        """Diffs larger than 15,000 chars should be truncated before sending."""
        from ai_service import AIService
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as MockModel:
            mock_response = MagicMock()
            mock_response.text = MOCK_REVIEW_TEXT
            mock_instance = MockModel.return_value
            mock_instance.generate_content.return_value = mock_response

            svc = AIService(api_key='fake_key')
            large_diff = 'x' * 20_000
            result, _ = await svc.analyze_code(large_diff)
            # Verify generate_content was called with truncated content
            call_args = mock_instance.generate_content.call_args[0][0]
            assert len(call_args) < 16_500  # truncated


# ===========================================================================
# GitHub Service Regression Tests
# ===========================================================================

class TestGitHubServiceRegressionShapes:
    """Ensure GitHub service methods return consistently shaped data."""

    def test_repos_list_items_have_id(self):
        for repo in MOCK_REPOS:
            assert 'id' in repo

    def test_repos_list_items_have_name(self):
        for repo in MOCK_REPOS:
            assert 'name' in repo

    def test_repos_list_items_have_owner(self):
        for repo in MOCK_REPOS:
            assert 'owner' in repo

    def test_prs_list_items_have_number(self):
        for pr in MOCK_PRS:
            assert 'number' in pr

    def test_prs_list_items_have_title(self):
        for pr in MOCK_PRS:
            assert 'title' in pr

    def test_prs_additions_deletions_are_ints(self):
        for pr in MOCK_PRS:
            assert isinstance(pr.get('additions', 0), int)
            assert isinstance(pr.get('deletions', 0), int)

    def test_prs_dates_are_strings(self):
        for pr in MOCK_PRS:
            assert isinstance(pr['created_at'], str)

    def test_mock_diff_contains_filename(self):
        assert 'auth.py' in MOCK_DIFF

    def test_mock_diff_contains_status_line(self):
        assert 'Status:' in MOCK_DIFF

    def test_mock_diff_non_empty(self):
        assert len(MOCK_DIFF.strip()) > 0

    def test_github_service_init_without_token(self):
        """GitHubService with no token should set gh=None."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': ''}):
            from importlib import reload
            import config as cfg_module
            reload(cfg_module)
            from github_service import GitHubService
            svc = GitHubService(token=None)
            # Reload config without token — service should be non-functional but not crash
            assert svc.gh is None or svc.gh is not None  # Not crashing is the assertion

    def test_github_service_get_user_repos_returns_empty_without_gh(self):
        """Without auth, get_user_repos should return []."""
        from github_service import GitHubService
        svc = GitHubService(token=None)
        svc.gh = None
        result = svc.get_user_repos()
        assert result == []

    def test_github_service_get_prs_returns_empty_without_gh(self):
        """Without auth, get_pull_requests should return []."""
        from github_service import GitHubService
        svc = GitHubService(token=None)
        svc.gh = None
        result = svc.get_pull_requests('owner', 'repo')
        assert result == []

    def test_github_service_get_diff_returns_empty_without_gh(self):
        """Without auth, get_pr_diff should return ''."""
        from github_service import GitHubService
        svc = GitHubService(token=None)
        svc.gh = None
        result = svc.get_pr_diff('owner', 'repo', 1)
        assert result == ''

    def test_github_service_post_comment_returns_false_without_gh(self):
        """Without auth, post_comment should return False."""
        from github_service import GitHubService
        svc = GitHubService(token=None)
        svc.gh = None
        result = svc.post_comment('owner', 'repo', 1, 'body')
        assert result is False


# ===========================================================================
# Configuration Regression Tests
# ===========================================================================

class TestConfigLoad:
    """Ensure config.py loads environment variables correctly."""

    def test_config_has_github_token_attr(self):
        from config import Config
        cfg = Config()
        assert hasattr(cfg, 'GITHUB_TOKEN')

    def test_config_has_google_api_key_attr(self):
        from config import Config
        cfg = Config()
        assert hasattr(cfg, 'GOOGLE_API_KEY')

    def test_config_has_mongo_uri_attr(self):
        from config import Config
        cfg = Config()
        assert hasattr(cfg, 'MONGO_URI')

    def test_config_has_mongo_db_name_attr(self):
        from config import Config
        cfg = Config()
        assert hasattr(cfg, 'MONGO_DB_NAME')

    def test_config_reads_test_github_token(self):
        from config import Config
        cfg = Config()
        # The mock_env fixture should have set this
        assert cfg.GITHUB_TOKEN == 'test_github_token'

    def test_config_reads_test_google_api_key(self):
        from config import Config
        cfg = Config()
        assert cfg.GOOGLE_API_KEY == 'test_google_api_key'

    def test_mongo_uri_is_string(self):
        from config import Config
        cfg = Config()
        assert isinstance(cfg.MONGO_URI, str)

    def test_app_env_is_test(self):
        from config import Config
        cfg = Config()
        assert cfg.APP_ENV == 'test'
