const API_BASE = "http://localhost:8000";

const state = {
    ghToken: localStorage.getItem('ghToken') || '',
    geminiKey: localStorage.getItem('geminiKey') || '',
    repos: [],
    currentRepo: null,
    prs: [],
    currentPR: null
};

// DOM Elements
const authSection = document.getElementById('auth-section');
const dashboardSection = document.getElementById('dashboard-section');
const ghTokenInput = document.getElementById('gh-token');
const geminiKeyInput = document.getElementById('gemini-key');
const loginBtn = document.getElementById('login-btn');
const repoList = document.getElementById('repo-list');
const repoLoader = document.getElementById('repo-loader');
const prListView = document.getElementById('pr-list-view');
const prListItems = document.getElementById('pr-list-items');
const emptyState = document.getElementById('empty-state');
const reviewView = document.getElementById('review-view');
const currentRepoName = document.getElementById('current-repo-name');
const prTitle = document.getElementById('pr-title');
const prNumber = document.getElementById('pr-number');
const prAuthor = document.getElementById('pr-author');
const startReviewBtn = document.getElementById('start-review-btn');
const reviewResultContainer = document.getElementById('review-result-container');
const reviewContent = document.getElementById('review-content');
const reviewLoader = document.getElementById('review-loader');
const postCommentBtn = document.getElementById('post-comment-btn');

// Initialization
if (state.ghToken && state.geminiKey) {
    showDashboard();
}

loginBtn.addEventListener('click', () => {
    state.ghToken = ghTokenInput.value.trim();
    state.geminiKey = geminiKeyInput.value.trim();
    
    if (!state.ghToken || !state.geminiKey) {
        alert("Please provide both GitHub Token and Gemini Key");
        return;
    }

    localStorage.setItem('ghToken', state.ghToken);
    localStorage.setItem('geminiKey', state.geminiKey);
    showDashboard();
});

async function showDashboard() {
    authSection.classList.add('hidden');
    dashboardSection.classList.remove('hidden');
    await fetchRepos();
}

async function apiFetch(endpoint, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json',
        'X-GitHub-Token': state.ghToken,
        'X-Google-API-Key': state.geminiKey
    };

    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(`${API_BASE}${endpoint}`, options);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'API request failed');
    }
    return response.json();
}

async function fetchRepos() {
    repoLoader.classList.remove('hidden');
    repoList.innerHTML = '';
    try {
        const repos = await apiFetch('/repos');
        state.repos = repos;
        repoList.innerHTML = repos.map(repo => `
            <div class="list-item" onclick="selectRepo('${repo.owner}', '${repo.name}')">
                <div class="list-title">${repo.name}</div>
                <div class="list-subtitle">${repo.owner}</div>
            </div>
        `).join('');
    } catch (err) {
        alert("Error fetching repos: " + err.message);
    } finally {
        repoLoader.classList.add('hidden');
    }
}

window.selectRepo = async (owner, name) => {
    state.currentRepo = { owner, name };
    currentRepoName.innerText = `${owner} / ${name}`;
    
    emptyState.classList.add('hidden');
    reviewView.classList.add('hidden');
    prListView.classList.remove('hidden');
    
    prListItems.innerHTML = '<div style="text-align:center"><span class="loader"></span></div>';
    
    try {
        const prs = await apiFetch(`/repos/${owner}/${name}/prs`);
        state.prs = prs;
        prListItems.innerHTML = prs.length ? prs.map(pr => `
            <div class="list-item" onclick="selectPR(${pr.number})">
                <div class="list-title">${pr.title}</div>
                <div class="list-subtitle">#${pr.number} by ${pr.author}</div>
            </div>
        `).join('') : '<p style="text-align:center; padding: 2rem;">No open Pull Requests found.</p>';
    } catch (err) {
        alert("Error fetching PRs: " + err.message);
    }
};

window.selectPR = (number) => {
    const pr = state.prs.find(p => p.number === number);
    state.currentPR = pr;
    
    prTitle.innerText = pr.title;
    prNumber.innerText = `#${pr.number}`;
    prAuthor.innerText = pr.author;
    
    prListView.classList.add('hidden');
    reviewView.classList.remove('hidden');
    reviewResultContainer.classList.add('hidden');
    reviewContent.innerText = '';
};

startReviewBtn.addEventListener('click', async () => {
    reviewLoader.classList.remove('hidden');
    startReviewBtn.disabled = true;
    reviewResultContainer.classList.add('hidden');
    
    try {
        const result = await apiFetch(`/review/${state.currentRepo.owner}/${state.currentRepo.name}/${state.currentPR.number}`, 'POST');
        reviewContent.innerText = result.review;
        reviewResultContainer.classList.remove('hidden');
    } catch (err) {
        alert("Review failed: " + err.message);
    } finally {
        reviewLoader.classList.add('hidden');
        startReviewBtn.disabled = false;
    }
});

postCommentBtn.addEventListener('click', async () => {
    if (!confirm("Do you want to post this review as a comment on GitHub?")) return;
    
    try {
        await apiFetch(`/repos/${state.currentRepo.owner}/${state.currentRepo.name}/prs/${state.currentPR.number}/comment`, 'POST', {
            comment: reviewContent.innerText
        });
        alert("Comment posted successfully!");
    } catch (err) {
        alert("Failed to post comment: " + err.message);
    }
});

document.getElementById('back-to-repos').addEventListener('click', () => {
    prListView.classList.add('hidden');
    emptyState.classList.remove('hidden');
});

document.getElementById('back-to-prs').addEventListener('click', () => {
    reviewView.classList.add('hidden');
    prListView.classList.remove('hidden');
});
