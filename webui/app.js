/* Giao diện công cụ Cào & Dịch Video.
 *
 * Ba tác vụ nặng dùng task_key cố định ("download" | "translate" | "merge") nên
 * mở lại trang là nối lại đúng luồng log đang chạy, không cần nhớ mã tác vụ.
 */
const TASKS = { download: 'download', translate: 'translate', merge: 'merge' };

const state = {
    config: {},
    library: [],
    selected: new Set(),   // entry_id đang chọn ở tab Thư Viện
    mergeList: [],         // [{entry_id, kind, name, label}]
    probe: [],
    roi: null,             // {x, y, w, h} theo pixel THẬT của video
    prepared: null,
    streams: {},           // task_key -> EventSource
    subCtx: null,          // {entryId, name} của phụ đề đang mở
};

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function toast(message, type = 'info') {
    let box = $('toastBox');
    if (!box) {
        box = document.createElement('div');
        box.id = 'toastBox';
        box.style.cssText = 'position:fixed;right:18px;bottom:18px;z-index:9999;display:flex;'
            + 'flex-direction:column;gap:8px;max-width:420px;';
        document.body.appendChild(box);
    }
    const item = document.createElement('div');
    const colors = { info: '#2563eb', success: '#059669', error: '#dc2626', warn: '#d97706' };
    item.style.cssText = `background:${colors[type] || colors.info};color:#fff;padding:11px 14px;`
        + 'border-radius:10px;font-size:13px;box-shadow:0 8px 24px rgba(0,0,0,.35);white-space:pre-wrap;';
    item.textContent = message;
    box.appendChild(item);
    setTimeout(() => item.remove(), type === 'error' ? 9000 : 4500);
}

async function api(path, options = {}) {
    const res = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = text; }
    if (!res.ok) {
        const detail = (data && data.detail) || text || `HTTP ${res.status}`;
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
}

function fmtDuration(sec) {
    sec = Math.round(Number(sec) || 0);
    if (!sec) return '—';
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    return (h ? `${h}:${String(m).padStart(2, '0')}` : `${m}`) + `:${String(s).padStart(2, '0')}`;
}

/* ------------------------------------------------------------------ Tabs */
function initTabs() {
    document.querySelectorAll('.nav-item').forEach((btn) => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.nav-item').forEach((b) => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
            btn.classList.add('active');
            const panel = $(`tab-${btn.dataset.tab}`);
            if (panel) panel.classList.add('active');
            if (btn.dataset.tab === 'library') loadLibrary();
            if (btn.dataset.tab === 'merge') loadMerged();
            if (btn.dataset.tab === 'settings') loadStats();
        });
    });
}

function goTab(name) {
    const btn = document.querySelector(`.nav-item[data-tab="${name}"]`);
    if (btn) btn.click();
}

/* ------------------------------------------------------- Cấu hình & form */
function getByPath(obj, path) {
    return path.split('.').reduce((acc, key) => (acc == null ? undefined : acc[key]), obj);
}

function setByPath(obj, path, value) {
    const keys = path.split('.');
    let cur = obj;
    keys.slice(0, -1).forEach((k) => {
        if (typeof cur[k] !== 'object' || cur[k] === null) cur[k] = {};
        cur = cur[k];
    });
    cur[keys[keys.length - 1]] = value;
}

function readField(el) {
    if (el.type === 'checkbox') return el.checked;
    if (el.type === 'number') return el.value === '' ? null : Number(el.value);
    return el.value;
}

function writeField(el, value) {
    if (value === undefined || value === null) return;
    if (el.type === 'checkbox') el.checked = Boolean(value);
    else el.value = value;
}

async function loadConfig() {
    state.config = await api('/api/config');
    document.querySelectorAll('[data-cfg]').forEach((el) => {
        writeField(el, getByPath(state.config, el.dataset.cfg));
    });
    state.wantedOllamaModel = getByPath(state.config, 'translate.ollama_model') || '';
}

async function loadUiSettings() {
    const saved = await api('/api/ui-settings');
    // ui_settings ghi đè cấu hình chung: đây là thứ người dùng vừa chỉnh trên form.
    Object.entries(saved || {}).forEach(([id, value]) => writeField($(id) || {}, value));
    if (saved && saved.trOllamaModel) state.wantedOllamaModel = saved.trOllamaModel;
    refreshTranslateVisibility();
}

async function saveAllSettings() {
    const cfg = JSON.parse(JSON.stringify(state.config || {}));
    document.querySelectorAll('[data-cfg]').forEach((el) => {
        const value = readField(el);
        if (value !== null) setByPath(cfg, el.dataset.cfg, value);
    });
    const ui = {};
    document.querySelectorAll('[data-persist]').forEach((el) => {
        if (el.id) ui[el.id] = readField(el);
    });
    await api('/api/config', { method: 'POST', body: JSON.stringify(cfg) });
    await api('/api/ui-settings', { method: 'POST', body: JSON.stringify(ui) });
    state.config = cfg;
    toast('Đã lưu cấu hình.', 'success');
}

/* --------------------------------------------------------------- Log SSE */
function appendLog(consoleId, text, cls = '') {
    const box = $(consoleId);
    if (!box) return;
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
    const line = document.createElement('span');
    if (cls) line.className = cls;
    line.textContent = text;
    box.appendChild(line);
    box.appendChild(document.createElement('br'));
    while (box.childNodes.length > 4000) box.removeChild(box.firstChild);
    if (atBottom) box.scrollTop = box.scrollHeight;
}

// Dịch JSON event của adapter sang câu tiếng Việt; trả null nếu không nhận ra.
function describeEvent(e) {
    const pct = (v) => (v || v === 0 ? ` ${Number(v).toFixed(0)}%` : '');
    switch (e.event) {
        case 'batch_start': return ['log-system', `[HỆ THỐNG] Bắt đầu tải ${e.total} video → ${e.output_dir}`];
        case 'item_start': return ['log-system', `[${e.index}/${e.total}] Đang tải: ${e.title}`];
        case 'item_done': return ['log-success', `[${e.index}/${e.total}] Xong: ${e.title} (${fmtDuration(e.duration)})`];
        case 'item_skipped': return ['log-warn', `[${e.index}/${e.total}] Bỏ qua: ${e.title} — ${e.reason}`];
        case 'item_failed': return ['log-error', `[LỖI] ${e.title || e.url}: ${e.error}`];
        case 'batch_done': return ['log-success',
            `[XONG] Tải: ${e.ok} thành công, ${e.skipped} bỏ qua, ${e.failed} lỗi.`];
        case 'batch_failed': return ['log-error', `[LỖI] ${e.error}`];
        case 'download_start': return ['log-system', `Đang tải: ${e.url}`];
        case 'download_progress': return ['', `  ...${pct(e.percent)} ${e.speed || ''} ${e.eta ? 'còn ' + e.eta + 's' : ''}`];
        case 'download_done': return ['log-success', `Đã tải xong: ${e.path}`];
        case 'download_info': return ['log-system', `[INFO] ${e.message}`];
        case 'download_warning': return ['log-warn', `[CẢNH BÁO] ${e.message}`];
        case 'download_error': return ['log-error', `[LỖI] ${e.error || e.message}`];
        case 'autosub_progress': return ['log-system', `[${pct(e.percent).trim() || '…'}] ${e.message}`];
        case 'autosub_warn': return ['log-warn', `[CẢNH BÁO] ${e.message}`];
        case 'autosub_error': return ['log-error', `[LỖI] ${e.error}`];
        case 'autosub_done': return ['log-success',
            e.translate_only ? `[XONG] Đã xuất phụ đề: ${e.output}` : `[XONG] Video kết quả: ${e.output}`];
        case 'ocr_progress': return ['', `  OCR${pct(e.percent)} ${e.message || ''}`];
        default: return null;
    }
}

function renderLogLine(consoleId, raw) {
    const text = String(raw);
    if (text === '[PING]') return;
    const trimmed = text.trim();
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
        try {
            const parsed = JSON.parse(trimmed);
            const described = describeEvent(parsed);
            if (described) { appendLog(consoleId, described[1], described[0]); return; }
        } catch (err) { /* không phải JSON của adapter — in thô */ }
    }
    let cls = '';
    if (/\[LỖI\]|\[ERROR\]|Traceback|Error:/i.test(text)) cls = 'log-error';
    else if (/\[THÀNH CÔNG\]|\[XONG\]|\[SUCCESS\]/i.test(text)) cls = 'log-success';
    else if (/\[CẢNH BÁO\]|\[WARN/i.test(text)) cls = 'log-warn';
    else if (/\[HỆ THỐNG\]|\[SYSTEM\]|\[Info\]/i.test(text)) cls = 'log-system';
    appendLog(consoleId, text, cls);
}

function streamLogs(taskKey, consoleId, onFinish) {
    if (state.streams[taskKey]) state.streams[taskKey].close();
    const source = new EventSource(`/api/tasks/logs/${taskKey}`);
    state.streams[taskKey] = source;
    source.onmessage = (event) => {
        renderLogLine(consoleId, event.data);
        if (/Process completed/i.test(event.data)) {
            source.close();
            delete state.streams[taskKey];
            setRunning(taskKey, false);
            if (onFinish) onFinish();
        }
    };
    source.onerror = () => {
        source.close();
        delete state.streams[taskKey];
        // SSE đứt không có nghĩa tác vụ đã xong — hỏi lại trạng thái thật.
        api(`/api/tasks/status/${taskKey}`).then((s) => {
            if (s.running) setTimeout(() => streamLogs(taskKey, consoleId, onFinish), 1500);
            else { setRunning(taskKey, false); if (onFinish) onFinish(); }
        }).catch(() => setRunning(taskKey, false));
    };
}

const RUN_BUTTONS = {
    download: ['btnDlStart', 'btnDlStop'],
    translate: ['btnTrStart', 'btnTrStop'],
    merge: ['btnMgStart', 'btnMgStop'],
};

function setRunning(taskKey, running) {
    const pair = RUN_BUTTONS[taskKey];
    if (pair) {
        const [startId, stopId] = pair;
        if ($(startId)) $(startId).style.display = running ? 'none' : '';
        if ($(stopId)) $(stopId).style.display = running ? '' : 'none';
    }
    const anyRunning = Object.keys(state.streams).length > 0 || running;
    const badge = $('statusBadge');
    if (badge) {
        badge.textContent = anyRunning ? 'Đang chạy' : 'Rảnh';
        badge.className = 'badge ' + (anyRunning ? 'badge-active' : 'badge-inactive');
    }
    if (!running) { loadStats(); }
}

async function resumeRunningTasks() {
    let running = [];
    try { running = (await api('/api/tasks/running')).running || []; } catch (e) { return; }
    running.forEach((key) => {
        if (!RUN_BUTTONS[key]) return;
        setRunning(key, true);
        streamLogs(key, `logConsole-${key}`, key === 'download' ? loadLibrary : loadLibrary);
    });
}

async function stopTask(taskKey) {
    try {
        await api(`/api/tasks/stop?task_key=${encodeURIComponent(taskKey)}`, { method: 'POST' });
        toast('Đã gửi yêu cầu dừng.', 'warn');
    } catch (e) { toast(e.message, 'error'); }
}

/* ------------------------------------------------------------ Cào video */
function urlsFromBox() {
    return ($('dlUrls').value || '').split('\n').map((s) => s.trim()).filter(Boolean);
}

function downloadPayload(urls) {
    return {
        urls,
        platform: $('dlPlatform').value,
        cookies_file: $('dlCookies').value.trim() || null,
        max_items: Number($('dlMaxItems').value || 0),
        skip_existing: $('dlSkipExisting').checked,
        stop_on_error: $('dlStopOnError').checked,
        auto_translate: $('dlAutoTranslate').checked,
        translate: $('dlAutoTranslate').checked ? translateParams() : null,
    };
}

async function doProbe() {
    const urls = urlsFromBox();
    if (!urls.length) { toast('Chưa nhập link nào.', 'warn'); return; }
    const btn = $('btnDlProbe');
    btn.disabled = true; btn.textContent = '⏳ Đang đọc danh sách…';
    try {
        const data = await api('/api/download/probe', {
            method: 'POST', body: JSON.stringify(downloadPayload(urls)),
        });
        state.probe = data.entries || [];
        renderProbe(data);
        toast(`Tìm thấy ${state.probe.length} video.`, 'success');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        btn.disabled = false; btn.textContent = '🔍 Xem trước danh sách';
    }
}

function renderProbe(data) {
    $('dlProbeBox').style.display = '';
    $('dlProbeCount').textContent = state.probe.length;
    const rows = state.probe.map((e, i) => `
        <label class="list-row">
            <input type="checkbox" class="probe-check" data-idx="${i}" checked>
            <span class="list-main">
                <b>${esc(e.title)}</b>
                <small>${esc(e.uploader || '')} ${e.duration ? '· ' + fmtDuration(e.duration) : ''}</small>
                <small class="dim">${esc(e.url)}</small>
            </span>
        </label>`).join('');
    const errors = (data.errors || []).map((er) =>
        `<div class="list-row log-error"><span class="list-main">${esc(er.url)} — ${esc(er.error)}</span></div>`).join('');
    $('dlProbeList').innerHTML = rows + errors || '<p class="help-text">Không có video nào.</p>';
}

async function startDownload(urls) {
    if (!urls.length) { toast('Chưa nhập link nào.', 'warn'); return; }
    $('logConsole-download').innerHTML = '';
    try {
        await api('/api/download/start', { method: 'POST', body: JSON.stringify(downloadPayload(urls)) });
        setRunning(TASKS.download, true);
        streamLogs(TASKS.download, 'logConsole-download', loadLibrary);
    } catch (e) { toast(e.message, 'error'); }
}

/* -------------------------------------------------------------- Thư viện */
async function loadLibrary() {
    try {
        state.library = await api('/api/videos');
    } catch (e) {
        $('libList').innerHTML = `<p class="help-text">Không đọc được thư viện: ${esc(e.message)}</p>`;
        return;
    }
    renderLibrary();
    renderTranslateSelection();
    loadStats();
}

function filteredLibrary() {
    const q = ($('libSearch').value || '').toLowerCase();
    const filter = $('libFilter').value;
    return state.library.filter((v) => {
        if (q && !(v.title || '').toLowerCase().includes(q)) return false;
        if (filter === 'translated' && !v.has_translation) return false;
        if (filter === 'untranslated' && v.has_translation) return false;
        if (filter === 'missing' && v.exists) return false;
        return true;
    });
}

function renderLibrary() {
    const items = filteredLibrary();
    if (!items.length) {
        $('libList').innerHTML = '<p class="help-text" style="text-align:center;">'
            + 'Chưa có video nào. Sang tab <b>Cào Video</b> để tải, hoặc nhập video có sẵn ở trên.</p>';
        return;
    }
    $('libList').innerHTML = items.map((v) => {
        const subs = (v.subs || []).map((s) => `
            <span class="chip">
                ${esc(s.name)}
                <a href="#" data-act="sub-edit" data-id="${esc(v.entry_id)}" data-name="${esc(s.name)}">sửa</a>
                <a href="/api/videos/${encodeURIComponent(v.entry_id)}/sub?name=${encodeURIComponent(s.name)}&download=true">tải</a>
            </span>`).join('');
        const outs = (v.outputs || []).map((o) => `
            <span class="chip">
                ${esc(o.name)} · ${esc(o.size_human)}
                <a href="#" data-act="play-out" data-id="${esc(v.entry_id)}" data-name="${esc(o.name)}">xem</a>
                <a href="#" data-act="merge-add" data-id="${esc(v.entry_id)}" data-name="${esc(o.name)}">ghép</a>
            </span>`).join('');
        return `
        <div class="lib-card">
            <label class="lib-head">
                <input type="checkbox" class="lib-check" data-id="${esc(v.entry_id)}"
                       ${state.selected.has(v.entry_id) ? 'checked' : ''}>
                <span class="list-main">
                    <b>${esc(v.title)}</b>
                    <small>
                        ${esc(v.platform || 'local')} ·
                        ${v.width ? v.width + '×' + v.height + ' · ' : ''}${fmtDuration(v.duration)} ·
                        ${esc(v.size_human)}
                        ${v.has_translation ? '<b class="ok"> · đã có bản dịch</b>' : ''}
                        ${v.exists ? '' : '<b class="bad"> · thiếu file trên đĩa</b>'}
                    </small>
                    ${v.url ? `<small class="dim">${esc(v.url)}</small>` : ''}
                </span>
            </label>
            <div class="lib-actions">
                <button class="btn btn-secondary btn-sm" data-act="play" data-id="${esc(v.entry_id)}">▶️ Xem</button>
                <button class="btn btn-secondary btn-sm" data-act="folder" data-id="${esc(v.entry_id)}">📂 Thư mục</button>
                <button class="btn btn-secondary btn-sm" data-act="translate-one" data-id="${esc(v.entry_id)}">🈯 Dịch</button>
                <button class="btn btn-danger btn-sm" data-act="delete" data-id="${esc(v.entry_id)}">🗑️</button>
            </div>
            ${subs ? `<div class="chips"><b>Phụ đề:</b> ${subs}</div>` : ''}
            ${outs ? `<div class="chips"><b>Bản đã gắn sub:</b> ${outs}</div>` : ''}
        </div>`;
    }).join('');
}

function libSelectionIds() {
    return state.library.filter((v) => state.selected.has(v.entry_id)).map((v) => v.entry_id);
}

async function deleteSelected() {
    const ids = libSelectionIds();
    if (!ids.length) { toast('Chưa chọn video nào.', 'warn'); return; }
    if (!confirm(`Xoá ${ids.length} video khỏi thư viện? Thao tác này không hoàn tác.`)) return;
    for (const id of ids) {
        try { await api(`/api/videos/${encodeURIComponent(id)}`, { method: 'DELETE' }); }
        catch (e) { toast(`Không xoá được ${id}: ${e.message}`, 'error'); }
    }
    state.selected.clear();
    toast('Đã xoá.', 'success');
    loadLibrary();
}

function openPlayer(entryId, kind, name, title) {
    const query = `kind=${encodeURIComponent(kind)}&name=${encodeURIComponent(name || '')}`;
    $('playerTitle').textContent = title || 'Xem video';
    $('playerVideo').src = `/api/videos/${encodeURIComponent(entryId)}/play?${query}`;
    $('modalPlayer').classList.add('open');
}

async function openSubEditor(entryId, name) {
    try {
        const res = await fetch(`/api/videos/${encodeURIComponent(entryId)}/sub?name=${encodeURIComponent(name)}`);
        if (!res.ok) throw new Error(await res.text());
        $('subEditor').value = await res.text();
        state.subCtx = { entryId, name };
        $('subTitle').textContent = `Sửa phụ đề — ${name}`;
        $('modalSub').classList.add('open');
    } catch (e) { toast(e.message, 'error'); }
}

/* ---------------------------------------------------------------- Dịch */
function translateParams() {
    const engine = $('trLlmEngine').value;
    const params = {
        source_lang: $('trSourceLang').value,
        target_lang: $('trTargetLang').value,
        sub_source: $('trSubSource').value,
        source_srt: $('trSourceSrt').value.trim() || null,
        translate_only: $('trTranslateOnly').checked,
        no_translate: $('trNoTranslate').checked,
        burn_method: $('trBurnMethod').value,
        clean_audio: $('trCleanAudio').checked,
        enable_voiceover: $('trVoiceover').checked,
        tts_engine: $('trTtsEngine').value,
        tts_voice: $('trTtsVoice').value,
        auto_clone: $('trAutoClone').checked,
        ducking_ratio: Number($('trDucking').value || 90),
        llm_engine: engine,
        llm_api_key: $('trGeminiKey').value.trim() || null,
        llm_offline_base_url: engine === 'gemini_api' ? ($('trBaseUrl').value.trim() || null) : null,
        llm_offline_model: engine === 'ollama' ? ($('trOllamaModel').value || null) : null,
        font_name: $('trFontName').value,
        font_size: Number($('trFontSize').value || 45),
        text_color: $('trTextColor').value,
        stroke_color: $('trStrokeColor').value,
        stroke_width: Number($('trStrokeWidth').value || 1.5),
        bg_style: $('trBgStyle').value,
        bg_color: $('trBgColor').value,
        bg_alpha: Number($('trBgAlpha').value || 140),
        sub_position: $('trSubPosition').value,
        custom_position: Number($('trCustomPos').value || 70),
    };
    if (state.roi) Object.assign(params, {
        crop_x: state.roi.x, crop_y: state.roi.y, crop_w: state.roi.w, crop_h: state.roi.h,
    });
    return params;
}

function refreshTranslateVisibility() {
    const subSource = $('trSubSource').value;
    $('grpTrOcr').style.display = subSource === 'ocr' ? '' : 'none';
    $('grpTrImportSrt').style.display = subSource === 'import' ? '' : 'none';
    $('grpTrCleanAudio').style.display = subSource === 'whisper' ? '' : 'none';

    const translateOnly = $('trTranslateOnly').checked;
    $('grpTrBurnMethod').style.display = translateOnly ? 'none' : '';
    $('grpTrStyle').style.display = translateOnly ? 'none' : '';

    const voice = $('trVoiceover').checked && !translateOnly;
    $('grpTrVoice').style.display = voice ? '' : 'none';
    $('grpTrAutoClone').style.display = $('trTtsEngine').value === 'clone' ? '' : 'none';

    $('grpTrBgColor').style.display = $('trBgStyle').value === 'Box' ? '' : 'none';
    $('grpTrBgAlpha').style.display = $('trBgStyle').value === 'Box' ? '' : 'none';
    $('grpTrCustomPos').style.display = $('trSubPosition').value === 'custom' ? '' : 'none';

    const engine = $('trLlmEngine').value;
    $('grpTrOllamaModel').style.display = engine === 'ollama' ? '' : 'none';
    $('grpTrGeminiKey').style.display = engine === 'gemini' ? '' : 'none';
    $('grpTrBaseUrl').style.display = engine === 'gemini_api' ? '' : 'none';
}

function renderTranslateSelection() {
    const ids = libSelectionIds();
    const box = $('trSelected');
    if (!ids.length) {
        box.innerHTML = '<p class="help-text" style="text-align:center;">'
            + 'Chưa chọn video nào — sang tab Thư Viện và tích chọn.</p>';
        return;
    }
    box.innerHTML = state.library.filter((v) => state.selected.has(v.entry_id)).map((v) => `
        <div class="list-row">
            <span class="list-main"><b>${esc(v.title)}</b>
                <small>${fmtDuration(v.duration)} · ${esc(v.size_human)}</small></span>
            <button type="button" class="btn btn-secondary btn-sm" data-act="unselect" data-id="${esc(v.entry_id)}">bỏ</button>
        </div>`).join('');
}

async function startTranslate() {
    const ids = libSelectionIds();
    if (!ids.length) { toast('Chưa chọn video nào để dịch.', 'warn'); goTab('library'); return; }
    const payload = { entry_ids: ids, ...translateParams() };
    $('logConsole-translate').innerHTML = '';
    try {
        const res = await api('/api/translate/start', { method: 'POST', body: JSON.stringify(payload) });
        setRunning(TASKS.translate, true);
        streamLogs(TASKS.translate, 'logConsole-translate', loadLibrary);
        toast(`Đã đưa ${res.count} video vào hàng đợi dịch.`, 'success');
    } catch (e) { toast(e.message, 'error'); }
}

async function prepareRoi() {
    const ids = libSelectionIds();
    if (!ids.length) { toast('Chọn một video ở tab Thư Viện trước đã.', 'warn'); return; }
    const btn = $('btnTrPrepare');
    btn.disabled = true; btn.textContent = '⏳ Đang lấy khung hình…';
    try {
        const data = await api('/api/autosub/prepare', {
            method: 'POST', body: JSON.stringify({ entry_id: ids[0] }),
        });
        state.prepared = data;
        $('trPreviewImg').src = data.preview_b64;
        $('trRoiArea').style.display = '';
        $('trRoiInfo').textContent = `Khung hình ${data.width}×${data.height}`;
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        btn.disabled = false; btn.textContent = '🖼️ Lấy khung hình xem trước';
    }
}

function initRoiPicker() {
    const area = $('trRoiArea');
    const rect = $('trRoiRect');
    let dragging = false, startX = 0, startY = 0;

    const posOf = (event) => {
        const box = area.getBoundingClientRect();
        return { x: event.clientX - box.left, y: event.clientY - box.top };
    };

    area.addEventListener('mousedown', (event) => {
        dragging = true;
        const p = posOf(event);
        startX = p.x; startY = p.y;
        Object.assign(rect.style, { display: 'block', left: `${p.x}px`, top: `${p.y}px`, width: '0px', height: '0px' });
        event.preventDefault();
    });
    area.addEventListener('mousemove', (event) => {
        if (!dragging) return;
        const p = posOf(event);
        Object.assign(rect.style, {
            left: `${Math.min(startX, p.x)}px`, top: `${Math.min(startY, p.y)}px`,
            width: `${Math.abs(p.x - startX)}px`, height: `${Math.abs(p.y - startY)}px`,
        });
    });
    window.addEventListener('mouseup', (event) => {
        if (!dragging) return;
        dragging = false;
        const img = $('trPreviewImg');
        if (!img.clientWidth || !state.prepared) return;
        // Ảnh hiển thị bị co lại theo bề ngang khung — quy đổi về pixel THẬT của
        // video, vì PaddleOCR cắt theo toạ độ gốc chứ không theo ảnh trên màn hình.
        const scale = state.prepared.width / img.clientWidth;
        const x = Math.round(parseFloat(rect.style.left) * scale);
        const y = Math.round(parseFloat(rect.style.top) * scale);
        const w = Math.round(parseFloat(rect.style.width) * scale);
        const h = Math.round(parseFloat(rect.style.height) * scale);
        if (w < 8 || h < 8) { state.roi = null; rect.style.display = 'none'; return; }
        state.roi = { x, y, w, h };
        $('trRoiInfo').textContent = `Vùng phụ đề: ${w}×${h} tại (${x}, ${y})`;
    });
}

/* --------------------------------------------------------------- Ghép */
function addToMerge(entryId, kind, name) {
    const entry = state.library.find((v) => v.entry_id === entryId);
    const label = `${entry ? entry.title : entryId} — ${kind === 'source' ? 'bản gốc' : name}`;
    if (state.mergeList.some((it) => it.entry_id === entryId && it.kind === kind && it.name === name)) return;
    state.mergeList.push({ entry_id: entryId, kind, name: name || '', label });
    renderMergeList();
}

function renderMergeList() {
    const box = $('mgList');
    if (!state.mergeList.length) {
        box.innerHTML = '<p class="help-text" style="text-align:center;">Chưa có video nào — '
            + 'thêm từ tab Thư Viện hoặc bấm "Nạp mọi bản đã dịch".</p>';
        return;
    }
    box.innerHTML = state.mergeList.map((it, i) => `
        <div class="list-row">
            <span class="list-main"><b>${i + 1}.</b> ${esc(it.label)}</span>
            <span style="display:flex; gap:4px;">
                <button type="button" class="btn btn-secondary btn-sm" data-act="mg-up" data-idx="${i}">▲</button>
                <button type="button" class="btn btn-secondary btn-sm" data-act="mg-down" data-idx="${i}">▼</button>
                <button type="button" class="btn btn-danger btn-sm" data-act="mg-del" data-idx="${i}">✕</button>
            </span>
        </div>`).join('');
}

async function loadMerged() {
    try {
        const files = await api('/api/merged');
        $('mgDone').innerHTML = files.length ? files.map((f) => `
            <div class="list-row"><span class="list-main"><b>${esc(f.name)}</b>
                <small>${esc(f.size_human)} · ${esc(f.mtime)}</small></span></div>`).join('')
            : '<p class="help-text" style="text-align:center;">Chưa có bản ghép nào.</p>';
    } catch (e) { /* bỏ qua */ }
}

async function startMerge() {
    if (!state.mergeList.length) { toast('Chưa chọn video nào để ghép.', 'warn'); return; }
    $('logConsole-merge').innerHTML = '';
    try {
        await api('/api/merge/start', {
            method: 'POST',
            body: JSON.stringify({
                items: state.mergeList.map((it) => ({ entry_id: it.entry_id, kind: it.kind, name: it.name })),
                output_name: $('mgOutputName').value.trim(),
            }),
        });
        setRunning(TASKS.merge, true);
        streamLogs(TASKS.merge, 'logConsole-merge', loadMerged);
    } catch (e) { toast(e.message, 'error'); }
}

/* ------------------------------------------------------- Thống kê & phụ */
async function loadStats() {
    try {
        const s = await api('/api/stats');
        $('sideStats').innerHTML = `${s.videos} video · ${s.translated} đã dịch<br>`
            + `${s.subs} phụ đề · ${s.merged} bản ghép<br>${esc(s.size_total_human)}`;
        if ($('stVideos')) {
            $('stVideos').textContent = s.videos;
            $('stTranslated').textContent = s.translated;
            $('stSubs').textContent = s.subs;
            $('stMerged').textContent = s.merged;
            $('stSize').textContent = s.size_total_human;
        }
    } catch (e) { /* bỏ qua */ }
}

async function loadOllamaModels() {
    try {
        const data = await api('/api/ollama/models');
        const select = $('trOllamaModel');
        const wanted = state.wantedOllamaModel || select.value;
        const names = data.models.map((m) => m.name);
        // Model người dùng đang chọn có thể không nằm trong danh sách khuyến nghị —
        // vẫn phải giữ lại, nếu không lần lưu sau sẽ âm thầm đổi sang model khác.
        if (wanted && !names.includes(wanted)) data.models.unshift({ name: wanted, label: '', installed: true });
        select.innerHTML = data.models.map((m) =>
            `<option value="${esc(m.name)}">${esc(m.name)}${m.installed ? '' : ' (chưa cài)'}` +
            `${m.label ? ' — ' + esc(m.label) : ''}</option>`).join('');
        if (wanted) select.value = wanted;
        $('trOllamaStatus').textContent = data.ollama_online
            ? 'Ollama đang chạy.' : 'Ollama chưa chạy — app sẽ tự bật khi cần.';
    } catch (e) { /* bỏ qua */ }
}

async function loadGpu() {
    try {
        const gpu = await api('/api/system/gpu-info');
        $('gpuInfo').textContent = `🎮 ${gpu.name}${gpu.vram !== 'N/A' ? ' · ' + gpu.vram : ''}`;
    } catch (e) { /* bỏ qua */ }
}

/* ------------------------------------------------------------ Sự kiện */
function bindEvents() {
    $('btnSaveSettings').addEventListener('click', () => saveAllSettings().catch((e) => toast(e.message, 'error')));
    $('btnOpenStorage').addEventListener('click', () =>
        api('/api/system/open-folder?kind=storage', { method: 'POST' }).catch((e) => toast(e.message, 'error')));

    // --- Cào video
    $('formDownload').addEventListener('submit', (e) => { e.preventDefault(); startDownload(urlsFromBox()); });
    $('btnDlProbe').addEventListener('click', doProbe);
    $('btnDlStop').addEventListener('click', () => stopTask(TASKS.download));
    $('btnDlCheckAll').addEventListener('click', () =>
        document.querySelectorAll('.probe-check').forEach((c) => { c.checked = true; }));
    $('btnDlUncheckAll').addEventListener('click', () =>
        document.querySelectorAll('.probe-check').forEach((c) => { c.checked = false; }));
    $('btnDlStartSelected').addEventListener('click', () => {
        const urls = [...document.querySelectorAll('.probe-check')]
            .filter((c) => c.checked)
            .map((c) => state.probe[Number(c.dataset.idx)].url);
        startDownload(urls);
    });

    // --- Thư viện
    $('btnLibReload').addEventListener('click', loadLibrary);
    $('libSearch').addEventListener('input', renderLibrary);
    $('libFilter').addEventListener('change', renderLibrary);
    $('btnLibSelectAll').addEventListener('click', () => {
        filteredLibrary().forEach((v) => state.selected.add(v.entry_id));
        renderLibrary(); renderTranslateSelection();
    });
    $('btnLibClearSel').addEventListener('click', () => {
        state.selected.clear(); renderLibrary(); renderTranslateSelection();
    });
    $('btnLibDelete').addEventListener('click', deleteSelected);
    $('btnLibTranslate').addEventListener('click', () => {
        if (!state.selected.size) { toast('Chưa chọn video nào.', 'warn'); return; }
        goTab('translate');
    });
    $('btnLibMerge').addEventListener('click', () => {
        state.library.filter((v) => state.selected.has(v.entry_id)).forEach((v) => {
            const outputs = v.outputs || [];
            if (outputs.length) addToMerge(v.entry_id, 'output', outputs[outputs.length - 1].name);
            else addToMerge(v.entry_id, 'source', '');
        });
        goTab('merge');
    });
    $('btnLibImport').addEventListener('click', async () => {
        const path = $('libImportPath').value.trim();
        if (!path) { toast('Nhập đường dẫn file video trước đã.', 'warn'); return; }
        try {
            await api('/api/videos/import', {
                method: 'POST',
                body: JSON.stringify({ path, copy_file: $('libImportCopy').checked }),
            });
            $('libImportPath').value = '';
            toast('Đã thêm vào thư viện.', 'success');
            loadLibrary();
        } catch (e) { toast(e.message, 'error'); }
    });

    $('libList').addEventListener('change', (event) => {
        const check = event.target.closest('.lib-check');
        if (!check) return;
        if (check.checked) state.selected.add(check.dataset.id);
        else state.selected.delete(check.dataset.id);
        renderTranslateSelection();
    });

    $('libList').addEventListener('click', async (event) => {
        const el = event.target.closest('[data-act]');
        if (!el) return;
        const { act, id, name } = el.dataset;
        const entry = state.library.find((v) => v.entry_id === id);
        if (act === 'play') { event.preventDefault(); openPlayer(id, 'source', '', entry && entry.title); }
        if (act === 'play-out') { event.preventDefault(); openPlayer(id, 'output', name, name); }
        if (act === 'sub-edit') { event.preventDefault(); openSubEditor(id, name); }
        if (act === 'merge-add') {
            event.preventDefault(); addToMerge(id, 'output', name); toast('Đã thêm vào danh sách ghép.', 'success');
        }
        if (act === 'folder') {
            api(`/api/videos/${encodeURIComponent(id)}/open-folder`, { method: 'POST' })
                .catch((e) => toast(e.message, 'error'));
        }
        if (act === 'translate-one') {
            state.selected.clear(); state.selected.add(id);
            renderLibrary(); renderTranslateSelection(); goTab('translate');
        }
        if (act === 'delete') {
            if (!confirm(`Xoá "${entry ? entry.title : id}" khỏi thư viện?`)) return;
            try {
                await api(`/api/videos/${encodeURIComponent(id)}`, { method: 'DELETE' });
                state.selected.delete(id);
                toast('Đã xoá.', 'success');
                loadLibrary();
            } catch (e) { toast(e.message, 'error'); }
        }
    });

    // --- Dịch
    ['trSubSource', 'trTranslateOnly', 'trVoiceover', 'trTtsEngine', 'trBgStyle',
        'trSubPosition', 'trLlmEngine'].forEach((id) =>
        $(id).addEventListener('change', refreshTranslateVisibility));
    $('formTranslate').addEventListener('submit', (e) => { e.preventDefault(); startTranslate(); });
    $('btnTrStop').addEventListener('click', () => stopTask(TASKS.translate));
    $('btnTrPrepare').addEventListener('click', prepareRoi);
    $('btnTrClearRoi').addEventListener('click', () => {
        state.roi = null;
        $('trRoiRect').style.display = 'none';
        $('trRoiInfo').textContent = 'Đã bỏ vùng chọn — sẽ quét cả khung hình.';
    });
    $('btnTrOpenOut').addEventListener('click', () => {
        const ids = libSelectionIds();
        if (!ids.length) { api('/api/system/open-folder?kind=videos', { method: 'POST' }); return; }
        api(`/api/videos/${encodeURIComponent(ids[0])}/open-folder?kind=output`, { method: 'POST' })
            .catch((e) => toast(e.message, 'error'));
    });
    $('trSelected').addEventListener('click', (event) => {
        const el = event.target.closest('[data-act="unselect"]');
        if (!el) return;
        state.selected.delete(el.dataset.id);
        renderLibrary(); renderTranslateSelection();
    });

    // --- Ghép
    $('formMerge').addEventListener('submit', (e) => { e.preventDefault(); startMerge(); });
    $('btnMgStop').addEventListener('click', () => stopTask(TASKS.merge));
    $('btnMgClear').addEventListener('click', () => { state.mergeList = []; renderMergeList(); });
    $('btnMgOpen').addEventListener('click', () =>
        api('/api/system/open-folder?kind=merged', { method: 'POST' }).catch((e) => toast(e.message, 'error')));
    $('btnMgLoadOutputs').addEventListener('click', () => {
        state.library.forEach((v) => (v.outputs || []).forEach((o) => addToMerge(v.entry_id, 'output', o.name)));
        if (!state.mergeList.length) toast('Chưa có bản đã gắn phụ đề nào.', 'warn');
    });
    $('mgList').addEventListener('click', (event) => {
        const el = event.target.closest('[data-act]');
        if (!el) return;
        const idx = Number(el.dataset.idx);
        if (el.dataset.act === 'mg-del') state.mergeList.splice(idx, 1);
        if (el.dataset.act === 'mg-up' && idx > 0) {
            [state.mergeList[idx - 1], state.mergeList[idx]] = [state.mergeList[idx], state.mergeList[idx - 1]];
        }
        if (el.dataset.act === 'mg-down' && idx < state.mergeList.length - 1) {
            [state.mergeList[idx + 1], state.mergeList[idx]] = [state.mergeList[idx], state.mergeList[idx + 1]];
        }
        renderMergeList();
    });

    // --- Cấu hình
    $('btnCleanupPreview').addEventListener('click', async () => {
        const res = await api('/api/maintenance/cleanup-tasks?dry_run=true', { method: 'POST' });
        $('cleanupResult').textContent = res.count
            ? `Sẽ xoá ${res.count} thư mục tạm (~${res.freed_mb} MB).`
            : 'Không có file tạm nào để xoá.';
    });
    $('btnCleanupRun').addEventListener('click', async () => {
        const res = await api('/api/maintenance/cleanup-tasks?dry_run=false', { method: 'POST' });
        $('cleanupResult').textContent = `Đã xoá ${res.count} thư mục tạm (~${res.freed_mb} MB).`;
        loadStats();
    });

    // --- Modal
    $('btnPlayerClose').addEventListener('click', () => {
        $('playerVideo').pause();
        $('playerVideo').src = '';
        $('modalPlayer').classList.remove('open');
    });
    $('btnSubCancel').addEventListener('click', () => $('modalSub').classList.remove('open'));
    $('btnSubDownload').addEventListener('click', () => {
        if (!state.subCtx) return;
        const { entryId, name } = state.subCtx;
        window.location.href =
            `/api/videos/${encodeURIComponent(entryId)}/sub?name=${encodeURIComponent(name)}&download=true`;
    });
    $('btnSubUse').addEventListener('click', () => {
        if (!state.subCtx) return;
        const { entryId, name } = state.subCtx;
        const entry = state.library.find((v) => v.entry_id === entryId);
        const sub = entry && (entry.subs || []).find((s) => s.name === name);
        if (!sub) { toast('Không thấy file phụ đề này trên đĩa.', 'error'); return; }
        // Phụ đề vừa sửa tay đã đúng ngôn ngữ đích -> ghi thẳng, dịch lại là hỏng bản sửa.
        $('trSourceSrt').value = sub.path;
        $('trSubSource').value = 'import';
        $('trNoTranslate').checked = true;
        $('trTranslateOnly').checked = false;
        state.selected.clear();
        state.selected.add(entryId);
        renderLibrary();
        renderTranslateSelection();
        refreshTranslateVisibility();
        $('modalSub').classList.remove('open');
        goTab('translate');
        toast('Đã nạp phụ đề — bấm "Bắt đầu dịch" để ghi vào video.', 'success');
    });
    $('btnSubSave').addEventListener('click', async () => {
        if (!state.subCtx) return;
        const { entryId, name } = state.subCtx;
        try {
            await api(`/api/videos/${encodeURIComponent(entryId)}/sub`, {
                method: 'POST',
                body: JSON.stringify({ name, content: $('subEditor').value }),
            });
            toast('Đã lưu phụ đề.', 'success');
            $('modalSub').classList.remove('open');
            loadLibrary();
        } catch (e) { toast(e.message, 'error'); }
    });
}

/* ------------------------------------------------------------------ Init */
document.addEventListener('DOMContentLoaded', async () => {
    initTabs();
    bindEvents();
    initRoiPicker();
    try { await loadConfig(); } catch (e) { toast(`Không đọc được cấu hình: ${e.message}`, 'error'); }
    try { await loadUiSettings(); } catch (e) { /* lần đầu chưa có file */ }
    refreshTranslateVisibility();
    loadOllamaModels();   // Ollama trả lời chậm vài giây — đừng chặn cả trang chờ nó
    loadGpu();
    loadLibrary();
    loadMerged();
    resumeRunningTasks();
});
