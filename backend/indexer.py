"""
indexer.py
----------
Code analysis pipeline:
  1. LlamaIndex (primary)  — creates vector index with Gemini embeddings, queries for report
  2. Direct Gemini (fallback) — sends all code in one large prompt

Both paths produce the same structured markdown report.
"""

import logging
import re
from typing import List, Dict, Tuple, Iterable, Optional

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"
GEMINI_MODEL_CANDIDATES = (
    DEFAULT_GEMINI_MODEL,
    "gemini-3-flash-preview",
    "gemini-3-flash-preview",
)

DEFAULT_EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_MODEL_CANDIDATES = (
    DEFAULT_EMBEDDING_MODEL,
    "text-embedding-005",
)

# ---------------------------------------------------------------------------
# Comprehensive analysis prompt
# ---------------------------------------------------------------------------
ANALYSIS_PROMPT = """
You are a principal software architect and security reviewer producing a production audit dossier.

Analyze the ENTIRE codebase deeply and return a long-form report that can be split into multiple dashboard pages.
Use these exact section headings and keep each section substantial with concrete evidence and implementation details.
For EVERY major section, include these subheadings in this order:
- ### What is happening
- ### What is wrong
- ### Why it matters
- ### What to do now
- ### Evidence (files/functions/flows)

## 📋 Executive Summary
- System purpose, product value, and deployment readiness.
- Current risk posture and engineering maturity level.
- High-level recommendation: GO / CONDITIONAL GO / NO GO.

## 🧭 System Landscape
- Modules, boundaries, service interactions, and trust boundaries.
- Data flow from user input to storage and outbound integrations.
- Architectural style (monolith/service-oriented/layered) and implications.

## 🏗️ Architecture Deep Dive
- Separation of concerns, coupling/cohesion, layering correctness.
- Explicit hotspots by file/folder with why they are hotspots.
- Design debt map with short-term and long-term impact.

## 🔐 Security Assessment
- Threat-focused review: authn/authz, secrets, injection risks, session/cookie security,
  validation/sanitization, dependency risk, logging exposure.
- Findings table with: severity, confidence, affected files, exploit scenario, remediation.
- Use severities: CRITICAL / HIGH / MEDIUM / LOW.

## ⚙️ Performance & Scalability
- CPU/memory/network/path-length concerns and algorithmic bottlenecks.
- Blocking I/O, repeated API calls, inefficient loops, serialization overhead.
- Capacity risks under load and concrete optimization plan.

## 🧪 Reliability & Testing Posture
- Test architecture quality, coverage gaps, missing integration paths.
- Failure modes, error handling quality, observability deficiencies.
- Release confidence level and what blocks safe rollout.

## 🧹 Code Quality & Maintainability
- Readability, naming, complexity, duplication, module churn risk.
- Refactoring priorities with expected ROI.
- Documentation quality and onboarding risk.

## 📦 Dependency & Supply Chain Review
- Key frameworks/libraries and purpose in system.
- Potentially outdated or risky packages and migration notes.
- Build/deploy pipeline weaknesses and hardening actions.

## 📍 File-Level Findings Matrix
- Provide at least 12 findings where possible.
- For each finding include: ID, category, severity, file path, evidence, impact, exact fix.

## 🗺️ Multi-Phase Remediation Roadmap
- Phase 1 (24-48h), Phase 2 (1-2 weeks), Phase 3 (1-2 months).
- Include owners, dependencies, and measurable success criteria.

## ✅ Strengths & Competitive Advantages
- What is already strong and should be preserved.

## 📊 Quantitative Scorecard
Rate each out of 10 with short justification:
- Architecture
- Security
- Performance
- Reliability
- Maintainability
- Testing
- Documentation
- **Overall Score: X/10**

## 🧩 Cross-Page Traceability Map
- Create explicit links between sections (example: architecture hotspot -> security risk -> roadmap fix).
- Mention dependency chains and execution flow transitions that explain root cause progression.
- Include a compact checklist of "done / in-progress / pending" controls for major risks.

---
**Confidence Score: X/10**
"""


def _normalize_model_name(model_name: str) -> str:
    return model_name if model_name.startswith("models/") else f"models/{model_name}"


def _iter_model_candidates() -> Iterable[str]:
    for model_name in GEMINI_MODEL_CANDIDATES:
        yield model_name
        yield _normalize_model_name(model_name)


def _iter_embedding_candidates() -> Iterable[str]:
    for model_name in EMBEDDING_MODEL_CANDIDATES:
        yield _normalize_model_name(model_name)


def _configure_llamaindex_models(api_key: str, temperature: float):
    from llama_index.llms.gemini import Gemini
    from llama_index.embeddings.gemini import GeminiEmbedding

    for model_name in _iter_model_candidates():
        try:
            llm = Gemini(
                model=model_name,
                api_key=api_key,
                temperature=temperature,
            )
        except Exception as exc:
            logger.warning("Gemini model %s unavailable for LlamaIndex: %s", model_name, exc)
            continue

        for embed_name in _iter_embedding_candidates():
            try:
                embed_model = GeminiEmbedding(
                    model_name=_normalize_model_name(embed_name),
                    api_key=api_key,
                )
                return llm, embed_model
            except Exception as exc:
                logger.warning("Gemini embedding model %s unavailable for LlamaIndex: %s", embed_name, exc)

    raise RuntimeError("No Gemini model/embedding candidate pair available")


# ---------------------------------------------------------------------------
# Primary: LlamaIndex + Gemini Embeddings
# ---------------------------------------------------------------------------

async def _analyze_with_llamaindex(
    files: List[Dict], api_key: str, repo_name: str
) -> Tuple[str, float]:
    """Build a VectorStoreIndex with Gemini embeddings, then query for a report."""
    from llama_index.core import VectorStoreIndex, Document, Settings

    llm, embed_model = _configure_llamaindex_models(api_key, temperature=0.1)
    Settings.llm = llm
    Settings.embed_model = embed_model
    Settings.chunk_size = 1024
    Settings.chunk_overlap = 128

    documents = [
        Document(
            text=f"### FILE: {f['path']}\n\n{f['content']}\n",
            metadata={"filename": f["path"], "repo": repo_name},
        )
        for f in files
    ]

    logger.info("🔨 Building vector index (%d documents)…", len(documents))
    index = VectorStoreIndex.from_documents(documents, show_progress=False)

    file_list = "\n".join(f"  • {f['path']} ({f.get('size', 0):,} bytes)" for f in files[:25])
    query = (
        f"Repository: {repo_name}\n"
        f"Files analysed ({len(files)}):\n{file_list}\n\n"
        + ANALYSIS_PROMPT
    )

    logger.info("🤖 Querying index for comprehensive report…")
    query_engine = index.as_query_engine(
        similarity_top_k=12,
        response_mode="tree_summarize",
    )
    response = query_engine.query(query)
    return str(response), _extract_confidence(str(response))


# ---------------------------------------------------------------------------
# Fallback: Direct Gemini (no embeddings — works always)
# ---------------------------------------------------------------------------

async def _analyze_direct_gemini(
    files: List[Dict], api_key: str, repo_name: str
) -> Tuple[str, float]:
    """Send all code in one large prompt to Gemini with fallback model selection."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = None
    last_error: Optional[Exception] = None
    for model_name in _iter_model_candidates():
        try:
            model = genai.GenerativeModel(
                model_name,
                generation_config={"temperature": 0.1, "max_output_tokens": 12288},
            )
            break
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini model %s unavailable for direct analysis: %s", model_name, exc)

    if model is None:
        raise last_error or RuntimeError("No Gemini model candidates available")

    # Build code context (respect token limits)
    blocks = []
    total = 0
    for f in files:
        block = f"\n=== {f['path']} ===\n{f['content']}\n"
        if total + len(block) > 700_000:
            break
        blocks.append(block)
        total += len(block)

    file_list = "\n".join(f"  • {f['path']}" for f in files[:25])
    prompt = (
        f"Repository: {repo_name}\n"
        f"Files analysed ({len(files)}):\n{file_list}\n\n"
        f"--- CODEBASE START ---\n{''.join(blocks)}\n--- CODEBASE END ---\n\n"
        + ANALYSIS_PROMPT
    )

    logger.info("🤖 Sending %d chars to Gemini directly (no index)…", len(prompt))
    response = model.generate_content(prompt)
    report = response.text
    return report, _extract_confidence(report)


async def _query_direct_gemini(
    files: List[Dict],
    query: str,
    api_key: str,
    repo_name: str,
) -> str:
    """Answer a repository chat query directly with Gemini, without vector embeddings."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = None
    last_error: Optional[Exception] = None
    for model_name in _iter_model_candidates():
        try:
            model = genai.GenerativeModel(
                model_name,
                generation_config={"temperature": 0.2, "max_output_tokens": 4096},
            )
            break
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini model %s unavailable for direct chat: %s", model_name, exc)

    if model is None:
        raise last_error or RuntimeError("No Gemini model candidates available")

    blocks = []
    total = 0
    for f in files:
        block = f"\n=== {f['path']} ===\n{f['content']}\n"
        if total + len(block) > 450_000:
            break
        blocks.append(block)
        total += len(block)

    prompt = (
        f"Repository: {repo_name}\n"
        "You are helping a developer understand this codebase. "
        "Answer using concrete file references and keep the response focused.\n\n"
        f"Question: {query}\n\n"
        f"--- CODEBASE START ---\n{''.join(blocks)}\n--- CODEBASE END ---\n"
    )

    logger.info("Direct chat mode: sending %d chars to Gemini (no index)", len(prompt))
    response = model.generate_content(prompt)
    return response.text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_codebase(
    files: List[Dict],
    api_key: str,
    repo_name: str = "Unknown",
    use_index: bool = True,
) -> Tuple[str, float]:
    """
    Analyse a codebase and return (report_markdown, confidence_score).

    Tries LlamaIndex vector index first; falls back to direct Gemini call.
    """
    if use_index:
        try:
            return await _analyze_with_llamaindex(files, api_key, repo_name)
        except Exception as exc:
            logger.warning("⚠️  LlamaIndex path failed (%s) — using direct Gemini.", exc)

    return await _analyze_direct_gemini(files, api_key, repo_name)


async def query_codebase(
    files: List[Dict],
    query: str,
    api_key: str,
    repo_name: str = "Unknown",
    use_index: bool = True,
) -> str:
    """Analyse a codebase for a specific query using LlamaIndex, with direct fallback."""
    if not use_index:
        return await _query_direct_gemini(files, query, api_key, repo_name)

    try:
        from llama_index.core import VectorStoreIndex, Document, Settings

        llm, embed_model = _configure_llamaindex_models(api_key, temperature=0.3)
        Settings.llm = llm
        Settings.embed_model = embed_model
        Settings.chunk_size = 1024
        Settings.chunk_overlap = 128

        documents = [
            Document(
                text=f"### FILE: {f['path']}\n\n{f['content']}\n",
                metadata={"filename": f["path"], "repo": repo_name},
            )
            for f in files
        ]

        index = VectorStoreIndex.from_documents(documents, show_progress=False)
        query_engine = index.as_query_engine(
            similarity_top_k=8,
            response_mode="tree_summarize",
        )
        response = query_engine.query(
            f"You are navigating the repository '{repo_name}'. Answer the user's question accurately using the provided code files. Be clear, concise, and include code snippets if helpful.\n\nQuestion: {query}"
        )
        return str(response)
    except Exception as exc:
        logger.warning("Chat LlamaIndex path failed (%s) - using direct Gemini.", exc)
        return await _query_direct_gemini(files, query, api_key, repo_name)

def _extract_confidence(text: str) -> float:
    for pattern in [
        r'Confidence Score[:\s*]+(\d+(?:\.\d+)?)\s*/\s*10',
        r'\*\*Confidence Score:\s*(\d+(?:\.\d+)?)/10\*\*',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return min(10.0, max(0.0, float(m.group(1))))
    return 7.5
