/* Tiện ích dùng chung cho trang chủ và editor (ES module, không cần bước build). */

export const $ = (id) => document.getElementById(id);

export const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export class LoiApi extends Error {
    constructor(status, detail) {
        const msg = typeof detail === 'string' ? detail : (detail && detail.thong_diep) || JSON.stringify(detail);
        super(msg || `HTTP ${status}`);
        this.status = status;
        this.detail = detail;
    }
}

export async function api(path, options = {}) {
    const opts = { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } };
    if (opts.body && typeof opts.body !== 'string') opts.body = JSON.stringify(opts.body);
    const res = await fetch(path, opts);
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = text; }
    if (!res.ok) throw new LoiApi(res.status, (data && data.detail) || text || `HTTP ${res.status}`);
    return data;
}

export function toast(message, type = 'info', ms) {
    let box = $('toastBox');
    if (!box) {
        box = document.createElement('div');
        box.id = 'toastBox';
        box.className = 'toast-box';
        document.body.appendChild(box);
    }
    const item = document.createElement('div');
    item.className = `toast toast-${type}`;
    item.textContent = message;
    box.appendChild(item);
    setTimeout(() => item.remove(), ms || (type === 'error' ? 9000 : 4500));
    return item;
}

export function fmtThoiGian(sec, coKhung = false, fps = 30) {
    sec = Math.max(0, Number(sec) || 0);
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60);
    const pad = (n) => String(n).padStart(2, '0');
    let out = `${pad(h)}:${pad(m)}:${pad(s)}`;
    if (coKhung) out += `:${pad(Math.floor((sec % 1) * fps + 1e-6))}`;
    return out;
}

export function fmtNgan(sec) {
    sec = Math.round(Number(sec) || 0);
    if (!sec) return '';
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    return (h ? `${h}:${String(m).padStart(2, '0')}` : `${m}`) + `:${String(s).padStart(2, '0')}`;
}

export function truoc(iso) {
    if (!iso) return '';
    const giay = (Date.now() - new Date(iso).getTime()) / 1000;
    if (giay < 60) return 'vừa xong';
    if (giay < 3600) return `${Math.floor(giay / 60)} phút trước`;
    if (giay < 86400) return `${Math.floor(giay / 3600)} giờ trước`;
    if (giay < 86400 * 30) return `${Math.floor(giay / 86400)} ngày trước`;
    return new Date(iso).toLocaleDateString('vi-VN');
}

export function coFile(n) {
    n = Number(n) || 0;
    for (const u of ['B', 'KB', 'MB', 'GB']) {
        if (n < 1024 || u === 'GB') return u === 'B' ? `${n} B` : `${n.toFixed(1)} ${u}`;
        n /= 1024;
    }
    return '';
}

/* Hộp thoại nhỏ thay cho prompt()/confirm() (WebView2 hiện chúng rất xấu). */
export function hoi({ tieuDe, noiDung = '', html = '', o = null, nut = 'Đồng ý', huy = 'Huỷ', nguyHiem = false, themNut = '' }) {
    return new Promise((resolve) => {
        const nen = document.createElement('div');
        nen.className = 'modal-nen';
        nen.innerHTML = `<div class="modal" role="dialog" aria-modal="true">
            <h3>${esc(tieuDe)}</h3>
            ${noiDung ? `<p class="modal-noi-dung">${noiDung}</p>` : ''}
            ${html}
            ${o ? (o.nhieuDong
                ? `<textarea class="o-nhap" rows="${o.nhieuDong}" placeholder="${esc(o.goiY || '')}">${esc(o.giaTri || '')}</textarea>`
                : `<input class="o-nhap" type="text" value="${esc(o.giaTri || '')}" placeholder="${esc(o.goiY || '')}">`) : ''}
            <div class="modal-nut">
                ${themNut}
                ${huy ? `<button class="nut" data-kq="huy">${esc(huy)}</button>` : ''}
                <button class="nut ${nguyHiem ? 'nut-nguy' : 'nut-chinh'}" data-kq="ok">${esc(nut)}</button>
            </div></div>`;
        document.body.appendChild(nen);
        const input = nen.querySelector('.o-nhap');
        const xong = (kq_val) => {
            nen.remove();
            if (kq_val === 'ok') resolve(input ? input.value : true);
            else if (kq_val === 'huy' || kq_val === false) resolve(null);
            else resolve(kq_val); // for custom buttons
        };
        nen.addEventListener('click', (e) => {
            if (e.target === nen) xong(false);
            const kq = e.target.dataset && e.target.dataset.kq;
            if (kq) xong(kq);
        });
        nen.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') xong(false);
            if (e.key === 'Enter' && (!input || input.tagName !== 'TEXTAREA')) xong('ok');
        });
        (input || nen.querySelector('[data-kq=ok]')).focus();
        if (input && input.select) input.select();
    });
}

export async function chonFile(mode = 'media') {
    const r = await api('/api/system/pick-files', { method: 'POST', body: { mode } });
    if (mode === 'folder') return r.folder || '';
    return r.paths || [];
}

export function tiLe(rong, cao) {
    const g = (a, b) => (b ? g(b, a % b) : a);
    const k = g(rong, cao) || 1;
    return `${rong / k}:${cao / k}`;
}
