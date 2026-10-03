import { $, api, toast } from './chung.js';
import { veDieuKhien, bindDieuKhien } from './chon_giong.js';
import { choTrangThai, moHopCookie, pingGemini } from './gemini_cookie.js';

let configData = {};
let uiSettingsData = {};

function getByPath(obj, path) {
    return path.split('.').reduce((acc, part) => acc && acc[part] !== undefined ? acc[part] : undefined, obj);
}

function setByPath(obj, path, value) {
    const parts = path.split('.');
    let curr = obj;
    for (let i = 0; i < parts.length - 1; i++) {
        if (!curr[parts[i]]) curr[parts[i]] = {};
        curr = curr[parts[i]];
    }
    curr[parts[parts.length - 1]] = value;
}

function readField(el) {
    if (el.type === 'checkbox') return el.checked;
    if (el.type === 'number' || el.type === 'range') return el.value === '' ? null : Number(el.value);
    return el.value;
}

function writeField(el, value) {
    if (value === undefined || value === null) return;
    if (el.type === 'checkbox') el.checked = Boolean(value);
    else el.value = value;
}

async function loadConfig() {
    configData = await api('/api/config');
    document.querySelectorAll('[data-cfg]').forEach((el) => {
        writeField(el, getByPath(configData, el.dataset.cfg));
    });
    
    // Select correct option for Ollama model if we populated it
    const ollamaModelEl = $('cfgOllamaModel');
    if (ollamaModelEl && getByPath(configData, 'translate.ollama_model')) {
        ollamaModelEl.value = getByPath(configData, 'translate.ollama_model');
    }
    
    const ttsEngineEl = $('cfgTtsEngine');
    const ttsVoiceEl = $('cfgAiChonGiong');
    if (ttsEngineEl && ttsVoiceEl) {
        const updateVoiceUI = () => {
            const eng = ttsEngineEl.value || 'edge';
            const lang = getByPath(configData, 'translate.target_lang') || 'Vietnamese';
            const curVal = getByPath(configData, `autosub.tts_voice_${eng}`) || getByPath(configData, 'autosub.tts_voice') || '';
            ttsVoiceEl.innerHTML = veDieuKhien(eng, curVal, 'cfgCg',
                getByPath(configData, 'autosub.tts_speed') ?? 1.0, getByPath(configData, 'autosub.tts_pitch') ?? 0);
            // Ghi vào configData: saveAllSettings lấy configData làm gốc nên bấm Lưu là lưu cả giọng/tốc độ/cao độ.
            bindDieuKhien(ttsVoiceEl, eng, lang, curVal, (val) => {
                setByPath(configData, 'autosub.tts_voice', val);
                setByPath(configData, `autosub.tts_voice_${eng}`, val);
            }, (speed) => setByPath(configData, 'autosub.tts_speed', speed),
               (pitch) => setByPath(configData, 'autosub.tts_pitch', pitch));
        };
        ttsEngineEl.addEventListener('change', updateVoiceUI);
        updateVoiceUI();
    }
}

async function saveAllSettings() {
    const cfg = JSON.parse(JSON.stringify(configData || {}));
    document.querySelectorAll('[data-cfg]').forEach((el) => {
        // Ô chọn model chưa tải xong danh sách (rỗng) mà bấm Lưu thì giữ giá trị cũ, đừng ghi ''.
        if (el.tagName === 'SELECT' && !el.options.length) return;
        const value = readField(el);
        if (value !== null) setByPath(cfg, el.dataset.cfg, value);
    });

    const ui = JSON.parse(JSON.stringify(uiSettingsData || {}));
    document.querySelectorAll('[data-persist]').forEach((el) => {
        if (el.id) ui[el.id] = readField(el);
    });

    await api('/api/config', { method: 'POST', body: JSON.stringify(cfg) });
    await api('/api/ui-settings', { method: 'POST', body: JSON.stringify(ui) });

    const tr0 = configData.translate || {}, tr1 = cfg.translate || {};
    const doiCookie = tr0.gemini_psid !== tr1.gemini_psid || tr0.gemini_psidts !== tr1.gemini_psidts;
    configData = cfg;
    if (doiCookie) pingThu();  // server đã ghi cookies.json + bật lại proxy -> ping luôn
    uiSettingsData = ui;
    toast('Đã lưu cấu hình.', 'success');
}

async function loadOllamaModels() {
    try {
        const data = await api('/api/ollama/models');
        const names = data.models.map((m) => m.name);

        for (const [id, cfgPath] of [
            ['cfgOllamaModel', 'translate.ollama_model'],
            ['cfgMtModel', 'translate.mt_model'],
            ['cfgMtModelDuPhong', 'translate.mt_model_du_phong']
        ]) {
            const select = $(id);
            if (!select) continue;
            const wanted = getByPath(configData, cfgPath) || select.value;
            let currentNames = [...names];
            if (wanted && !currentNames.includes(wanted)) currentNames.unshift(wanted);
            
            select.innerHTML = currentNames.map(n => `<option value="${n}">${n}</option>`).join('');
            if (wanted) select.value = wanted;
        }
    } catch (e) { /* ignore */ }
}

const NHAN_GEMINI = {
    san_sang: '✅ đã kết nối', cookie_het_han: '⚠ cookie hết hạn', chua_co_cookie: 'chưa điền cookie',
    dang_khoi_dong: '⏳ đang kết nối...', loi: '❌ lỗi', khong_co_proxy: 'không có proxy',
    thieu_venv: '❌ thiếu .venv toolCaoTruyen', da_tat: 'chưa bật',
};

async function capNhatGemini() {
    const el = $('geminiTrangThai');
    if (!el) return;
    el.textContent = NHAN_GEMINI.dang_khoi_dong;
    try {
        const tt = await choTrangThai();
        el.textContent = NHAN_GEMINI[tt.ma] || tt.ma;
        el.title = tt.thong_bao || '';
    } catch (e) { el.textContent = e.message; }
}

async function pingThu() {
    const el = $('geminiTrangThai');
    const nut = $('btnGeminiPing');
    nut.disabled = true;
    el.textContent = '📡 đang ping...';
    try {
        const p = await pingGemini();
        el.textContent = p.ok ? `✅ chuẩn — trả lời "${p.tra_loi}" sau ${(p.ms / 1000).toFixed(1)}s` : `❌ ${p.thong_bao}`;
        el.title = p.thong_bao || '';
        toast(p.thong_bao, p.ok ? 'success' : 'error', 6000);
    } catch (e) {
        el.textContent = `❌ ${e.message}`;
    } finally {
        nut.disabled = false;
    }
}

async function loadGpu() {
    try {
        const gpu = await api('/api/system/gpu-info');
        $('gpuInfo').textContent = `🎮 ${gpu.name}${gpu.vram !== 'N/A' ? ' · ' + gpu.vram : ''}`;
    } catch (e) { /* ignore */ }
}

async function loadUiSettings() {
    try {
        uiSettingsData = await api('/api/ui-settings');
        document.querySelectorAll('[data-persist]').forEach((el) => {
            if (el.id && uiSettingsData[el.id] !== undefined) {
                writeField(el, uiSettingsData[el.id]);
            }
        });
    } catch (e) { /* ignore */ }
}

document.addEventListener('DOMContentLoaded', async () => {
    $('btnSaveSettings').addEventListener('click', () => saveAllSettings().catch((e) => toast(e.message, 'error')));
    
    try { await loadConfig(); } catch (e) { toast(`Lỗi cấu hình: ${e.message}`, 'error'); }
    try { await loadUiSettings(); } catch (e) {}
    
    $('btnGeminiHuongDan').addEventListener('click', async (e) => {
        e.preventDefault();
        if (!(await moHopCookie())) return;
        // Hộp thoại đã lưu cookie vào cấu hình -> chỉ nạp lại 2 ô đó (loadConfig sẽ gắn trùng sự kiện).
        const cfg = await api('/api/config').catch(() => null);
        if (!cfg) return;
        for (const k of ['gemini_psid', 'gemini_psidts', 'gemini_offline_key']) {
            setByPath(configData, `translate.${k}`, (cfg.translate || {})[k] || '');
            const el = document.querySelector(`[data-cfg="translate.${k}"]`);
            if (el) el.value = (cfg.translate || {})[k] || '';
        }
        capNhatGemini();
    });
    $('btnGeminiPing').addEventListener('click', (e) => { e.preventDefault(); pingThu(); });
    capNhatGemini();
    await loadOllamaModels();
    await loadGpu();
});

