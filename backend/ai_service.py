"""
ai_service.py
-------------
Handles all AI-powered code review logic using Google Gemini.
Includes structured prompt engineering and confidence score extraction.
"""

import re
import logging
from typing import Tuple, Optional

import google.generativeai as genai
from config import config

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"
GEMINI_MODEL_CANDIDATES = (
    DEFAULT_GEMINI_MODEL,
    "gemini-3-flash-preview",
    "gemini-3-flash-preview",
)

# ---------------------------------------------------------------------------
# System Prompt — Engineering for structured, high-quality reviews
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an elite principal engineer and software auditor.
Produce an expert-grade, deeply detailed PR review dossier, not a short summary.

Output must be comprehensive and structured. If the review feels shallow, expand automatically.
Use concrete evidence from the diff and reference filenames/line contexts whenever possible.
For EVERY major section, include these exact subheadings in this order:
- ### What is happening
- ### What is wrong
- ### Why it matters
- ### What to do now
- ### Evidence

You MUST format the response with these exact sections:

## 📌 Executive Summary
- What changed, intended impact, and release readiness.
- One clear verdict: APPROVE / NEEDS_CHANGES / BLOCKER.

## 🧠 Functional Correctness Review
- Logic flaws, edge cases, missing branches, state handling risks.
- Include root cause and user-visible impact for each finding.

## 🔐 Security Review
- Authentication/authorization, input validation, injection risk, secrets leakage,
  unsafe deserialization, SSRF, XSS, CSRF, privilege escalation.
- Classify each finding as CRITICAL/HIGH/MEDIUM/LOW.

## ⚡ Performance & Scalability
- Complexity pitfalls, heavy loops, blocking operations, repeated calls,
  memory pressure, network inefficiency, caching opportunities.

## 🧱 Architecture & Design Quality
- Layering, separation of concerns, coupling/cohesion, API boundaries,
  extensibility and maintainability implications.

## 🧪 Testing & Reliability Gaps
- Missing tests and likely regression vectors.
- Include specific test ideas with input/expected behavior.

## 📎 File-by-File Findings
- Provide a compact matrix per affected file with key risks and recommended fixes.

## ✅ Strengths
- What is already strong and should be preserved.

## 🛠️ Action Plan (Prioritized)
- Numbered plan with immediate, short-term, and medium-term remediation steps.
- Include estimated implementation effort for each step.

## 🧩 Connected Change Narrative
- Explain the end-to-end change flow across files/modules.
- Map root causes to concrete fixes and post-fix validation steps.
- Document which pages in a larger report should consume each finding (executive, architecture, security, roadmap).

## 📊 Scorecard
- Correctness: X/10
- Security: X/10
- Performance: X/10
- Maintainability: X/10
- Testability: X/10
- **Overall Score: X/10**

**Confidence Score: X/10**

Rules:
- Be highly specific, avoid generic advice.
- Always include at least several concrete findings when evidence exists.
- If no issue in a category, explicitly justify why.
"""


class AIService:
    """Wraps the Google Gemini API for PR code review."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.GOOGLE_API_KEY
        self.model = None
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = self._create_model()
                logger.info("✅ Gemini AI service initialised.")
            except Exception as e:
                logger.error("Failed to initialise Gemini model: %s", e)
        else:
            logger.warning("⚠️  No GOOGLE_API_KEY provided. AI service disabled.")

    def _create_model(self):
        last_error: Optional[Exception] = None
        for model_name in GEMINI_MODEL_CANDIDATES:
            try:
                return genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=SYSTEM_PROMPT,
                )
            except Exception as exc:
                last_error = exc
                logger.warning("Gemini model %s unavailable: %s", model_name, exc)

        if last_error:
            raise last_error
        raise RuntimeError("No Gemini model candidates available")

    async def analyze_code(self, diff_text: str) -> Tuple[str, float]:
        """
        Analyse a PR diff and return structured review text and confidence score.

        Args:
            diff_text: The unified diff string from GitHub.

        Returns:
            Tuple of (review_markdown: str, confidence_score: float)
        """
        if not self.model:
            return (
                "AI model not configured. Please provide a valid GOOGLE_API_KEY.",
                0.0,
            )

        if not diff_text or not diff_text.strip():
            return "⚠️ No code changes were found in this PR to review.", 0.0

        # Truncate extremely large diffs to avoid token limits
        max_diff_chars = 30_000
        if len(diff_text) > max_diff_chars:
            diff_text = diff_text[:max_diff_chars] + "\n\n... [diff truncated for length] ..."

        user_message = f"Please review the following Pull Request diff:\n\n```diff\n{diff_text}\n```"

        try:
            response = self.model.generate_content(user_message)
            review_text = response.text
            confidence = self._extract_confidence_score(review_text)
            return review_text, confidence
        except Exception as e:
            logger.error("AI analysis failed: %s", e)
            return f"❌ AI analysis failed: {str(e)}", 0.0

    def _extract_confidence_score(self, review_text: str) -> float:
        """
        Parse the confidence score from the structured AI response.
        Expects a line like: **Confidence Score: 8/10**

        Returns:
            float between 0.0 and 10.0, defaults to 7.0 if not found.
        """
        pattern = r"Confidence Score:\s*(\d+(?:\.\d+)?)\s*/\s*10"
        match = re.search(pattern, review_text, re.IGNORECASE)
        if match:
            try:
                score = float(match.group(1))
                return min(max(score, 0.0), 10.0)
            except ValueError:
                pass
        return 7.0  # sensible default
