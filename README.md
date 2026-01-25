# AI Code Reviewer – GitHub PR Analysis using LLMs

## Project Overview
AI Code Reviewer is a web-based system that analyzes GitHub pull requests using Large Language Models (LLMs) and provides automated code review feedback.

## Problem It Solves
Manual code reviews are time-consuming and inconsistent. Developers may miss bugs, security issues, or best practices due to time constraints.

## Target Users (Personas)
- Developer: Wants quick and accurate code reviews
- Team Lead: Wants consistent review standards
- Open Source Maintainer: Wants automated review assistance

## Vision Statement
To improve code quality and developer productivity by automating pull request reviews using AI.

## Key Features / Goals
- GitHub authentication
- Fetch GitHub pull requests
- AI-based code analysis
- Display review suggestions
- Post comments to GitHub PRs

## Success Metrics
- Number of PRs reviewed
- Reduction in manual review time
- Developer satisfaction

## Assumptions & Constraints
- GitHub API availability
- Internet connectivity required
- LLM API usage limits

---

## Branching Strategy
This project follows GitHub Flow.
- main branch contains stable code
- feature branches are used for development
- changes are merged via pull requests

---

## Quick Start – Local Development
1. Install Docker Desktop
2. Run:
   docker build -t ai-code-reviewer .
   docker run -p 8000:8000 ai-code-reviewer
3. Open http://localhost:8000

---

## Local Development Tools
- GitHub
- Docker Desktop
- Draw.io
- Figma
