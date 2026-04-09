"""
test_integration.py
-------------------
Integration tests for the AI Code Reviewer API.
Tests the full request/response cycle for every major endpoint,
verifying status codes, response shapes, and data correctness.

Tools used: pytest, FastAPI TestClient (httpx under the hood)
Run with: pytest tests/test_integration.py -v
"""

import pytest
from conftest import MOCK_REPOS, MOCK_PRS, MOCK_REVIEW_TEXT


class TestHealth:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client):
        response = client.get('/health')
        assert response.status_code == 200

    def test_health_response_shape(self, client):
        data = client.get('/health').json()
        assert 'status' in data
        assert 'db_connected' in data
        assert 'version' in data

    def test_health_status_is_healthy(self, client):
        data = client.get('/health').json()
        assert data['status'] == 'healthy'

    def test_health_version_is_string(self, client):
        data = client.get('/health').json()
        assert isinstance(data['version'], str)
        assert len(data['version']) > 0


class TestRepositories:
    """Tests for the /repos endpoint."""

    def test_get_repos_returns_200(self, client):
        response = client.get('/repos', headers={'X-Github-Token': 'test_token'})
        assert response.status_code == 200

    def test_get_repos_returns_list(self, client):
        response = client.get('/repos', headers={'X-Github-Token': 'test_token'})
        data = response.json()
        assert isinstance(data, list)

    def test_get_repos_returns_correct_count(self, client):
        response = client.get('/repos', headers={'X-Github-Token': 'test_token'})
        data = response.json()
        assert len(data) == len(MOCK_REPOS)

    def test_get_repos_item_has_required_fields(self, client):
        response = client.get('/repos', headers={'X-Github-Token': 'test_token'})
        repo = response.json()[0]
        required_fields = ['id', 'name', 'full_name', 'owner', 'url', 'stars']
        for field in required_fields:
            assert field in repo, f"Missing field: {field}"

    def test_get_repos_without_token_returns_401(self, client):
        # Override to use a fresh client with no dependency override on get_github_service
        from fastapi.testclient import TestClient
        import main
        # Save overrides and clear
        saved = dict(main.app.dependency_overrides)
        main.app.dependency_overrides.clear()
        with TestClient(main.app, raise_server_exceptions=False) as fresh:
            response = fresh.get('/repos')
            assert response.status_code == 401
        # Restore
        main.app.dependency_overrides.update(saved)

    def test_get_repos_data_matches_mock(self, client):
        response = client.get('/repos', headers={'X-Github-Token': 'test_token'})
        repo = response.json()[0]
        assert repo['name'] == MOCK_REPOS[0]['name']
        assert repo['owner'] == MOCK_REPOS[0]['owner']


class TestPullRequests:
    """Tests for the /repos/{owner}/{repo}/prs endpoint."""

    OWNER = 'testuser'
    REPO = 'my-repo'

    def url(self):
        return f'/repos/{self.OWNER}/{self.REPO}/prs'

    def test_get_prs_returns_200(self, client):
        response = client.get(self.url(), headers={'X-Github-Token': 'test_token'})
        assert response.status_code == 200

    def test_get_prs_returns_list(self, client):
        response = client.get(self.url(), headers={'X-Github-Token': 'test_token'})
        assert isinstance(response.json(), list)

    def test_get_prs_count_matches_mock(self, client):
        response = client.get(self.url(), headers={'X-Github-Token': 'test_token'})
        assert len(response.json()) == len(MOCK_PRS)

    def test_pr_item_has_required_fields(self, client):
        response = client.get(self.url(), headers={'X-Github-Token': 'test_token'})
        pr = response.json()[0]
        required = ['id', 'number', 'title', 'author', 'state', 'created_at',
                    'additions', 'deletions', 'changed_files']
        for field in required:
            assert field in pr, f"Missing PR field: {field}"

    def test_pr_number_is_integer(self, client):
        response = client.get(self.url(), headers={'X-Github-Token': 'test_token'})
        pr = response.json()[0]
        assert isinstance(pr['number'], int)

    def test_pr_state_is_open(self, client):
        response = client.get(self.url(), headers={'X-Github-Token': 'test_token'})
        pr = response.json()[0]
        assert pr['state'] == 'open'

    def test_pr_additions_non_negative(self, client):
        response = client.get(self.url(), headers={'X-Github-Token': 'test_token'})
        pr = response.json()[0]
        assert pr['additions'] >= 0
        assert pr['deletions'] >= 0


class TestAIReview:
    """Tests for the POST /review/{owner}/{repo}/{pr_number} endpoint."""

    OWNER = 'testuser'
    REPO = 'my-repo'
    PR = 5

    def url(self):
        return f'/review/{self.OWNER}/{self.REPO}/{self.PR}'

    def headers(self):
        return {
            'X-Github-Token': 'test_token',
            'X-Google-Api-Key': 'test_api_key',
        }

    def test_review_returns_200(self, client):
        response = client.post(self.url(), headers=self.headers())
        assert response.status_code == 200

    def test_review_has_status_field(self, client):
        data = client.post(self.url(), headers=self.headers()).json()
        assert 'status' in data

    def test_review_status_is_success(self, client):
        data = client.post(self.url(), headers=self.headers()).json()
        assert data['status'] == 'success'

    def test_review_has_review_field(self, client):
        data = client.post(self.url(), headers=self.headers()).json()
        assert 'review' in data
        assert len(data['review']) > 0

    def test_review_has_confidence_score(self, client):
        data = client.post(self.url(), headers=self.headers()).json()
        assert 'confidence_score' in data
        score = data['confidence_score']
        assert isinstance(score, (int, float))
        assert 0 <= score <= 10

    def test_review_has_review_id(self, client):
        data = client.post(self.url(), headers=self.headers()).json()
        assert 'review_id' in data

    def test_review_content_contains_summary(self, client):
        data = client.post(self.url(), headers=self.headers()).json()
        assert 'Summary' in data['review'] or 'summary' in data['review'].lower()


class TestComments:
    """Tests for the POST /repos/{owner}/{repo}/prs/{number}/comment endpoint."""

    OWNER = 'testuser'
    REPO = 'my-repo'
    PR = 5

    def url(self):
        return f'/repos/{self.OWNER}/{self.REPO}/prs/{self.PR}/comment'

    def test_post_comment_returns_200(self, client):
        response = client.post(
            self.url(),
            headers={'X-Github-Token': 'test_token'},
            json={'comment': 'Great PR! Here is my review.'},
        )
        assert response.status_code == 200

    def test_post_comment_success_true(self, client):
        data = client.post(
            self.url(),
            headers={'X-Github-Token': 'test_token'},
            json={'comment': 'Nice work!'},
        ).json()
        assert data['success'] is True

    def test_post_comment_with_empty_body(self, client):
        response = client.post(
            self.url(),
            headers={'X-Github-Token': 'test_token'},
            json={'comment': ''},
        )
        # Should still return 200 (empty comment is valid per API contract)
        assert response.status_code == 200

    def test_post_comment_has_message_field(self, client):
        data = client.post(
            self.url(),
            headers={'X-Github-Token': 'test_token'},
            json={'comment': 'Hello'},
        ).json()
        assert 'message' in data


class TestHistory:
    """Tests for the /history endpoints."""

    def test_history_returns_200(self, client):
        response = client.get('/history')
        assert response.status_code == 200

    def test_history_has_required_fields(self, client):
        data = client.get('/history').json()
        assert 'total' in data
        assert 'reviews' in data
        assert 'limit' in data
        assert 'skip' in data

    def test_history_reviews_is_list(self, client):
        data = client.get('/history').json()
        assert isinstance(data['reviews'], list)

    def test_history_pagination_params(self, client):
        data = client.get('/history?limit=5&skip=0').json()
        assert data['limit'] == 5
        assert data['skip'] == 0

    def test_history_repo_endpoint_returns_200(self, client):
        response = client.get('/history/testuser/my-repo')
        assert response.status_code == 200

    def test_history_repo_endpoint_shape(self, client):
        data = client.get('/history/testuser/my-repo').json()
        assert 'owner' in data
        assert 'repo' in data
        assert 'reviews' in data

    def test_history_total_is_integer(self, client):
        data = client.get('/history').json()
        assert isinstance(data['total'], int)
        assert data['total'] >= 0
