import { api, esc, chonFile } from './chung.js';

const voiceCache = {};

// Hàm thuần lấy giọng mặc định
export function layGiongMacDinh(engine, giongCu, dsGiong, lang) {
    if (engine === 'clone') return (giongCu === 'auto' || !giongCu || (typeof giongCu === 'string' && (giongCu.endsWith('.wav') || giongCu.endsWith('.mp3')))) ? (giongCu || 'auto') : 'auto';
    if (engine === 'vieneu') {
        const p = (giongCu || '').split('|');
        if (p[0] && dsGiong.includes(p[0])) return giongCu;
        return dsGiong.length ? `${dsGiong[0]}|v3turbo` : 'Ngọc Lan|v3turbo';
    }
    if (engine === 'piper' && dsGiong.length > 0) {
        const prefixMap = { 'vi': 'vi_', 'en': 'en_', 'ch': 'zh_' };
        const prefix = prefixMap[lang] || `${lang}_`;
        if (giongCu && dsGiong.includes(giongCu) && giongCu.toLowerCase().startsWith(prefix)) return giongCu;
        const matched = dsGiong.find(v => v.toLowerCase().startsWith(prefix));
        if (matched) return matched;
        if (giongCu && dsGiong.includes(giongCu)) return giongCu;
    }
    if (giongCu && dsGiong.includes(giongCu)) return giongCu;
    return dsGiong.length > 0 ? dsGiong[0] : '';
}

// Helper to construct the final tts_voice string from inputs
export function taoTtsVoice(engine, giong, cheDo, autoClone, fileMau) {
    if (engine === 'vieneu') return `${giong || 'Ngọc Lan'}|${cheDo || 'v3turbo'}`;
    if (engine === 'clone') return autoClone ? 'auto' : fileMau;
    return giong || '';
}

// Render HTML for the controls
export function veDieuKhien(engine, val, idPrefix = 'cg', speed = 1.0, pitch = 0) {
    let ttsVoice = val || '';
    let html = '';
    
    if (engine === 'vieneu') {
        const parts = ttsVoice.split('|');
        const v = parts[0] || '';
        const m = parts[1] || 'v3turbo';
        html = '<label>Tên giọng <select id="' + idPrefix + '_giong" class="cg-giong"></select></label>' +
               '<label>Chế độ <select id="' + idPrefix + '_chedo" class="cg-chedo">' +
               '<option value="v3turbo" ' + (m === 'v3turbo' ? 'selected' : '') + '>v3turbo</option>' +
               '<option value="standard" ' + (m === 'standard' ? 'selected' : '') + '>standard</option>' +
               '</select></label>';
    } else if (engine === 'clone') {
        const cleanVal = layGiongMacDinh(engine, ttsVoice, [], '');
        const auto = cleanVal === 'auto';
        const file = auto ? '' : cleanVal;
        html = '<label class="check"><input type="checkbox" id="' + idPrefix + '_auto" class="cg-auto" ' + (auto ? 'checked' : '') + '> Tự clone giọng nhân vật từ video gốc</label>' +
               '<label id="' + idPrefix + '_file_wrap" style="display: ' + (auto ? 'none' : 'block') + '">' +
               'File mẫu .wav <div style="display:flex;gap:5px"><input type="text" id="' + idPrefix + '_file" class="cg-file" value="' + esc(file) + '" placeholder="đường dẫn...">' +
               '<button type="button" class="nut cg-btn-file">📂</button></div></label>';
    } else {
        html = '<label>Tên giọng <select id="' + idPrefix + '_giong" class="cg-giong"></select></label>';
    }

    if (['edge', 'piper', 'clone'].includes(engine)) {
        html += '<label>Tốc độ <span id="' + idPrefix + '_speed_val" class="gt">' + speed + '</span>' +
                '<input type="range" id="' + idPrefix + '_speed" class="cg-speed" min="0.5" max="2.0" step="0.1" value="' + speed + '"></label>';
    }
    if (engine === 'edge') {
        html += '<label>Cao độ <span id="' + idPrefix + '_pitch_val" class="gt">' + pitch + '</span>' +
                '<input type="range" id="' + idPrefix + '_pitch" class="cg-pitch" min="-12" max="12" step="1" value="' + pitch + '"></label>';
    }
    
    return html;
}

// Bind events and load voices
export async function bindDieuKhien(container, engine, lang, currentVal, onChange) {
    const notify = () => {
        let giong = '', cheDo = '', autoClone = false, fileMau = '';
        const q = (sel) => container.querySelector(sel);
        if (engine === 'vieneu') {
            giong = q('.cg-giong') ? q('.cg-giong').value : '';
            cheDo = q('.cg-chedo') ? q('.cg-chedo').value : 'v3turbo';
        } else if (engine === 'clone') {
            autoClone = q('.cg-auto') ? q('.cg-auto').checked : true;
            fileMau = q('.cg-file') ? q('.cg-file').value : '';
        } else {
            giong = q('.cg-giong') ? q('.cg-giong').value : '';
        }
        onChange(taoTtsVoice(engine, giong, cheDo, autoClone, fileMau));
    };

    const giongSel = container.querySelector('.cg-giong');
    if (giongSel && ['edge', 'piper', 'kokoro', 'vieneu'].includes(engine)) {
        let voices = voiceCache[`${engine}_${lang}`];
        if (!voices) {
            try {
                const r = await api(`/api/tts/giong?engine=${engine}&lang=${lang}`);
                voices = r.giong || [];
                voiceCache[`${engine}_${lang}`] = voices;
            } catch (e) { voices = []; }
        }
        
        const validVal = layGiongMacDinh(engine, currentVal, voices, lang);
        if (validVal !== currentVal) onChange(validVal);
        
        let valToMatch = validVal || '';
        if (engine === 'vieneu') valToMatch = valToMatch.split('|')[0] || '';
        
        giongSel.innerHTML = voices.map(v => `<option value="${esc(v)}" ${v === valToMatch ? 'selected' : ''}>${esc(v)}</option>`).join('');
        
        giongSel.onchange = notify;
    } else if (engine === 'clone') {
        const validVal = layGiongMacDinh(engine, currentVal, [], lang);
        if (validVal !== currentVal) onChange(validVal);
    }
    
    const cheDoSel = container.querySelector('.cg-chedo');
    if (cheDoSel) cheDoSel.onchange = notify;
    
    const autoChk = container.querySelector('.cg-auto');
    if (autoChk) {
        autoChk.onchange = () => {
            const w = container.querySelector('[id$="_file_wrap"]');
            if (w) w.style.display = autoChk.checked ? 'none' : 'block';
            notify();
        };
    }
    
    const fileIn = container.querySelector('.cg-file');
    if (fileIn) fileIn.oninput = notify;
    
    const btnFile = container.querySelector('.cg-btn-file');
    if (btnFile) {
        btnFile.onclick = async () => {
            try {
                // In ui, chonFile might return an array for media
                const f = await chonFile('media');
                if (f && f.length) {
                    fileIn.value = f[0];
                    notify();
                }
            } catch (e) {}
        };
    }
}


