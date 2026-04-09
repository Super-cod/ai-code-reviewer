'use strict';

const state = {
    user: null,
    repos: [],
    prs: [],
    selectedRepo: null,
    selectedPr: null,
    history: [],
    currentReview: null,
    activeReportPage: 'executive',
    mermaidRendered: false,
};

const PAGE_DOCS = {
    overview: {
        purpose: 'Operational snapshot of repositories, PRs, health, and pipeline readiness.',
        inputs: 'Session status, /repos, /history, /health.',
        outputs: 'KPI cards, timeline state, language mix bars.',
        actions: 'Use for quick health checks before detailed analysis.',
    },
    repositories: {
        purpose: 'Repository inventory and selection context.',
        inputs: '/repos response data.',
        outputs: 'Repository selector and metadata table.',
        actions: 'Choose repository to scope PR and analysis pages.',
    },
    pullrequests: {
        purpose: 'Open PR listing for selected repository.',
        inputs: '/repos/{owner}/{repo}/prs response data.',
        outputs: 'PR selector with change metrics and branch info.',
        actions: 'Pick the target PR for deep analysis.',
    },
    analysis: {
        purpose: 'Execution control for PR + deep repo analysis pipeline.',
        inputs: 'Selected repo and PR; /review endpoint.',
        outputs: 'Pipeline progress bars and review payload in memory.',
        actions: 'Run deep analysis and transition to report page.',
    },
    report: {
        purpose: 'Multi-page report viewer with issue metrics and structured documentation.',
        inputs: '/review response including report_pages and page_documentation.',
        outputs: 'Narrative report pages, findings list, per-page docs and cross-links.',
        actions: 'Review findings and optionally post PR comment.',
    },
    history: {
        purpose: 'Access persisted review records for comparison and audits.',
        inputs: '/history and /history/review/{id}.',
        outputs: 'Historical review table and report restoration.',
        actions: 'Open past reviews and compare evolution over time.',
    },
    docs: {
        purpose: 'Central architecture and developer-facing documentation of this UI.',
        inputs: 'Static architecture spec + runtime state summaries.',
        outputs: 'Mermaid diagrams, page docs catalog, endpoint map.',
        actions: 'Understand how code and pages connect end-to-end.',
    },
    settings: {
        purpose: 'Session controls for runtime behavior and API key storage.',
        inputs: 'Gemini key input and session endpoints.',
        outputs: 'Saved key state and immediate UX feedback.',
        actions: 'Configure model key and session preferences.',
    },
};

const $ = id => document.getElementById(id);
const esc = value => String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function showToast(message, type = 'success') {
    const toast = $('toast');
    toast.textContent = message;
    toast.className = `toast ${type === 'error' ? 'error' : ''}`.trim();
    toast.classList.remove('hidden');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.add('hidden'), 3000);
}

async function api(path, opts = {}) {
    const res = await fetch(path, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        ...opts,
    });
    const data = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
}

function setActiveView(name) {
    document.querySelectorAll('.view').forEach(v => {
        v.classList.toggle('active', v.id === `view-${name}`);
    });
    document.querySelectorAll('#dashboard-nav button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === name);
    });

    const titles = {
        overview: ['Overview', 'Platform activity and analysis readiness'],
        repositories: ['Repositories', 'Source control inventory and selection'],
        pullrequests: ['Pull Requests', 'Open pull requests for selected repository'],
        analysis: ['Analysis Studio', 'Run clone + index + AI synthesis pipeline'],
        report: ['Deep Report', 'PR findings and repository-wide analysis'],
        history: ['History', 'Persisted review records and metadata'],
        docs: ['Docs & Architecture', 'Frontend architecture maps and page-level documentation'],
        settings: ['Settings', 'Session and model runtime configuration'],
    };
    $('top-title').innerHTML = `<strong>${titles[name][0]}</strong>`;
    $('top-subtitle').textContent = titles[name][1];

    if (name === 'docs') {
        renderDocsArchitecture();
    }
}

function renderDocsCatalog() {
    const target = $('page-docs-catalog');
    if (!target) return;

    target.innerHTML = Object.entries(PAGE_DOCS).map(([page, info]) => `
        <article class="doc-card">
            <h4>${esc(reportPageLabel(page) === page ? page.charAt(0).toUpperCase() + page.slice(1) : reportPageLabel(page))} Page</h4>
            <div class="doc-row"><strong>Purpose:</strong> ${esc(info.purpose)}</div>
            <div class="doc-row"><strong>Inputs:</strong> ${esc(info.inputs)}</div>
            <div class="doc-row"><strong>Outputs:</strong> ${esc(info.outputs)}</div>
            <div class="doc-row"><strong>Actions:</strong> ${esc(info.actions)}</div>
        </article>
    `).join('');
}

function renderEndpointDocs() {
    const target = $('endpoint-docs');
    if (!target) return;

    const repoLabel = state.selectedRepo ? `${state.selectedRepo.owner}/${state.selectedRepo.name}` : '{owner}/{repo}';
    const prLabel = state.selectedPr ? state.selectedPr.number : '{pr_number}';
    target.innerHTML = `
        <div class="timeline-item"><strong>Session bootstrap:</strong> GET /auth/status, GET /auth/me</div>
        <div class="timeline-item"><strong>Repository discovery:</strong> GET /repos</div>
        <div class="timeline-item"><strong>Pull request fetch:</strong> GET /repos/${esc(repoLabel)}/prs</div>
        <div class="timeline-item"><strong>Deep analysis run:</strong> POST /review/${esc(repoLabel)}/${esc(String(prLabel))}</div>
        <div class="timeline-item"><strong>Comment sync:</strong> POST /repos/${esc(repoLabel)}/prs/${esc(String(prLabel))}/comment</div>
        <div class="timeline-item"><strong>History:</strong> GET /history and GET /history/review/{id}</div>
    `;
}

function renderDocsArchitecture() {
    renderDocsCatalog();
    renderEndpointDocs();
    renderMermaid();
}

function renderMermaid() {
    if (!window.mermaid) return;
    try {
        if (!state.mermaidRendered) {
            window.mermaid.initialize({
                startOnLoad: false,
                securityLevel: 'loose',
                theme: 'default',
                flowchart: { curve: 'basis' },
            });
        }
        window.mermaid.run({ querySelector: '.mermaid' });
        state.mermaidRendered = true;
    } catch {
        // Mermaid rendering is optional; page docs still work without it.
    }
}

function formatDate(value) {
    if (!value) return '-';
    return new Date(value).toLocaleString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function mdToHtml(text) {
    if (!text) return '';
    const codeBlocks = [];
    const escaped = esc(text).replace(/```([\w-]*)\n([\s\S]*?)```/g, (_, language, code) => {
        const index = codeBlocks.length;
        const className = language ? ` language-${language}` : '';
        codeBlocks.push(`<pre class="code-block${className}"><code>${code.replace(/^\n/, '')}</code></pre>`);
        return `__CODE_BLOCK_${index}__`;
    });

    const blocks = escaped
        .split(/\n{2,}/)
        .map(block => block.trim())
        .filter(Boolean)
        .map(block => {
            if (/^__CODE_BLOCK_\d+__$/.test(block)) {
                return block;
            }

            if (/^(#{1,3})\s+/.test(block)) {
                return block
                    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
                    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
                    .replace(/^# (.+)$/gm, '<h1>$1</h1>');
            }

            const lines = block.split('\n').map(line => line.trim()).filter(Boolean);
            const isList = lines.every(line => /^([-*•]|\d+\.)\s+/.test(line));

            if (isList) {
                const items = lines.map(line => line
                    .replace(/^([-*•]|\d+\.)\s+/, '')
                    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>'))
                    .map(item => `<li>${item}</li>`)
                    .join('');
                return `<ul class="report-list">${items}</ul>`;
            }

            const content = lines
                .map(line => line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>'))
                .join(' ');
            return `<p>${content}</p>`;
        });

    let html = blocks.join('\n');
    codeBlocks.forEach((code, index) => {
        html = html.replace(`__CODE_BLOCK_${index}__`, code);
    });

    return html;
}

function normalizeReportPages(review) {
    if (review.report_pages && Object.keys(review.report_pages).length) {
        return review.report_pages;
    }

    const full = review.deep_analysis_report || review.report_text || '';
    return {
        executive: full,
        full_report: full,
    };
}

function reportPageLabel(key) {
    const labels = {
        executive: 'Executive',
        landscape: 'Landscape',
        architecture: 'Architecture',
        security: 'Security',
        performance: 'Performance',
        reliability: 'Reliability',
        quality: 'Quality',
        dependencies: 'Dependencies',
        findings: 'Findings Matrix',
        roadmap: 'Roadmap',
        pr_review: 'PR Review',
        full_report: 'Full Report',
        report_story: 'Report Story',
    };
    return labels[key] || key;
}

function defaultPageDocumentation(pageKey, pageContent, review) {
    const counts = review.issue_counts || {};
    return {
        title: `${reportPageLabel(pageKey)} Documentation`,
        what_is_happening: (pageContent || '').slice(0, 500) || 'This page summarizes current behavior and implementation state.',
        what_is_wrong: 'Potential defects and risks are listed in this page content and related findings.',
        why_it_matters: `Current risk mix: CRITICAL=${counts.critical || 0}, HIGH=${counts.high || 0}, MEDIUM=${counts.medium || 0}, LOW=${counts.low || 0}.`,
        recommended_actions: 'Use the roadmap and findings matrix to prioritize fixes and verification.',
        cross_links: 'Related pages: Executive, Architecture, Security, Findings, Roadmap.',
    };
}

function renderPageDocumentation(review, pageKey) {
    const pages = normalizeReportPages(review);
    const pageContent = pages[pageKey] || '';
    const docs = review.page_documentation || {};
    const doc = docs[pageKey] || defaultPageDocumentation(pageKey, pageContent, review);

    $('doc-title').textContent = doc.title || `${reportPageLabel(pageKey)} Documentation`;
    $('page-doc').innerHTML = `
        <div class="timeline-item"><strong>What is happening:</strong> ${esc(doc.what_is_happening || '-')}</div>
        <div class="timeline-item"><strong>What is wrong:</strong> ${esc(doc.what_is_wrong || '-')}</div>
        <div class="timeline-item"><strong>Why it matters:</strong> ${esc(doc.why_it_matters || '-')}</div>
        <div class="timeline-item"><strong>What to do now:</strong> ${esc(doc.recommended_actions || '-')}</div>
    `;

    $('page-links').innerHTML = `
        <div class="timeline-item">${esc(doc.cross_links || 'No cross-links available.')}</div>
    `;
}

function renderReportNavigation(review) {
    const nav = $('report-nav');
    const pages = normalizeReportPages(review);
    const keys = Object.keys(pages).filter(k => (pages[k] || '').trim().length > 0);

    nav.innerHTML = keys.length
        ? keys.map(key =>
            `<button type="button" class="report-chip ${state.activeReportPage === key ? 'active' : ''}" onclick="openReportPage('${key}')">${reportPageLabel(key)}</button>`
        ).join('')
        : '<span class="muted">Run analysis to generate report pages.</span>';
}

function updateReportHeader(review) {
    const pages = normalizeReportPages(review);
    const pageCount = Object.values(pages).filter(page => (page || '').trim().length > 0).length;
    const counts = review.issue_counts || {};

    $('report-page-count').textContent = `${pageCount} section${pageCount === 1 ? '' : 's'} ready`;
    $('report-file-count').textContent = `${review.files_indexed || 0} files indexed`;
    $('report-signal').textContent = `Critical ${counts.critical || 0}, High ${counts.high || 0}, Medium ${counts.medium || 0}, Low ${counts.low || 0}.`;
}

window.openReportPage = function openReportPage(key) {
    if (!state.currentReview) return;
    state.activeReportPage = key;
    const pages = normalizeReportPages(state.currentReview);
    const content = pages[key] || 'No content available for this page.';
    $('report-body').innerHTML = mdToHtml(content);
    renderPageDocumentation(state.currentReview, key);
    renderReportNavigation(state.currentReview);
};

function renderFindingsAndMetrics(review) {
    const counts = review.issue_counts || {};
    $('metric-critical').textContent = counts.critical || 0;
    $('metric-high').textContent = counts.high || 0;
    $('metric-medium').textContent = counts.medium || 0;
    $('metric-low').textContent = counts.low || 0;

    const findings = review.top_findings || [];
    $('top-findings').innerHTML = findings.length
        ? findings.map(f => `<div class="timeline-item">${esc(f)}</div>`).join('')
        : '<div class="timeline-item">No explicit findings list extracted.</div>';

    const snapshot = review.executive_summary || (normalizeReportPages(review).executive || '').slice(0, 1200);
    $('executive-snapshot').innerHTML = mdToHtml(snapshot);
}

function setPipeline(clone, index, review) {
    $('p-clone').style.width = `${clone}%`;
    $('p-index').style.width = `${index}%`;
    $('p-review').style.width = `${review}%`;
}

function renderRepoTable() {
    const table = $('repo-table');
    if (!state.repos.length) {
        table.innerHTML = '<tr><td>No repositories found.</td></tr>';
        return;
    }

    table.innerHTML = `
        <thead>
            <tr>
                <th>Repository</th>
                <th>Language</th>
                <th>Visibility</th>
                <th>Stars</th>
                <th>Updated Scope</th>
            </tr>
        </thead>
        <tbody>
            ${state.repos.map(r => `
                <tr>
                    <td>${esc(r.full_name)}</td>
                    <td>${esc(r.language || 'Unknown')}</td>
                    <td>${r.private ? 'Private' : 'Public'}</td>
                    <td>${r.stars || 0}</td>
                    <td>${esc(r.description || '-')}</td>
                </tr>
            `).join('')}
        </tbody>
    `;
}

function renderPrTable() {
    const table = $('pr-table');
    if (!state.prs.length) {
        table.innerHTML = '<tr><td>No open PRs.</td></tr>';
        return;
    }

    table.innerHTML = `
        <thead>
            <tr>
                <th>PR</th>
                <th>Author</th>
                <th>Changes</th>
                <th>Branches</th>
                <th>Updated</th>
            </tr>
        </thead>
        <tbody>
            ${state.prs.map(pr => `
                <tr>
                    <td>#${pr.number} - ${esc(pr.title)}</td>
                    <td>${esc(pr.author)}</td>
                    <td>+${pr.additions} / -${pr.deletions} (${pr.changed_files} files)</td>
                    <td>${esc(pr.head_branch)} -> ${esc(pr.base_branch)}</td>
                    <td>${formatDate(pr.updated_at)}</td>
                </tr>
            `).join('')}
        </tbody>
    `;
}

function renderHistoryTable() {
    const table = $('history-table');
    if (!state.history.length) {
        table.innerHTML = '<tr><td>No reviews stored yet.</td></tr>';
        return;
    }

    table.innerHTML = `
        <thead>
            <tr>
                <th>Date</th>
                <th>Repository</th>
                <th>PR</th>
                <th>Score</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            ${state.history.map(h => `
                <tr>
                    <td>${formatDate(h.analyzed_at)}</td>
                    <td>${esc(h.repo_name || '-')}</td>
                    <td>#${h.pr_number || '-'} ${esc(h.pr_title || '')}</td>
                    <td>${h.overall_score != null ? `${h.overall_score}/10` : '-'}</td>
                    <td><button class="btn btn-secondary" onclick="openHistory(${h.id})">Open</button></td>
                </tr>
            `).join('')}
        </tbody>
    `;
}

function renderLanguageMix() {
    const target = $('language-bars');
    if (!state.repos.length) {
        target.innerHTML = '<p class="muted">No language data available.</p>';
        return;
    }

    const counts = {};
    state.repos.forEach(r => {
        const lang = r.language || 'Unknown';
        counts[lang] = (counts[lang] || 0) + 1;
    });

    const total = state.repos.length;
    const bars = Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 6)
        .map(([lang, count]) => {
            const pct = Math.round((count / total) * 100);
            return `
                <div style="margin-bottom:10px;">
                    <div class="muted" style="display:flex; justify-content:space-between;"><span>${esc(lang)}</span><span>${pct}%</span></div>
                    <div class="progress"><span style="width:${pct}%"></span></div>
                </div>
            `;
        }).join('');

    target.innerHTML = bars;
}

function renderOverview() {
    $('kpi-repos').textContent = state.repos.length;
    $('kpi-prs').textContent = state.prs.length;
    $('kpi-reviews').textContent = state.history.length;

    $('pipeline-timeline').innerHTML = `
        <div class="timeline-item"><strong>1.</strong> Login session validated and GitHub profile loaded.</div>
        <div class="timeline-item"><strong>2.</strong> Repository catalog synchronized for current user.</div>
        <div class="timeline-item"><strong>3.</strong> PR metadata loaded for selected repository.</div>
        <div class="timeline-item"><strong>4.</strong> Analysis pipeline ready: clone, index, PR review, deep synthesis.</div>
    `;

    renderLanguageMix();
}

async function loadHealth() {
    try {
        const health = await api('/health');
        $('kpi-health').textContent = health.status === 'healthy' ? 'Healthy' : 'Degraded';
        $('kpi-health').className = `tag ${health.status === 'healthy' ? 'ok' : 'error'}`;
    } catch {
        $('kpi-health').textContent = 'Unknown';
        $('kpi-health').className = 'tag error';
    }
}

async function loadSession() {
    const status = await api('/auth/status');
    if (!status.authenticated) {
        window.location.href = '/login';
        return;
    }

    state.user = await api('/auth/me');
    $('user-name').innerHTML = `<strong>${esc(state.user.name || state.user.login)}</strong>`;
    $('user-login').textContent = `@${state.user.login}`;
    $('user-avatar').src = state.user.avatar_url || 'https://avatars.githubusercontent.com/u/0?v=4';
}

async function loadRepositories() {
    state.repos = await api('/repos');
    const select = $('repo-select');
    if (!state.repos.length) {
        select.innerHTML = '<option value="">No repositories available</option>';
        state.selectedRepo = null;
        state.prs = [];
        renderRepoTable();
        renderPrTable();
        return;
    }

    select.innerHTML = state.repos
        .map(r => `<option value="${esc(r.owner)}/${esc(r.name)}">${esc(r.full_name)}</option>`)
        .join('');

    const first = state.repos[0];
    state.selectedRepo = { owner: first.owner, name: first.name };
    renderRepoTable();
    await loadPullRequests();
}

async function loadPullRequests() {
    if (!state.selectedRepo) return;
    state.prs = await api(`/repos/${state.selectedRepo.owner}/${state.selectedRepo.name}/prs`);

    const prSelect = $('pr-select');
    if (!state.prs.length) {
        prSelect.innerHTML = '<option value="">No open pull requests</option>';
        state.selectedPr = null;
    } else {
        prSelect.innerHTML = state.prs
            .map(pr => `<option value="${pr.number}">#${pr.number} - ${esc(pr.title)}</option>`)
            .join('');
        state.selectedPr = state.prs[0];
    }

    renderPrTable();
    syncAnalysisSelection();
    renderEndpointDocs();
}

function syncAnalysisSelection() {
    const repo = state.selectedRepo ? `${state.selectedRepo.owner}/${state.selectedRepo.name}` : '-';
    const pr = state.selectedPr ? `#${state.selectedPr.number} - ${state.selectedPr.title}` : '-';
    $('analysis-repo').textContent = repo;
    $('analysis-pr').textContent = pr;
}

async function loadHistory() {
    const data = await api('/history?limit=40&skip=0');
    state.history = data.reviews || [];
    renderHistoryTable();
}

async function runAnalysis() {
    const error = $('analysis-error');
    error.classList.add('hidden');
    error.textContent = '';

    if (!state.selectedRepo || !state.selectedPr) {
        error.textContent = 'Select repository and pull request first.';
        error.classList.remove('hidden');
        return;
    }

    const button = $('run-review-btn');
    button.disabled = true;
    button.textContent = 'Running...';

    try {
        setPipeline(15, 0, 0);
        const promise = api(`/review/${state.selectedRepo.owner}/${state.selectedRepo.name}/${state.selectedPr.number}`, {
            method: 'POST',
        });

        await new Promise(r => setTimeout(r, 900));
        setPipeline(100, 35, 0);
        await new Promise(r => setTimeout(r, 1200));
        setPipeline(100, 100, 55);

        const review = await promise;
        state.currentReview = review;
        setPipeline(100, 100, 100);

        state.activeReportPage = 'executive';
        renderFindingsAndMetrics(review);
        updateReportHeader(review);
        renderReportNavigation(review);
        openReportPage('executive');
        $('comment-box').value = review.review;
        $('meta-repo').textContent = `Repo: ${review.owner}/${review.repo}`;
        $('meta-pr').textContent = `PR: #${review.pr_number} ${review.pr_title}`;
        $('meta-score').textContent = `Overall: ${review.overall_score || '-'} / 10`;
        $('meta-confidence').textContent = `Confidence: ${review.confidence_score || '-'} / 10`;

        await loadHistory();
        renderOverview();
        renderEndpointDocs();
        setActiveView('report');
        showToast('Deep analysis completed');
    } catch (e) {
        error.textContent = e.message;
        error.classList.remove('hidden');
        setPipeline(0, 0, 0);
        showToast('Analysis failed', 'error');
    } finally {
        button.disabled = false;
        button.textContent = 'Run Deep Analysis';
    }
}

async function postComment() {
    if (!state.currentReview) {
        showToast('Run analysis first', 'error');
        return;
    }

    const comment = $('comment-box').value.trim();
    if (!comment) {
        showToast('Comment is empty', 'error');
        return;
    }

    try {
        const res = await api(`/repos/${state.currentReview.owner}/${state.currentReview.repo}/prs/${state.currentReview.pr_number}/comment`, {
            method: 'POST',
            body: JSON.stringify({ comment }),
        });
        if (res.success) showToast('Comment posted to GitHub');
        else showToast('Failed to post comment', 'error');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

window.openHistory = async function openHistory(id) {
    try {
        const row = await api(`/history/review/${id}`);
        const split = '# Deep Repository Analysis';
        const content = row.report_text || '';
        const idx = content.indexOf(split);
        const prReview = idx > -1 ? content.slice(0, idx).trim() : content;
        const deepReport = idx > -1 ? content.slice(idx + split.length).trim() : content;


        // Update repo to make chat context ready
        state.selectedRepo = { owner: row.owner, name: row.repo };
        syncAnalysisSelection();

        state.currentReview = {
            owner: row.owner,
            repo: row.repo,
            pr_number: row.pr_number,
            pr_title: row.pr_title,
            review: prReview,
            deep_analysis_report: deepReport,
            report_pages: {
                executive: deepReport,
                pr_review: prReview,
                full_report: deepReport,
            },
            page_documentation: {
                executive: {
                    title: 'Executive Documentation',
                    what_is_happening: deepReport.slice(0, 500),
                    what_is_wrong: 'Historical data may not include full structured metadata for all sections.',
                    why_it_matters: 'This record is restored from stored review text and may require a fresh run for full multi-page docs.',
                    recommended_actions: 'Re-run deep analysis on latest PR to generate connected documentation pages.',
                    cross_links: 'Related pages: PR Review, Full Report',
                },
            },
            issue_counts: {
                critical: 0,
                high: 0,
                medium: 0,
                low: 0,
            },
            top_findings: [],
            executive_summary: deepReport,
            confidence_score: row.confidence_score,
            overall_score: row.overall_score,
            files_indexed: row.files_analyzed || 0,
        };

        state.activeReportPage = 'executive';
        renderFindingsAndMetrics(state.currentReview);
        updateReportHeader(state.currentReview);
        renderReportNavigation(state.currentReview);
        openReportPage('executive');
        $('meta-repo').textContent = `Repo: ${row.repo_name || '-'}`;
        $('meta-pr').textContent = `PR: #${row.pr_number || '-'} ${row.pr_title || ''}`;
        $('meta-score').textContent = `Overall: ${row.overall_score || '-'} / 10`;
        $('meta-confidence').textContent = `Confidence: ${row.confidence_score || '-'} / 10`;
        $('comment-box').value = prReview.slice(0, 4000);

        setActiveView('report');
        showToast('History record loaded');
    } catch (e) {
        showToast(e.message, 'error');
    }
};

function wireEvents() {
    document.querySelectorAll('#dashboard-nav button').forEach(btn => {
        btn.addEventListener('click', () => setActiveView(btn.dataset.view));
    });

    $('repo-select').addEventListener('change', async e => {
        const [owner, name] = e.target.value.split('/');
        state.selectedRepo = { owner, name };
        await loadPullRequests();
        renderOverview();
    });

    $('pr-select').addEventListener('change', e => {
        const number = Number(e.target.value);
        state.selectedPr = state.prs.find(pr => pr.number === number) || null;
        syncAnalysisSelection();
    });

    $('run-review-btn').addEventListener('click', runAnalysis);
    $('post-comment-btn').addEventListener('click', postComment);
    $('copy-report-btn').addEventListener('click', () => {
        if (!state.currentReview) {
            showToast('No report to copy', 'error');
            return;
        }
        const text = `# PR Review\n\n${state.currentReview.review}\n\n# Deep Repository Analysis\n\n${state.currentReview.deep_analysis_report}`;
        navigator.clipboard.writeText(text)
            .then(() => showToast('Report copied'))
            .catch(() => showToast('Copy failed', 'error'));
    });

    $('save-key-btn').addEventListener('click', async () => {
        const key = $('gemini-key-input').value.trim();
        if (!key) {
            showToast('Gemini key is empty', 'error');
            return;
        }
        try {
            await api('/auth/set-gemini-key', {
                method: 'POST',
                body: JSON.stringify({ gemini_key: key }),
            });
            showToast('Gemini key saved');
        } catch (e) {
            showToast(e.message, 'error');
        }
    });

    $('show-key-btn').addEventListener('click', () => {
        const input = $('gemini-key-input');
        input.type = input.type === 'password' ? 'text' : 'password';
    });

    $('logout-btn').addEventListener('click', () => {
        window.location.href = '/auth/logout';
    });

    $('refresh-all').addEventListener('click', async () => {
        await bootstrap();
        showToast('Data refreshed');
    });

    $('open-chat-btn').addEventListener('click', () => {
        $('chat-panel').classList.remove('hidden');
    });

    $('close-chat-btn').addEventListener('click', () => {
        $('chat-panel').classList.add('hidden');
    });

    $('send-chat-btn').addEventListener('click', sendChatMessage);
    $('chat-input').addEventListener('keypress', (e) => {
        if(e.key === 'Enter') sendChatMessage();
    });
}

async function sendChatMessage() {
    const input = $('chat-input');
    const msg = input.value.trim();
    if (!msg) return;

    if (!state.selectedRepo) {
        showToast('Select a repository and run analysis first.', 'error');
        return;
    }

    const history = $('chat-history');
    
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-msg user';
    userDiv.textContent = msg;
    history.appendChild(userDiv);

    input.value = '';
    
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chat-msg ai loading';
    loadingDiv.textContent = 'Thinking...';
    history.appendChild(loadingDiv);
    
    history.scrollTop = history.scrollHeight;

    try {
        const res = await api(`/chat/${state.selectedRepo.owner}/${state.selectedRepo.name}`, {
            method: 'POST',
            body: JSON.stringify({ query: msg }),
        });
        
        history.removeChild(loadingDiv);
        const aiDiv = document.createElement('div');
        aiDiv.className = 'chat-msg ai';
        aiDiv.innerHTML = mdToHtml(res.response);
        history.appendChild(aiDiv);
    } catch (e) {
        history.removeChild(loadingDiv);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'chat-msg error-msg';
        errorDiv.textContent = `Error: ${e.message}`;
        history.appendChild(errorDiv);
        showToast(`Chat error: ${e.message}`, 'error');
    }
    
    history.scrollTop = history.scrollHeight;
}

async function bootstrap() {
    await loadSession();
    await loadRepositories();
    await loadHistory();
    await loadHealth();
    renderOverview();
    syncAnalysisSelection();
    renderDocsArchitecture();
}

wireEvents();
bootstrap().catch(e => {
    showToast(e.message, 'error');
});
