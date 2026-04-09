'use strict';

const loginBtn = document.getElementById('login-btn');
const errorBox = document.getElementById('login-error');

function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.remove('hidden');
}

async function api(path) {
    const res = await fetch(path, { credentials: 'include' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
}

async function bootstrap() {
    try {
        const status = await api('/auth/status');
        if (status.authenticated) {
            window.location.href = '/dashboard';
            return;
        }
    } catch {
        // Ignore and keep login page visible.
    }

    const params = new URLSearchParams(window.location.search);
    if (params.get('auth_error')) {
        showError('GitHub login failed. Please try again.');
    }
}

loginBtn.addEventListener('click', () => {
    window.location.href = '/auth/github';
});

bootstrap();
