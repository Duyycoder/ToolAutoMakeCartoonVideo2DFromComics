/* Giao diện công cụ Cào & Dịch Video.
 *
 * Ba tác vụ nặng dùng task_key cố định ("download" | "translate" | "merge") nên
 * mở lại trang là nối lại đúng luồng log đang chạy, không cần nhớ mã tác vụ.
 */
const TASKS = { download: 'download', translate: 'translate', merge: 'merge', import: 'import' };

const state = {
    config: {},
    library: [],
    selected: new Set(),   // entry_id đang chọn ở tab Thư Viện
    mergeList: [],         // [{entry_id, kind, name, label}]
    batch: [],             // hàng đợi tab Lô: [{kind:'file'|'url', value, title, note}]
    batches: [],           // các lô đã chạy, để tab Ghép nạp lại
    duAn: null,            // dự án đang mở: {folder, name, videos...}
    duAnVideos: [],        // video của dự án, ĐÃ theo thứ tự đánh số
    duAnChon: [],          // tên file đã chọn, theo đúng thứ tự người dùng sắp
    duAnModal: null,       // ngữ cảnh cửa sổ tạo/init dự án
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
    // Hàng đợi đang soạn dở không phải là một ô nhập nên lưu riêng, để F5 hay tắt
    // app giữa chừng không mất công sắp lại thứ tự.
    if (saved && Array.isArray(saved._batchQueue)) state.batch = saved._batchQueue;
    refreshTranslateVisibility();
    refreshBatchVisibility();
    renderBatch();
}

async function saveAllSettings() {
    const cfg = JSON.parse(JSON.stringify(state.config || {}));
    document.querySelectorAll('[data-cfg]').forEach((el) => {
        const value = readField(el);
        if (value !== null) setByPath(cfg, el.dataset.cfg, value);
    });
    const ui = { _batchQueue: state.batch };
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

// Tải và nhập file dùng chung cặp nút của tab Lô: một lô có thể chạy bằng cả hai.
const RUN_BUTTONS = {
    download: ['btnBatchRun', 'btnBatchStop'],
    import: ['btnBatchRun', 'btnBatchStop'],
    translate: ['btnTrStart', 'btnTrStop'],
    merge: ['btnMgStart', 'btnMgStop'],
};

const TASK_CONSOLE = {
    download: 'logConsole-batch',
    import: 'logConsole-batch',
    translate: 'logConsole-translate',
    merge: 'logConsole-merge',
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
        if (!TASK_CONSOLE[key]) return;
        setRunning(key, true);
        streamLogs(key, TASK_CONSOLE[key], key === 'merge' ? loadMerged : loadLibrary);
    });
}

async function stopTask(taskKey) {
    try {
        await api(`/api/tasks/stop?task_key=${encodeURIComponent(taskKey)}`, { method: 'POST' });
        toast('Đã gửi yêu cầu dừng.', 'warn');
    } catch (e) { toast(e.message, 'error'); }
}

/* --------------------------------------------------------------- Lô video
 * Hàng đợi gom hai nguồn (file trên máy + link) vào MỘT danh sách đã sắp; vị trí
 * trong danh sách này chính là thứ tự ghép, nên mọi thao tác đều giữ nguyên nó.
 */
function urlsFromBox() {
    return ($('dlUrls').value || '').split('\n').map((s) => s.trim()).filter(Boolean);
}

function sourceParams() {
    return {
        platform: $('dlPlatform').value,
        cookies_file: $('dlCookies').value.trim() || null,
        max_items: Number($('dlMaxItems').value || 0),
    };
}

/** Sắp tự nhiên: "tap2" đứng trước "tap10" (sắp theo chữ thì ngược lại). */
function compareNatural(a, b) {
    return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' });
}

function baseName(path) {
    return String(path || '').split(/[\\/]/).pop();
}

function addToQueue(items) {
    const seen = new Set(state.batch.map((it) => it.value));
    let added = 0;
    items.forEach((it) => {
        if (!it.value || seen.has(it.value)) return;
        seen.add(it.value);
        state.batch.push(it);
        added += 1;
    });
    renderBatch();
    return added;
}

function renderBatch() {
    const box = $('bqList');
    $('bqCount').textContent = state.batch.length;
    if (!state.batch.length) {
        box.innerHTML = '<p class="help-text" style="text-align:center;">Hàng đợi trống — '
            + 'chọn file trên máy hoặc dán link rồi bấm "Giải link".</p>';
        return;
    }
    box.innerHTML = state.batch.map((it, i) => `
        <div class="list-row">
            <span class="list-main">
                <b>${i + 1}. ${esc(it.title || baseName(it.value))}</b>
                <small class="dim">${it.kind === 'file' ? '📁 ' : '🔗 '}${esc(it.note || it.value)}</small>
            </span>
            <span style="display:flex; gap:4px;">
                <button type="button" class="btn btn-secondary btn-sm" data-act="bq-up" data-idx="${i}">▲</button>
                <button type="button" class="btn btn-secondary btn-sm" data-act="bq-down" data-idx="${i}">▼</button>
                <button type="button" class="btn btn-danger btn-sm" data-act="bq-del" data-idx="${i}">✕</button>
            </span>
        </div>`).join('');
}

async function pickFiles(mode) {
    const btn = mode === 'folder' ? $('btnPickFolder') : $('btnPickFiles');
    const label = btn.textContent;
    btn.disabled = true; btn.textContent = '⏳ Đang mở hộp thoại…';
    try {
        const res = await api('/api/system/pick-files', {
            method: 'POST', body: JSON.stringify({ mode }),
        });
        if (res.cancelled) return;
        if (!(res.paths || []).length) {
            toast(mode === 'folder'
                ? `Thư mục "${baseName(res.folder)}" không có file video nào.`
                : 'Chưa chọn video nào.', 'warn');
            return;
        }
        const added = addToQueue((res.paths || []).map((p) => ({
            kind: 'file', value: p, title: baseName(p).replace(/\.[^.]+$/, ''), note: p,
        })));
        toast(added ? `Đã thêm ${added} video vào hàng đợi.` : 'Các video này đã có trong hàng đợi.',
            added ? 'success' : 'warn');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        btn.disabled = false; btn.textContent = label;
    }
}

async function doProbe() {
    const urls = urlsFromBox();
    if (!urls.length) { toast('Chưa dán link nào.', 'warn'); return; }
    const btn = $('btnDlProbe');
    const label = btn.textContent;
    btn.disabled = true; btn.textContent = '⏳ Đang giải link…';
    try {
        // Giải playlist/kênh ngay tại đây: có vậy người dùng mới sắp được thứ tự
        // của từng video trước khi chạy, thay vì phó mặc cho lúc tải.
        const data = await api('/api/download/probe', {
            method: 'POST', body: JSON.stringify({ urls, ...sourceParams() }),
        });
        const entries = data.entries || [];
        const added = addToQueue(entries.map((e) => ({
            kind: 'url', value: e.url, title: e.title || e.url,
            note: `${e.uploader || ''}${e.duration ? ' · ' + fmtDuration(e.duration) : ''}`.trim() || e.url,
        })));
        (data.errors || []).forEach((er) => toast(`${er.url}: ${er.error}`, 'error'));
        toast(added ? `Đã thêm ${added} video vào hàng đợi.` : 'Các link này đã có trong hàng đợi.',
            added ? 'success' : 'warn');
        if (added) $('dlUrls').value = '';
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        btn.disabled = false; btn.textContent = label;
    }
}

/* Ô "soi": bản sao của một ô thật bên tab khác, để chỉnh ngay tại màn hình đang
 * đứng mà không phải nhảy tab. Giá trị chỉ có MỘT nguồn duy nhất là ô thật —
 * mọi hàm đọc tham số (translateParams…) vẫn đọc ô thật như cũ. */
function copyField(from, to) {
    if (to.type === 'checkbox') to.checked = from.checked;
    else to.value = from.value;
}

function bindMirrors() {
    document.querySelectorAll('[data-mirror]').forEach((clone) => {
        const src = $(clone.dataset.mirror);
        if (!src) return;
        // Chép luôn danh sách lựa chọn thay vì viết tay lần nữa — thêm/bớt option
        // ở ô thật là ô soi tự có theo, không bao giờ lệch nhau.
        if (src.tagName === 'SELECT') clone.innerHTML = src.innerHTML;
        copyField(src, clone);
        clone.addEventListener('change', () => {
            copyField(clone, src);
            src.dispatchEvent(new Event('change'));   // để refreshTranslateVisibility chạy theo
        });
        src.addEventListener('change', () => copyField(src, clone));
    });
}

function syncMirrors() {
    document.querySelectorAll('[data-mirror]').forEach((clone) => {
        const src = $(clone.dataset.mirror);
        if (src) copyField(src, clone);
    });
}

function refreshBatchVisibility() {
    const showMerge = $('bqDoMerge').checked;
    document.querySelectorAll('.bq-merge-opt').forEach((el) => {
        el.style.display = showMerge ? '' : 'none';
    });
    const showSub = $('dlAutoTranslate').checked;
    document.querySelectorAll('.bq-sub-opt').forEach((el) => {
        el.style.display = showSub ? '' : 'none';
    });
}

function mergeAfterPayload() {
    if (!$('bqDoMerge').checked) return null;
    return {
        enabled: true,
        output_name: $('bqMergeName').value.trim(),
        prefer: $('bqMergePrefer').value,
        normalize: $('bqNormalize').checked,
    };
}

/** Khúc dịch + ghép chỉ được gắn vào LỆNH CUỐI của lô, không thì nó chạy khi mới xong nửa. */
function batchTail() {
    const translate = $('dlAutoTranslate').checked;
    return {
        auto_translate: translate,
        translate: translate ? translateParams() : null,
        merge_after: mergeAfterPayload(),
    };
}

async function startDownloadLeg(urls, batchId, tail, batchName, duAn = '') {
    try {
        await api('/api/download/start', {
            method: 'POST',
            body: JSON.stringify({
                urls: urls.map((u) => u.value),
                batch_index: urls.map((u) => u.index),
                batch_id: batchId || '',
                batch_name: batchName || '',
                project_folder: duAn,
                skip_existing: $('dlSkipExisting').checked,
                stop_on_error: $('dlStopOnError').checked,
                ...sourceParams(),
                ...tail,
            }),
        });
        setRunning(TASKS.download, true);
        streamLogs(TASKS.download, 'logConsole-batch', afterBatch);
    } catch (e) {
        toast(e.message, 'error');
        setRunning(TASKS.download, false);
    }
}

function afterBatch() {
    loadLibrary();
    loadMerged();
    loadBatches();
}

async function runBatch() {
    if (!state.batch.length) { toast('Hàng đợi đang trống.', 'warn'); return; }

    const files = [], urls = [];
    state.batch.forEach((it, i) => {
        const slot = { value: it.value, title: it.title, index: i + 1 };
        (it.kind === 'file' ? files : urls).push(slot);
    });

    const batchName = $('bqName').value.trim();
    const tail = batchTail();
    const duAn = duAnDichCuaLo();
    $('logConsole-batch').innerHTML = '';

    if (!files.length) {
        startDownloadLeg(urls, '', tail, batchName, duAn);
        return;
    }

    try {
        const res = await api('/api/videos/import-batch', {
            method: 'POST',
            body: JSON.stringify({
                items: files.map((f) => ({ path: f.value, title: f.title, index: f.index })),
                copy_file: $('bqCopyFile').checked,
                batch_name: batchName,
                project_folder: duAn,
                // Còn link phải tải thì để khúc tải mang theo phần dịch/ghép.
                ...(urls.length ? {} : tail),
            }),
        });
        setRunning(TASKS.import, true);
        streamLogs(TASKS.import, 'logConsole-batch', () => {
            loadLibrary();
            if (urls.length) startDownloadLeg(urls, res.batch_id, tail, batchName, duAn);
            else afterBatch();
        });
    } catch (e) {
        toast(e.message, 'error');
        setRunning(TASKS.import, false);
    }
}

function stopBatch() {
    // Một lô có thể đang ở khúc nhập hoặc khúc tải — dừng cái nào đang chạy.
    Object.keys(state.streams).forEach((key) => {
        if (key === TASKS.import || key === TASKS.download) stopTask(key);
    });
}

/* ------------------------------------------------------------------ Dự án
 * Dự án = MỘT thư mục trên đĩa có `.duan.json`. Mở thư mục có sẵn video thì
 * luôn phải qua bảng duyệt đổi tên — đổi tên file không Ctrl+Z được.
 */
async function chonThuMuc() {
    try {
        const res = await api('/api/system/pick-files', {
            method: 'POST', body: JSON.stringify({ mode: 'folder' }),
        });
        return res.cancelled ? null : res;
    } catch (e) {
        toast(e.message, 'error');
        return null;
    }
}

function renderXemTruocDoiTen(danhSach) {
    $('duAnPreview').innerHTML = danhSach.map((x, i) => `
        <div class="list-row">
            <span class="list-main">
                <b>${i + 1}. ${esc(x.moi)}</b>
                <small class="dim">${x.doi ? `từ: ${esc(x.cu)}` : 'giữ nguyên tên'}</small>
            </span>
        </div>`).join('') || '<p class="help-text">Không có video nào.</p>';
}

function moModalDuAn(cheDo, thongTin) {
    state.duAnModal = { cheDo, ...thongTin };
    const laTao = cheDo === 'tao';
    $('duAnTitle').textContent = laTao ? 'Tạo dự án trống' : 'Mở thư mục thành dự án';
    $('duAnFolder').textContent = laTao
        ? `Sẽ tạo một thư mục con trong: ${thongTin.folder}`
        : thongTin.folder;
    $('duAnTen').value = thongTin.ten || '';
    $('duAnPreviewBox').style.display = laTao ? 'none' : '';
    $('btnDuAnGiuTen').style.display = laTao ? 'none' : '';
    $('btnDuAnXacNhan').textContent = laTao ? 'Tạo dự án' : 'Đổi tên & mở dự án';
    if (!laTao) renderXemTruocDoiTen(thongTin.xem_truoc || []);
    $('modalDuAn').classList.add('open');
}

async function moThuMucDuAn() {
    const chon = await chonThuMuc();
    if (!chon) return;
    try {
        const xem = await api('/api/project/inspect', {
            method: 'POST', body: JSON.stringify({ folder: chon.folder }),
        });
        if (xem.da_init) {          // đã là dự án rồi thì mở thẳng, không hỏi lại
            await moDuAn(xem.folder);
            return;
        }
        if (!xem.co_video) {
            toast(`Thư mục "${baseName(xem.folder)}" không có file video nào.`, 'warn');
            return;
        }
        moModalDuAn('init', { folder: xem.folder, ten: xem.ten, xem_truoc: xem.xem_truoc });
    } catch (e) { toast(e.message, 'error'); }
}

/** `opts.veTab`: tạo xong thì về tab nào (tạo từ tab Lô Video thì ở lại đó để chạy lô). */
async function taoDuAnMoi(opts = {}) {
    const chon = await chonThuMuc();
    if (!chon) return;
    moModalDuAn('tao', { folder: chon.folder, ten: '', veTab: opts.veTab || '' });
}

/** Lô đổ vào dự án đang mở (nếu có và người dùng không tắt), không thì "" = thư viện chung. */
function duAnDichCuaLo() {
    return state.duAn && $('bqVaoDuAn').checked ? state.duAn.folder : '';
}

/** Mọi chỗ trên giao diện phụ thuộc "có đang mở dự án không". */
function refreshDuAnUI() {
    const coDuAn = !!state.duAn;
    // Thanh công cụ thư viện: tìm/lọc/ghép/XOÁ/nhập chỉ đúng với thư viện chung.
    // Để hiện khi đang mở dự án là bấm vào sẽ thao tác lên lựa chọn ẩn của thư
    // viện chung — nút Xoá còn xoá nhầm video người dùng không nhìn thấy.
    document.querySelectorAll('.chi-thu-vien').forEach((el) => { el.style.display = coDuAn ? 'none' : ''; });
    document.querySelectorAll('.chi-du-an').forEach((el) => { el.style.display = coDuAn ? '' : 'none'; });
    $('btnDuAnHoanTac').style.display = coDuAn ? '' : 'none';
    $('bqDichDuAn').style.display = coDuAn ? '' : 'none';
    $('bqDichThuVien').style.display = coDuAn ? 'none' : '';
    if (coDuAn) $('bqDuAnTen').textContent = state.duAn.name || state.duAn.folder;
    const vaoDuAn = !!duAnDichCuaLo();
    // Vào dự án thì file trên máy LUÔN được chép — ô "chép vào thư viện" vô nghĩa.
    const oChep = $('bqCopyFile').closest('label');
    if (oChep) oChep.style.display = vaoDuAn ? 'none' : '';
    $('bqMergeName').placeholder = vaoDuAn
        ? 'Để trống = tên dự án (lưu trong ban_ghep/)' : 'Để trống = ghep_ngày_giờ';
}

/** Mở thư mục dự án (kind: '' | 'da_sub' | 'phu_de' | 'ban_ghep') bằng File Explorer. */
function moThuMucCuaDuAn(kind = '') {
    if (!state.duAn) return;
    api(`/api/project/open-folder${kind ? `?kind=${kind}` : ''}`, {
        method: 'POST', body: JSON.stringify({ folder: state.duAn.folder }),
    }).catch((e) => toast(e.message, 'error'));
}

/** Về thư viện chung. `daQuen`: backend đã tự quên dự án (vd sau hoàn tác). */
async function dongDuAn(opts = {}) {
    if (!opts.daQuen) {
        try { await api('/api/project/close', { method: 'POST' }); }
        catch (e) { toast(e.message, 'error'); return; }
    }
    state.duAn = null;
    state.duAnChon = [];
    state.duAnVideos = [];
    refreshBuocTiepTheo();
    refreshDuAnUI();
    await loadDuAnGanDay();
    await loadLibrary();   // không còn dự án → thư viện chung
}

async function hoanTacDuAn() {
    if (!state.duAn) return;
    const ok = confirm(
        `Trả tên file về như trước khi tạo dự án "${state.duAn.name}" và bỏ đánh dấu dự án?\n\n`
        + 'Danh sách "đã ghép" sẽ mất theo. Phụ đề, bản đã sub và bản ghép vẫn nằm nguyên trên đĩa.');
    if (!ok) return;
    try {
        const res = await api('/api/project/undo-rename', {
            method: 'POST', body: JSON.stringify({ folder: state.duAn.folder }),
        });
        toast(`Đã trả lại tên cho ${res.so_da_tra_lai} video.`, 'success');
        await dongDuAn({ daQuen: true });
    } catch (e) { toast(e.message, 'error'); }
}

async function xacNhanDuAn(doiTen) {
    const ctx = state.duAnModal;
    if (!ctx) return;
    const ten = $('duAnTen').value.trim();
    try {
        let data;
        if (ctx.cheDo === 'tao') {
            if (!ten) { toast('Phải đặt tên dự án.', 'warn'); return; }
            data = await api('/api/project/create', {
                method: 'POST', body: JSON.stringify({ thu_muc_cha: ctx.folder, ten }),
            });
        } else {
            data = await api('/api/project/init', {
                method: 'POST',
                body: JSON.stringify({ folder: ctx.folder, name: ten, doi_ten: doiTen }),
            });
        }
        $('modalDuAn').classList.remove('open');
        await moDuAn(data.folder, { veTab: ctx.veTab });
        toast(`Đã mở dự án "${data.name}".`, 'success');
    } catch (e) { toast(e.message, 'error'); }
}

async function moDuAn(folder, opts = {}) {
    try {
        state.duAn = await api('/api/project/open', {
            method: 'POST', body: JSON.stringify({ folder }),
        });
    } catch (e) {
        toast(e.message, 'error');
        return;
    }
    state.duAnChon = [];
    refreshDuAnUI();
    await loadDuAnVideos();
    await loadDuAnGanDay();
    if (!opts.im_lang) goTab(opts.veTab || 'library');
}

async function loadDuAnGanDay() {
    let res;
    try { res = await api('/api/project/recent'); } catch (e) { return; }
    const select = $('duAnSelect');
    select.innerHTML = '<option value="">— Chưa mở dự án nào —</option>'
        + (res.gan_day || []).map((r) =>
            `<option value="${esc(r.folder)}">${esc(r.name || r.folder)}</option>`).join('');
    select.value = (state.duAn && state.duAn.folder) || res.hien_tai || '';
    // Mở lại app là vào thẳng dự án đang làm dở, không phải chọn lại.
    if (!state.duAn && res.hien_tai) moDuAn(res.hien_tai, { im_lang: true });
}

async function loadDuAnVideos() {
    if (!state.duAn) { state.duAnVideos = []; renderLibrary(); return; }
    const url = `/api/project/videos?folder=${encodeURIComponent(state.duAn.folder)}`
        + `&ke_ca_da_ghep=${$('libHienDaGhep').checked}`;
    try {
        state.duAnVideos = await api(url);
    } catch (e) {
        state.duAnVideos = [];
        toast(e.message, 'error');
    }
    // Video biến mất khỏi danh sách thì cũng bỏ khỏi lựa chọn, không để chọn ma.
    const con = new Set(state.duAnVideos.map((v) => v.file));
    state.duAnChon = state.duAnChon.filter((f) => con.has(f));
    renderLibrary();
}

/** Video đã chọn, theo ĐÚNG thứ tự người dùng sắp (không phải thứ tự đánh số). */
function duAnVideoDaChon() {
    return state.duAnChon
        .map((f) => state.duAnVideos.find((v) => v.file === f))
        .filter(Boolean);
}

function renderDuAnLibrary() {
    const chon = state.duAnChon;
    const rows = state.duAnVideos.map((v) => {
        const thuTu = chon.indexOf(v.file);
        const daChon = thuTu >= 0;
        return `
        <div class="lib-card">
            <label class="lib-head">
                <input type="checkbox" class="duan-check" data-file="${esc(v.file)}" ${daChon ? 'checked' : ''}>
                <span class="list-main">
                    <b>${daChon ? `<span class="ok">[${thuTu + 1}]</span> ` : ''}${esc(v.file)}</b>
                    <small>
                        ${v.exists ? human(v.size) : '<b class="bad">thiếu file trên đĩa</b>'}
                        ${v.merged_into ? ` · <b class="ok">đã ghép vào ${esc(v.merged_into)}</b>` : ''}
                    </small>
                    ${v.ten_goc && v.ten_goc !== v.file
                        ? `<small class="dim">tên cũ: ${esc(v.ten_goc)}</small>` : ''}
                </span>
            </label>
            <div class="lib-actions">
                ${daChon ? `
                    <button class="btn btn-secondary btn-sm" data-act="duan-up" data-file="${esc(v.file)}">▲</button>
                    <button class="btn btn-secondary btn-sm" data-act="duan-down" data-file="${esc(v.file)}">▼</button>` : ''}
            </div>
        </div>`;
    }).join('');

    $('libList').innerHTML = rows || '<p class="help-text" style="text-align:center;">'
        + 'Dự án chưa có video nào. Tải video về ở tab <b>Lô Video</b>.</p>';
    $('libDuAnTomTat').innerHTML = state.duAnVideos.length
        ? `Đã chọn <b>${chon.length}</b>/${state.duAnVideos.length} video`
          + (chon.length ? ' — thứ tự trên đây cũng là thứ tự ghép.' : ' — chọn video để đi tiếp.')
        : '';
    refreshBuocTiepTheo();
    // Tab Dịch hiển thị đúng danh sách này — chọn/bỏ/sắp lại ở đây phải khớp ngay bên đó.
    renderTranslateSelection();
}

/** Bước tinh chỉnh tham số chỉ mở ra khi đã chọn xong và sắp xong thứ tự. */
function refreshBuocTiepTheo() {
    const box = $('libDuAnBuoc');
    if (!box) return;
    box.style.display = state.duAn && state.duAnVideos.length ? 'flex' : 'none';
    const nut = $('btnDuAnTinhChinh');
    const coChon = state.duAnChon.length > 0;
    nut.disabled = !coChon;
    nut.style.opacity = coChon ? '' : '.5';
    nut.title = coChon ? '' : 'Chọn ít nhất một video trước đã';
}

function human(bytes) {
    const n = Number(bytes || 0);
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    if (n < 1024 ** 3) return `${(n / 1024 / 1024).toFixed(1)} MB`;
    return `${(n / 1024 ** 3).toFixed(1)} GB`;
}

/* -------------------------------------------------------------- Thư viện */
async function loadLibrary() {
    // Đang mở dự án thì thư viện lấy từ thư mục dự án, không phải từ storage.
    if (state.duAn) { await loadDuAnVideos(); loadStats(); return; }
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
    // Có dự án đang mở thì thư viện CHÍNH LÀ danh sách video của dự án đó —
    // chọn và sắp thứ tự ngay tại đây rồi mới sang bước tinh chỉnh tham số.
    if (state.duAn) { renderDuAnLibrary(); return; }

    $('libDuAnTomTat').innerHTML = '';
    const items = filteredLibrary();
    if (!items.length) {
        $('libList').innerHTML = '<p class="help-text" style="text-align:center;">'
            + 'Chưa có video nào. Sang tab <b>Lô Video</b> để chọn file/dán link, '
            + 'hoặc nhập video có sẵn bằng nút ở trên.</p>';
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
                    ${v.batch_id ? `<small class="dim">📦 Lô ${esc(batchLabel(v.batch_id))}`
                        + ` · thứ tự ${esc(String(v.batch_index || 0))}</small>` : ''}
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
    const box = $('trSelected');
    const ghep = $('trDuAnGhep');
    // Đang mở dự án: tab Dịch chạy ĐÚNG các video đã chọn ở thư viện dự án, theo
    // thứ tự đã sắp. Trước đây tab này luôn đọc lựa chọn của thư viện cũ
    // (storage/videos) nên chọn xong trong dự án vẫn báo "Chưa chọn video nào".
    if (state.duAn) {
        const ds = duAnVideoDaChon();
        if (ghep) ghep.style.display = ds.length > 1 ? '' : 'none';
        if (!ds.length) {
            box.innerHTML = '<p class="help-text" style="text-align:center;">'
                + `Chưa chọn video nào — sang tab Thư Viện (dự án <b>${esc(state.duAn.name || '')}</b>) và tích chọn.</p>`;
            return;
        }
        box.innerHTML = ds.map((v, i) => `
            <div class="list-row">
                <span class="list-main"><b><span class="ok">[${i + 1}]</span> ${esc(v.file)}</b>
                    <small>${v.exists ? human(v.size) : '<b class="bad">thiếu file trên đĩa</b>'}</small></span>
                <button type="button" class="btn btn-secondary btn-sm" data-act="duan-unselect" data-file="${esc(v.file)}">bỏ</button>
            </div>`).join('');
        return;
    }
    if (ghep) ghep.style.display = 'none';
    const ids = libSelectionIds();
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
    let url, payload;
    if (state.duAn) {
        const files = state.duAnChon.slice();
        if (!files.length) { toast('Chưa chọn video nào để dịch.', 'warn'); goTab('library'); return; }
        url = '/api/project/translate';
        payload = {
            folder: state.duAn.folder, files, ...translateParams(),
            merge_after: {
                enabled: files.length > 1 && $('trDuAnGhepBat').checked,
                output_name: $('trDuAnGhepTen').value.trim(),
                prefer: 'output', normalize: true,
            },
        };
    } else {
        const ids = libSelectionIds();
        if (!ids.length) { toast('Chưa chọn video nào để dịch.', 'warn'); goTab('library'); return; }
        url = '/api/translate/start';
        payload = { entry_ids: ids, ...translateParams() };
    }
    $('logConsole-translate').innerHTML = '';
    try {
        const res = await api(url, { method: 'POST', body: JSON.stringify(payload) });
        setRunning(TASKS.translate, true);
        streamLogs(TASKS.translate, 'logConsole-translate', loadLibrary);
        toast(`Đã đưa ${res.count} video vào hàng đợi dịch.`, 'success');
    } catch (e) { toast(e.message, 'error'); }
}

async function prepareRoi() {
    let nguon;
    if (state.duAn) {
        const dau = duAnVideoDaChon()[0];
        if (!dau) { toast('Chọn một video ở tab Thư Viện trước đã.', 'warn'); return; }
        nguon = { video_path: dau.path };
    } else {
        const ids = libSelectionIds();
        if (!ids.length) { toast('Chọn một video ở tab Thư Viện trước đã.', 'warn'); return; }
        nguon = { entry_id: ids[0] };
    }
    const btn = $('btnTrPrepare');
    btn.disabled = true; btn.textContent = '⏳ Đang lấy khung hình…';
    try {
        const data = await api('/api/autosub/prepare', {
            method: 'POST', body: JSON.stringify(nguon),
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
    refreshMergeSizeWarning();
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

/** Nhãn dễ đọc của một lô — lấy luôn nhãn server đã tính, chưa có thì hiện mã thô. */
function batchLabel(batchId) {
    const found = state.batches.find((b) => b.batch_id === batchId);
    return found ? found.name : batchId;
}

async function loadBatches() {
    try {
        state.batches = await api('/api/batches');
    } catch (e) { state.batches = []; }
    const select = $('mgBatchPick');
    if (!select) return;
    const current = select.value;
    select.innerHTML = '<option value="">— Chọn một lô đã chạy —</option>'
        + state.batches.map((b) =>
            `<option value="${esc(b.batch_id)}">${esc(b.name)} — ${b.count} video`
            + `${b.translated ? ` (${b.translated} đã dịch)` : ''}</option>`).join('');
    select.value = current;
}

async function loadBatchIntoMerge() {
    const batchId = $('mgBatchPick').value;
    if (!batchId) { toast('Chọn một lô trước đã.', 'warn'); return; }
    try {
        // Lấy từ API chứ không lọc state.library: thứ tự của lô nằm ở batch_index,
        // còn thư viện thì sắp theo "mới nhất trước" — lọc tay là ghép ngược.
        const entries = await api(`/api/batches/${encodeURIComponent(batchId)}`);
        state.mergeList = [];
        entries.forEach((v) => {
            const outputs = v.outputs || [];
            if (outputs.length) addToMerge(v.entry_id, 'output', outputs[outputs.length - 1].name);
            else addToMerge(v.entry_id, 'source', '');
        });
        toast(`Đã nạp ${state.mergeList.length} video của lô, đúng thứ tự.`, 'success');
    } catch (e) { toast(e.message, 'error'); }
}

/** Cảnh báo trước khi ghép nếu lô lẫn nhiều cỡ khác nhau. */
function refreshMergeSizeWarning() {
    const box = $('mgSizeWarn');
    if (!box) return;
    const sizes = state.mergeList.map((it) => {
        const entry = state.library.find((v) => v.entry_id === it.entry_id);
        return entry && entry.width ? `${entry.width}x${entry.height}` : '';
    }).filter(Boolean);
    const distinct = [...new Set(sizes)];
    if (distinct.length < 2) { box.style.display = 'none'; return; }
    box.style.display = '';
    box.textContent = `⚠️ Danh sách có ${distinct.length} cỡ khác nhau (${distinct.join(', ')}) — `
        + 'giữ ô "tự chuẩn hoá" được bật, không thì ffmpeg nối không nổi.';
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
                normalize: $('mgNormalize').checked,
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

    // --- Lô video
    $('btnPickFiles').addEventListener('click', () => pickFiles('files'));
    $('btnPickFolder').addEventListener('click', () => pickFiles('folder'));
    $('btnDlProbe').addEventListener('click', doProbe);
    $('formBatch').addEventListener('submit', (e) => { e.preventDefault(); runBatch(); });
    $('btnBatchStop').addEventListener('click', stopBatch);
    $('btnBqSortName').addEventListener('click', () => {
        state.batch.sort((a, b) => compareNatural(a.title || a.value, b.title || b.value));
        renderBatch();
    });
    $('btnBqReverse').addEventListener('click', () => { state.batch.reverse(); renderBatch(); });
    $('btnBqClear').addEventListener('click', () => { state.batch = []; renderBatch(); });
    $('bqDoMerge').addEventListener('change', refreshBatchVisibility);
    $('dlAutoTranslate').addEventListener('change', refreshBatchVisibility);
    $('btnBqMoreParams').addEventListener('click', () => goTab('translate'));
    $('bqList').addEventListener('click', (event) => {
        const el = event.target.closest('[data-act]');
        if (!el) return;
        const idx = Number(el.dataset.idx);
        if (el.dataset.act === 'bq-del') state.batch.splice(idx, 1);
        if (el.dataset.act === 'bq-up' && idx > 0) {
            [state.batch[idx - 1], state.batch[idx]] = [state.batch[idx], state.batch[idx - 1]];
        }
        if (el.dataset.act === 'bq-down' && idx < state.batch.length - 1) {
            [state.batch[idx + 1], state.batch[idx]] = [state.batch[idx], state.batch[idx + 1]];
        }
        renderBatch();
    });

    // --- Dự án
    $('btnDuAnMo').addEventListener('click', moThuMucDuAn);
    $('btnDuAnTao').addEventListener('click', taoDuAnMoi);
    $('duAnSelect').addEventListener('change', (event) => {
        if (event.target.value) moDuAn(event.target.value);
        else if (state.duAn) dongDuAn();   // "— Chưa mở dự án nào —" = về thư viện chung
    });
    $('btnDuAnHoanTac').addEventListener('click', hoanTacDuAn);
    $('btnLibMoDuAn').addEventListener('click', () => moThuMucCuaDuAn());
    $('bqVaoDuAn').addEventListener('change', refreshDuAnUI);
    $('btnBqTaoDuAn').addEventListener('click', () => taoDuAnMoi({ veTab: 'download' }));
    $('btnDuAnXacNhan').addEventListener('click', () => xacNhanDuAn(true));
    $('btnDuAnGiuTen').addEventListener('click', () => xacNhanDuAn(false));
    $('btnDuAnHuy').addEventListener('click', () => $('modalDuAn').classList.remove('open'));
    $('libHienDaGhep').addEventListener('change', loadDuAnVideos);
    $('btnDuAnTinhChinh').addEventListener('click', () => {
        if (!state.duAnChon.length) { toast('Chọn ít nhất một video trước đã.', 'warn'); return; }
        goTab('translate');
    });

    // --- Thư viện
    $('btnLibReload').addEventListener('click', loadLibrary);
    $('libSearch').addEventListener('input', renderLibrary);
    $('libFilter').addEventListener('change', renderLibrary);
    $('btnLibSelectAll').addEventListener('click', () => {
        if (state.duAn) {
            // Giữ thứ tự đã sắp của video đã chọn, thêm phần còn lại theo số thứ tự.
            state.duAnVideos.forEach((v) => {
                if (!state.duAnChon.includes(v.file)) state.duAnChon.push(v.file);
            });
            renderLibrary();
            return;
        }
        filteredLibrary().forEach((v) => state.selected.add(v.entry_id));
        renderLibrary(); renderTranslateSelection();
    });
    $('btnLibClearSel').addEventListener('click', () => {
        if (state.duAn) { state.duAnChon = []; renderLibrary(); return; }
        state.selected.clear(); renderLibrary(); renderTranslateSelection();
    });
    $('btnLibDelete').addEventListener('click', deleteSelected);
    $('btnLibTranslate').addEventListener('click', () => {
        const coChon = state.duAn ? state.duAnChon.length : state.selected.size;
        if (!coChon) { toast('Chưa chọn video nào.', 'warn'); return; }
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
        try {
            const picked = await api('/api/system/pick-files', {
                method: 'POST', body: JSON.stringify({ mode: 'files' }),
            });
            const paths = picked.paths || [];
            if (!paths.length) return;
            for (const path of paths) {
                await api('/api/videos/import', {
                    method: 'POST', body: JSON.stringify({ path, copy_file: false }),
                });
            }
            toast(`Đã thêm ${paths.length} video vào thư viện.`, 'success');
            loadLibrary();
        } catch (e) { toast(e.message, 'error'); }
    });

    $('libList').addEventListener('change', (event) => {
        const duAnCheck = event.target.closest('.duan-check');
        if (duAnCheck) {
            const file = duAnCheck.dataset.file;
            // Bỏ vào cuối danh sách chọn = thứ tự chọn chính là thứ tự ghép mặc định.
            if (duAnCheck.checked) state.duAnChon.push(file);
            else state.duAnChon = state.duAnChon.filter((f) => f !== file);
            renderLibrary();
            refreshBuocTiepTheo();
            return;
        }
        const check = event.target.closest('.lib-check');
        if (!check) return;
        if (check.checked) state.selected.add(check.dataset.id);
        else state.selected.delete(check.dataset.id);
        renderTranslateSelection();
    });

    $('libList').addEventListener('click', async (event) => {
        const el = event.target.closest('[data-act]');
        if (!el) return;

        // Sắp thứ tự video trong dự án — thứ tự này chính là thứ tự ghép.
        if (el.dataset.act === 'duan-up' || el.dataset.act === 'duan-down') {
            const i = state.duAnChon.indexOf(el.dataset.file);
            const j = el.dataset.act === 'duan-up' ? i - 1 : i + 1;
            if (i >= 0 && j >= 0 && j < state.duAnChon.length) {
                [state.duAnChon[i], state.duAnChon[j]] = [state.duAnChon[j], state.duAnChon[i]];
                renderLibrary();
            }
            return;
        }

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
        if (state.duAn) { moThuMucCuaDuAn('da_sub'); return; }
        const ids = libSelectionIds();
        if (!ids.length) { api('/api/system/open-folder?kind=videos', { method: 'POST' }); return; }
        api(`/api/videos/${encodeURIComponent(ids[0])}/open-folder?kind=output`, { method: 'POST' })
            .catch((e) => toast(e.message, 'error'));
    });
    $('trSelected').addEventListener('click', (event) => {
        const boDuAn = event.target.closest('[data-act="duan-unselect"]');
        if (boDuAn) {
            state.duAnChon = state.duAnChon.filter((f) => f !== boDuAn.dataset.file);
            renderLibrary();   // render cả thư viện dự án lẫn tab Dịch
            return;
        }
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
    $('btnMgLoadBatch').addEventListener('click', loadBatchIntoMerge);
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
    bindMirrors();
    initRoiPicker();
    try { await loadConfig(); } catch (e) { toast(`Không đọc được cấu hình: ${e.message}`, 'error'); }
    try { await loadUiSettings(); } catch (e) { /* lần đầu chưa có file */ }
    syncMirrors();
    refreshTranslateVisibility();
    refreshBatchVisibility();
    refreshDuAnUI();      // trạng thái "chưa mở dự án" cho tới khi loadDuAnGanDay mở lại
    renderBatch();
    loadOllamaModels();   // Ollama trả lời chậm vài giây — đừng chặn cả trang chờ nó
    loadGpu();
    loadDuAnGanDay();   // có dự án đang làm dở thì mở lại luôn
    loadLibrary();
    loadMerged();
    loadBatches();
    resumeRunningTasks();
});
