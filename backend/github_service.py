from github import Github, Auth
from config import config

class GitHubService:
    def __init__(self, token: str = None):
        self.token = token or config.GITHUB_TOKEN
        if self.token:
            self.gh = Github(auth=Auth.Token(self.token))
        else:
            self.gh = None

    def get_user_repos(self):
        if not self.gh:
            return []
        user = self.gh.get_user()
        repos = []
        for repo in user.get_repos():
            repos.append({
                "id": repo.id,
                "name": repo.name,
                "owner": repo.owner.login,
                "description": repo.description
            })
        return repos

    def get_pull_requests(self, owner: str, repo_name: str):
        if not self.gh:
            return []
        repo = self.gh.get_repo(f"{owner}/{repo_name}")
        prs = []
        for pr in repo.get_pulls(state='open'):
            prs.append({
                "id": pr.id,
                "number": pr.number,
                "title": pr.title,
                "author": pr.user.login,
                "state": pr.state,
                "created_at": pr.created_at.isoformat()
            })
        return prs

    def get_pr_diff(self, owner: str, repo_name: str, pr_number: int):
        if not self.gh:
            return ""
        repo = self.gh.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        
        # Get the files and their changes
        files = pr.get_files()
        diff_text = ""
        for file in files:
            diff_text += f"File: {file.filename}\n"
            diff_text += f"Status: {file.status}\n"
            diff_text += f"Patch:\n{file.patch}\n\n"
        return diff_text

    def post_comment(self, owner: str, repo_name: str, pr_number: int, body: str):
        if not self.gh:
            return False
        repo = self.gh.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(body)
        return True
