// ==================== Token 工具 ====================

const t = window.translateAppText || ((text) => text);

// ===== 新手指引配置 =====
// 教程链接列表 — 在此维护外部教程链接，HTML 中 guide-links 区域会自动渲染
const GUIDE_TUTORIAL_LINKS = [
    // { title: '标题', url: 'https://example.com/tutorial' },
    // 在此添加教程链接...
];

const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]')?.content || '';
// 方式二：免注册 Azure —— 默认使用 Mozilla Thunderbird 公开 Client ID。
// Thunderbird 应用在 Azure 已登记 https://localhost 为回调地址，因此可直接授权。
const THUNDERBIRD_CLIENT_ID = '9e5f94bc-e8a4-4e73-b8be-63364c29d753';
const DEFAULT_REDIRECT_URI = 'https://localhost';
const SCOPE_PRESETS = {
    graph: ['offline_access', 'Mail.ReadWrite'],
    imap: ['offline_access', 'https://outlook.office.com/IMAP.AccessAsUser.All'],
};
const DEFAULT_COMPAT_SCOPE = SCOPE_PRESETS.graph.join(' ');

let scopeTokens = ['offline_access', 'Mail.ReadWrite'];
let currentTokenResult = null;

async function tokenToolFetch(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF_TOKEN,
        ...(options.headers || {}),
    };
    const response = await fetch(url, { ...options, headers });
    const data = await response.json().catch(() => ({
        success: false,
        error: { message: t('响应解析失败') },
    }));
    if (!response.ok && data.success === undefined) {
        data.success = false;
    }
    return data;
}

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function buildDefaultRedirectUri() {
    // 方式二固定使用 Thunderbird 已登记的回调地址，授权后从地址栏复制完整 URL 粘回即可
    return DEFAULT_REDIRECT_URI;
}

function showStatus(message, type = 'info', detail = '') {
    const statusNode = document.getElementById('statusMessage');
    if (!statusNode) {
        return;
    }
    statusNode.className = `token-status ${type}`;
    statusNode.innerHTML = `
        <div class="token-status-title">${escapeHtml(message)}</div>
        ${detail ? `<div class="token-status-detail">${escapeHtml(detail)}</div>` : ''}
    `;
}

function clearStatus() {
    const statusNode = document.getElementById('statusMessage');
    if (!statusNode) {
        return;
    }
    statusNode.className = 'token-status hidden';
    statusNode.innerHTML = '';
}

function showSaveDialogStatus(message, type = 'info', detail = '') {
    const statusNode = document.getElementById('saveDialogStatus');
    if (!statusNode) {
        showStatus(message, type, detail);
        return;
    }
    statusNode.className = `token-status token-dialog-status ${type}`;
    statusNode.innerHTML = `
        <div class="token-status-title">${escapeHtml(message)}</div>
        ${detail ? `<div class="token-status-detail">${escapeHtml(detail)}</div>` : ''}
    `;
}

function clearSaveDialogStatus() {
    const statusNode = document.getElementById('saveDialogStatus');
    if (!statusNode) {
        return;
    }
    statusNode.className = 'token-status token-dialog-status hidden';
    statusNode.innerHTML = '';
}

function parseScopeInput(raw) {
    return String(raw || '')
        .split(/[\s,;]+/)
        .map(item => item.trim())
        .filter(Boolean);
}

function updateScopeValue() {
    const scopeValue = document.getElementById('scopeValue');
    if (scopeValue) {
        scopeValue.value = scopeTokens.join(' ');
    }
    renderScopeSummary();
}

function renderScopeSummary() {
    const summaryNode = document.getElementById('scopeReadonlyText');
    if (summaryNode) {
        summaryNode.textContent = scopeTokens.join(' ') || DEFAULT_COMPAT_SCOPE;
    }
}

function switchAuthMethod(method) {
    const normalized = method === 'oneclick' ? 'oneclick' : 'manual';
    document.querySelectorAll('.auth-tab').forEach((tab) => {
        tab.classList.toggle('active', tab.dataset.method === normalized);
    });
    const paneOne = document.getElementById('authPane-oneclick');
    const paneManual = document.getElementById('authPane-manual');
    if (paneOne) paneOne.hidden = normalized !== 'oneclick';
    if (paneManual) paneManual.hidden = normalized !== 'manual';
    updateOneClickButtonState();
}

function initAuthMethodTabs() {
    // 默认：Thunderbird 默认 ID（回调 https://localhost）→ 方式二手动授权；
    // 自建应用（回调指向本服务）→ 方式一一键授权。
    const redirectUri = (document.getElementById('redirectUri')?.value || '').trim();
    const defaultMethod = (redirectUri && redirectUri !== DEFAULT_REDIRECT_URI) ? 'oneclick' : 'manual';
    switchAuthMethod(defaultMethod);
}

function setStepActive(step) {
    document.querySelectorAll('#tokenSteps .step').forEach((item) => {
        const active = String(item.dataset.step) === String(step);
        item.classList.toggle('active', active);
        if (active) {
            item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    });
}

function buildScopeChip(token) {
    const locked = token === 'offline_access';
    const chip = document.createElement('span');
    chip.className = locked ? 'scope-chip scope-chip-locked' : 'scope-chip';

    const label = document.createElement('span');
    label.textContent = token;
    chip.appendChild(label);

    if (locked) {
        const lock = document.createElement('span');
        lock.className = 'scope-chip-lock';
        lock.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="emoji-svg"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>';
        chip.appendChild(lock);
        return chip;
    }

    const removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.dataset.scope = token;
    removeButton.setAttribute('aria-label', t('移除 scope') + ' ' + token);
    removeButton.textContent = '×';
    chip.appendChild(removeButton);
    return chip;
}

function renderScopeChips(scopeValue) {
    const tokens = parseScopeInput(scopeValue);
    const unique = new Set(tokens);
    unique.add('offline_access');
    scopeTokens = Array.from(unique);
    updateScopeValue();

    const chipsNode = document.getElementById('scopeChips');
    if (!chipsNode) {
        return;
    }
    chipsNode.innerHTML = '';
    scopeTokens.forEach(token => {
        chipsNode.appendChild(buildScopeChip(token));
    });
}

function addScopeTokens(tokens) {
    if (!Array.isArray(tokens) || tokens.length === 0) {
        return;
    }
    renderScopeChips([...scopeTokens, ...tokens].join(' '));
}

function addScopeFromInput() {
    const scopeEntry = document.getElementById('scopeEntry');
    if (!scopeEntry) {
        return;
    }
    const tokens = parseScopeInput(scopeEntry.value);
    if (!tokens.length) {
        showStatus(t('请输入要添加的 scope'), 'error');
        return;
    }
    addScopeTokens(tokens);
    scopeEntry.value = '';
    clearStatus();
}

function removeScope(scope) {
    if (scope === 'offline_access') {
        return;
    }
    scopeTokens = scopeTokens.filter(item => item !== scope);
    renderScopeChips(scopeTokens.join(' '));
}

function handleScopeChipClick(event) {
    if (!(event.target instanceof Element)) {
        return;
    }
    const removeButton = event.target.closest('button[data-scope]');
    if (!removeButton) {
        return;
    }
    removeScope(removeButton.dataset.scope || '');
}

function setScopePreset(type) {
    const preset = SCOPE_PRESETS[type];
    if (!preset) {
        return;
    }
    renderScopeChips(preset.join(' '));
    clearStatus();
}

function handleTenantChange() {
    // No-op: tenant is hardcoded to 'common' on the backend (方式二 Thunderbird 多租户).
}

function collectFormConfig() {
    return {
        client_id: document.getElementById('clientId')?.value.trim() || '',
        client_secret: '',
        redirect_uri: document.getElementById('redirectUri')?.value.trim() || '',
        scope: document.getElementById('scopeValue')?.value.trim() || '',
        tenant: 'common',
        prompt_consent: Boolean(document.getElementById('promptConsent')?.checked),
    };
}

async function loadOAuthConfig() {
    const data = await tokenToolFetch('/api/token-tool/config');
    if (!data.success) {
        showStatus(data.error?.message || t('加载配置失败'), 'error');
        return;
    }

    const config = data.data || {};
    document.getElementById('clientId').value = config.client_id || '';
    document.getElementById('redirectUri').value = config.redirect_uri || buildDefaultRedirectUri();

    handleTenantChange();
    renderScopeChips(config.scope || DEFAULT_COMPAT_SCOPE);
    clearStatus();
    updateOneClickButtonState();
    initAuthMethodTabs();
}

async function startOAuth() {
    clearStatus();
    const config = collectFormConfig();
    const data = await tokenToolFetch('/api/token-tool/prepare', {
        method: 'POST',
        body: JSON.stringify(config),
    });
    if (!data.success) {
        showStatus(data.error?.message || t('生成授权 URL 失败'), 'error');
        return;
    }

    const authorizeUrl = data.data?.authorize_url;
    if (!authorizeUrl) {
        showStatus(t('授权地址为空'), 'error');
        return;
    }

    // Display the authorize link in the panel
    const linkInput = document.getElementById('authorizeUrl');
    if (linkInput) {
        linkInput.value = authorizeUrl;
    }
    const panel = document.getElementById('authorize-link-panel');
    if (panel) {
        panel.classList.remove('hidden');
        panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    document.getElementById('manual-exchange').open = true;
    switchAuthMethod('manual');
    setStepActive(2);
    showStatus(t('授权链接已生成，请复制并在浏览器中打开'), 'success');
}

// ===== 方式一：一键授权（弹窗自动回传）=====
let oneClickPopup = null;
let oneClickMessageBound = false;

function isOneClickAvailable() {
    // 一键授权要求回调地址指向当前服务器（自建 Azure 应用）；
    // 默认 Thunderbird ID 的 https://localhost 无法回传，仅支持手动方式。
    const redirectUri = (document.getElementById('redirectUri')?.value || '').trim();
    return redirectUri && redirectUri !== DEFAULT_REDIRECT_URI;
}

function updateOneClickButtonState() {
    const btn = document.getElementById('oneClickOAuthBtn');
    if (!btn) return;
    const available = isOneClickAvailable();
    btn.disabled = !available;
    const hint = document.getElementById('oneClickHint');
    if (hint) {
        hint.style.display = available ? 'none' : '';
    }
}

async function performExchange(callbackUrl) {
    clearStatus();
    const data = await tokenToolFetch('/api/token-tool/exchange', {
        method: 'POST',
        body: JSON.stringify({ callback_url: callbackUrl }),
    });
    if (!data.success) {
        showStatus(data.error?.message || t('换取 Token 失败'), 'error', data.error?.details || '');
        return false;
    }
    renderTokenResult(data.data || {});
    return true;
}

async function handleOAuthCallbackMessage(event) {
    // 只接受来自本服务（token 工具所在 origin）的回传消息，防止伪造凭证注入
    if (event.origin !== window.location.origin) {
        return;
    }
    const payload = event.data;
    if (!payload || payload.type !== 'oauth-callback') {
        return;
    }

    if (!payload.success) {
        showStatus(
            payload.error_code ? `${payload.error_code}: ${payload.error_description || ''}` : t('授权失败'),
            'error'
        );
        return;
    }

    if (!payload.callback_url) {
        showStatus(t('回调地址为空'), 'error');
        return;
    }

    showStatus(t('授权成功，正在换取 Token…'), 'info');
    await performExchange(payload.callback_url);
}

function bindOneClickMessageListener() {
    if (oneClickMessageBound) return;
    window.addEventListener('message', handleOAuthCallbackMessage);
    oneClickMessageBound = true;
}

async function startOneClickOAuth() {
    clearStatus();
    const config = collectFormConfig();
    const data = await tokenToolFetch('/api/token-tool/prepare', {
        method: 'POST',
        body: JSON.stringify(config),
    });
    if (!data.success) {
        showStatus(data.error?.message || t('生成授权 URL 失败'), 'error');
        return;
    }

    const authorizeUrl = data.data?.authorize_url;
    if (!authorizeUrl) {
        showStatus(t('授权地址为空'), 'error');
        return;
    }

    bindOneClickMessageListener();
    oneClickPopup = window.open(authorizeUrl, 'oauth-popup', 'width=520,height=680,scrollbars=yes');
    if (!oneClickPopup) {
        showStatus(t('弹窗被浏览器拦截，请允许弹出窗口后重试，或改用下方手动授权'), 'error');
        return;
    }
    setStepActive(2);
    showStatus(t('已在弹窗中打开授权页，登录并同意后会自动回传'), 'info');
}

function copyAuthorizeLink() {
    const linkInput = document.getElementById('authorizeUrl');
    if (!linkInput || !linkInput.value) {
        showStatus(t('没有可复制的授权链接'), 'error');
        return;
    }
    copyText(linkInput.value);
}

function openAuthorizeLink() {
    const linkInput = document.getElementById('authorizeUrl');
    if (!linkInput || !linkInput.value) {
        showStatus(t('没有可打开的授权链接'), 'error');
        return;
    }
    window.open(linkInput.value, '_blank');
}

function fillResultField(id, value) {
    const node = document.getElementById(id);
    if (node) {
        node.value = value || '';
    }
}

function renderTokenResult(result) {
    currentTokenResult = result || {};
    document.getElementById('result-panel').classList.remove('hidden');
    document.getElementById('resultSuccessBanner').classList.remove('hidden');

    fillResultField('refreshTokenResult', result.refresh_token || '');
    fillResultField('accessTokenResult', result.access_token || '');
    fillResultField('clientIdResult', result.client_id || '');
    fillResultField('redirectUriResult', result.redirect_uri || '');
    fillResultField('requestedScopeResult', result.requested_scope || '');
    fillResultField('grantedScopeResult', result.granted_scope || '');
    fillResultField('audienceResult', result.audience || '');
    fillResultField('scopeClaimResult', result.scope_claim || '');
    fillResultField('rolesClaimResult', result.roles_claim || '');
    fillResultField('expiresInResult', String(result.expires_in || ''));

    document.getElementById('result-panel').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    setStepActive(3);
    showStatus(t('Token 已成功换取，可以复制或写入账号'), 'success');
}

function getCurrentTokenResult() {
    return currentTokenResult || {};
}

async function exchangeToken() {
    const callbackUrl = document.getElementById('callbackUrl')?.value.trim() || '';
    if (!callbackUrl) {
        showStatus(t('请粘贴回调 URL'), 'error');
        return;
    }
    await performExchange(callbackUrl);
}

async function saveConfig() {
    clearStatus();
    const config = collectFormConfig();
    const data = await tokenToolFetch('/api/token-tool/config', {
        method: 'POST',
        body: JSON.stringify(config),
    });
    if (!data.success) {
        showStatus(data.error?.message || t('保存配置失败'), 'error');
        return;
    }
    showStatus(data.message || t('配置已保存'), 'success');
}

function copyResultField(id) {
    const node = document.getElementById(id);
    if (!node) {
        return;
    }
    copyText(node.value || '');
}

function copyAllResults() {
    const result = getCurrentTokenResult();
    const lines = [
        `refresh_token=${result.refresh_token || ''}`,
        `access_token=${result.access_token || ''}`,
        `client_id=${result.client_id || ''}`,
        `redirect_uri=${result.redirect_uri || ''}`,
        `requested_scope=${result.requested_scope || ''}`,
        `granted_scope=${result.granted_scope || ''}`,
        `audience=${result.audience || ''}`,
        `scope_claim=${result.scope_claim || ''}`,
        `roles_claim=${result.roles_claim || ''}`,
        `expires_in=${result.expires_in || ''}`,
    ];
    copyText(lines.join('\n'));
}

function copyText(text) {
    navigator.clipboard.writeText(text || '').then(() => {
        showStatus(t('内容已复制到剪贴板'), 'success');
    }).catch(() => {
        showStatus(t('复制失败，请手动复制'), 'error');
    });
}

function toggleSaveMode() {
    const selected = document.querySelector('input[name="saveMode"]:checked')?.value || 'update';
    document.getElementById('updateModeSection')?.classList.toggle('hidden', selected !== 'update');
    document.getElementById('createModeSection')?.classList.toggle('hidden', selected !== 'create');
    clearSaveDialogStatus();
}

async function loadAccountOptions() {
    const data = await tokenToolFetch('/api/token-tool/accounts');
    const select = document.getElementById('accountSelect');
    if (!select) {
        return;
    }
    if (!data.success) {
        select.innerHTML = `<option value="">${t('加载账号失败')}</option>`;
        showSaveDialogStatus(data.error?.message || t('加载账号失败'), 'error');
        return;
    }

    const accounts = data.data || [];
    if (!accounts.length) {
        select.innerHTML = `<option value="">${t('暂无可更新账号')}</option>`;
        showSaveDialogStatus(t('当前没有可更新账号，可切换到“创建新账号”模式'), 'info');
        return;
    }
    clearSaveDialogStatus();
    select.innerHTML = accounts.map(account => `
        <option value="${escapeHtml(String(account.id))}">
            ${escapeHtml(account.email)} (${escapeHtml(account.status || 'active')})
        </option>
    `).join('');
}

async function openSaveDialog() {
    if (!getCurrentTokenResult().refresh_token) {
        showStatus(t('请先成功换取 Token'), 'error');
        return;
    }
    clearSaveDialogStatus();
    toggleSaveMode();
    setStepActive(4);
    await loadAccountOptions();
    document.getElementById('save-dialog')?.showModal();
}

function closeSaveDialog() {
    clearSaveDialogStatus();
    document.getElementById('save-dialog')?.close();
}

async function confirmSaveToAccount() {
    clearStatus();
    clearSaveDialogStatus();
    const mode = document.querySelector('input[name="saveMode"]:checked')?.value || 'update';
    const resultData = getCurrentTokenResult();
    const payload = {
        mode,
        refresh_token: resultData.refresh_token,
        client_id: resultData.client_id,
        scope: resultData.requested_scope || resultData.granted_scope || '',
    };

    if (mode === 'update') {
        payload.account_id = document.getElementById('accountSelect')?.value || '';
        if (!payload.account_id) {
            showSaveDialogStatus(t('请选择要更新的账号'), 'error');
            return;
        }
    } else {
        payload.email = document.getElementById('newAccountEmail')?.value.trim() || '';
        if (!payload.email) {
            showSaveDialogStatus(t('请输入新账号邮箱地址'), 'error');
            return;
        }
    }

    const data = await tokenToolFetch('/api/token-tool/save', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
    if (!data.success) {
        showSaveDialogStatus(data.error?.message || t('写入失败'), 'error', data.error?.details || '');
        return;
    }

    closeSaveDialog();
    showStatus(t('Token 已写入账号'), 'success');
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('scopeChips')?.addEventListener('click', handleScopeChipClick);
    document.getElementById('redirectUri').value = buildDefaultRedirectUri();
    const clientIdInput = document.getElementById('clientId');
    if (clientIdInput && !clientIdInput.value.trim()) {
        // 默认 Thunderbird ID（免注册）；如需自建 Azure 应用可自行替换
        clientIdInput.value = THUNDERBIRD_CLIENT_ID;
    }
    const cbSample = document.getElementById('callbackUriSample');
    if (cbSample) {
        cbSample.textContent = `${window.location.origin}/token-tool/callback`;
    }
    const cbSample2 = document.getElementById('callbackUriSample2');
    if (cbSample2) {
        cbSample2.textContent = `${window.location.origin}/token-tool/callback`;
    }
    renderScopeChips(SCOPE_PRESETS.graph.join(' '));
    renderScopeSummary();
    setStepActive(1);
    loadOAuthConfig();
    toggleSaveMode();
    handleTenantChange();
    bindOneClickMessageListener();
    document.getElementById('oneClickOAuthBtn')?.addEventListener('click', startOneClickOAuth);
    document.getElementById('redirectUri')?.addEventListener('input', () => {
        updateOneClickButtonState();
        initAuthMethodTabs();
    });
    document.getElementById('clientId')?.addEventListener('input', () => {
        updateOneClickButtonState();
        initAuthMethodTabs();
    });
    initAuthMethodTabs();

    // 指引折叠状态记忆
    const guideCard = document.getElementById('guide-card');
    if (guideCard) {
        const guideDismissed = localStorage.getItem('token_tool_guide_dismissed');
        if (guideDismissed === 'true') {
            guideCard.removeAttribute('open');
        }
        guideCard.addEventListener('toggle', () => {
            localStorage.setItem('token_tool_guide_dismissed', guideCard.open ? '' : 'true');
        });
    }

    // 自动渲染教程链接到 guide-links 区域
    const guideLinksContainer = document.querySelector('.guide-links');
    if (guideLinksContainer && GUIDE_TUTORIAL_LINKS.length > 0) {
        GUIDE_TUTORIAL_LINKS.forEach((link) => {
            const a = document.createElement('a');
            a.href = link.url;
            a.target = '_blank';
            a.rel = 'noopener';
            a.textContent = link.title;
            guideLinksContainer.appendChild(a);
        });
    }
});
