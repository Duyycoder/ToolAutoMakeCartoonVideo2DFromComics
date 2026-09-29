import { $, api, toast } from './chung.js';
import { veDieuKhien, bindDieuKhien } from './chon_giong.js';

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
            ttsVoiceEl.innerHTML = veDieuKhien(eng, curVal, 'cfgCg');
            bindDieuKhien(ttsVoiceEl, eng, lang, curVal, (val) => {
                setByPath(configData, 'autosub.tts_voice', val);
                setByPath(configData, `autosub.tts_voice_${eng}`, val);
            });
        };
        ttsEngineEl.addEventListener('change', updateVoiceUI);
        updateVoiceUI();
    }
}

async function saveAllSettings() {
    const cfg = JSON.parse(JSON.stringify(configData || {}));
    document.querySelectorAll('[data-cfg]').forEach((el) => {
        const value = readField(el);
        if (value !== null) setByPath(cfg, el.dataset.cfg, value);
    });

    const ui = JSON.parse(JSON.stringify(uiSettingsData || {}));
    document.querySelectorAll('[data-persist]').forEach((el) => {
        if (el.id) ui[el.id] = readField(el);
    });

    await api('/api/config', { method: 'POST', body: JSON.stringify(cfg) });
    await api('/api/ui-settings', { method: 'POST', body: JSON.stringify(ui) });
    
    configData = cfg;
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
    
    await loadOllamaModels();
    await loadGpu();
});
