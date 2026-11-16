/* Tab Âm thanh: hiệu ứng cho clip đang chọn (clip.hieu_ung_am → hieu_ung_am.py khi xuất, am_hieu_ung.js khi xem trước)
   + fade vào/ra (clip.am_vao/am_ra) + thư viện SFX/nhạc nền có sẵn (thu_vien_am_ui.js).
   Kéo thanh trượt gộp thành một bước hoàn tác. */
import { esc } from './chung.js';
import { tao } from './store.js';
import { ThuVienAm } from './thu_vien_am_ui.js';
import { CHI_KHI_XUAT } from './am_hieu_ung.js';

const GIONG = [
    ['goc', 'Gốc', {}], ['soc', '🐿 Sóc chuột', { cao_do: 7 }], ['tre', '🧒 Trẻ con', { cao_do: 4 }],
    ['tram', '🎙 Trầm', { cao_do: -4 }], ['quai', '👹 Quái vật', { cao_do: -8, vang: 25, phong: 'hang' }],
    ['robot', '🤖 Robot', { robot: true }], ['dt', '📞 Điện thoại', { loc_bang: 'dien_thoai' }],
    ['radio', '📻 Radio', { loc_bang: 'radio', nen: 50 }], ['loa', '📢 Loa phóng thanh', { loc_bang: 'loa', nen: 40 }],
    ['game', '👾 8-bit', { bit: 6 }], ['hang', '🕳 Hang động', { vang: 60, phong: 'hang' }],
    ['nha_tho', '⛪ Nhà thờ', { vang: 55, phong: 'nha_tho' }], ['vong', '🔁 Vọng xa', { doi: 55, doi_tre: 420 }],
];
const THANH = [
    ['cao_do', 'Cao độ (nửa cung)', -12, 12, 1], ['vang', 'Tiếng vang', 0, 100, 1], ['doi', 'Tiếng dội (echo)', 0, 100, 1],
    ['doi_tre', 'Khoảng dội (ms)', 80, 1000, 10], ['meo', 'Méo tiếng', 0, 100, 1], ['bit', 'Bitcrush (bit, 0 = tắt)', 0, 12, 1],
    ['rung', 'Rung (tremolo)', 0, 100, 1], ['rung_tan', 'Tốc độ rung (Hz)', 1, 20, 1], ['nen', 'Nén tiếng (compressor)', 0, 100, 1],
];
const MAC_DINH = { doi_tre: 350, rung_tan: 6 };
const PHONG = [['phong_nho', 'Phòng nhỏ'], ['phong_lon', 'Phòng lớn'], ['nha_tho', 'Nhà thờ'], ['hang', 'Hang động']];
const LOC = [['', 'Không'], ['dien_thoai', 'Điện thoại'], ['radio', 'Radio'], ['loa', 'Loa phóng thanh']];
const BAT = [['robot', 'Giọng robot'], ['dao_nguoc', 'Phát ngược'], ['chuan_hoa', 'Chuẩn hoá độ to (-16 LUFS)']];

export class BangAmThanh {
    constructor(ctx) {
        this.ctx = ctx;
        this.thuVien = new ThuVienAm(ctx);
        this.el = document.createElement('div');
        this.el.style.cssText = 'display:flex;flex-direction:column;min-height:0;height:100%';
        this.el.innerHTML = `<div class="bang-dau"><h2>Âm thanh</h2></div><div class="bang-noi" style="padding:8px 12px">
            <details class="dc-muc" open><summary class="dc-muc-dau">Hiệu ứng cho clip đang chọn</summary><div data-khu="hu"></div></details>
            <details class="dc-muc" open><summary class="dc-muc-dau">Thư viện SFX &amp; nhạc nền</summary><div data-khu="tv"></div></details></div>`;
        this.hu = this.el.querySelector('[data-khu=hu]');
        this.el.querySelector('[data-khu=tv]').appendChild(this.thuVien.el);
        this.hu.addEventListener('input', (e) => {
            const k = e.target.dataset.k;
            if (!k || e.target.type !== 'range') return;
            const v = Number(e.target.value);
            e.target.nextElementSibling.textContent = String(v);
            if (k === 'am_vao' || k === 'am_ra') this._datClip({ [k]: v || undefined }, 'Fade', k);
            else this._dat({ [k]: !MAC_DINH[k] && v === 0 ? undefined : v }, 'Hiệu ứng âm thanh', k);
        });
        this.hu.addEventListener('change', (e) => {
            const k = e.target.dataset.k;
            if (!k) return;
            if (e.target.type === 'checkbox') this._dat({ [k]: e.target.checked || undefined }, 'Hiệu ứng âm thanh');
            else if (e.target.tagName === 'SELECT') this._dat({ [k]: e.target.value || undefined }, 'Hiệu ứng âm thanh');
        });
        this.hu.addEventListener('click', (e) => {
            const g = e.target.closest('[data-giong]');
            if (g) {
                const [, ten, p] = GIONG.find((x) => x[0] === g.dataset.giong);
                this._dat(null, `Giọng ${ten}`, null, { ...p });
            }
            if (e.target.closest('[data-hd=dat-lai]')) this._dat(null, 'Bỏ hiệu ứng âm thanh', null, {});
        });
        const veLai = () => {
            if (!this.el.isConnected) return;
            const a = document.activeElement;
            if (a && this.hu.contains(a) && ['INPUT', 'SELECT'].includes(a.tagName)) return;
            this.veHieuUng();
        };
        ctx.bus.on('chon', () => { if (this.el.isConnected) this.veHieuUng(); });
        ctx.bus.on('timeline', veLai);
    }

    get tl() { return this.ctx.store.timeline; }

    _clip() {
        if (this.ctx.ui.dang_chon.length !== 1) return null;
        const c = this.tl.clips.find((x) => x.id === this.ctx.ui.dang_chon[0]);
        const m = c && c.media && this.ctx.media.find((x) => x.id === c.media);
        return m && (m.loai === 'audio' || (m.loai === 'video' && m.co_am_thanh !== false)) ? c : null;
    }

    ve() { this.veHieuUng(); this.thuVien.ve(); }

    veHieuUng() {
        const c = this._clip();
        if (!c) { this.hu.innerHTML = '<div class="goi-y">Chọn một clip âm thanh / video có tiếng trên timeline để thêm hiệu ứng.</div>'; return; }
        const h = c.hieu_ung_am || {};
        const thanh = ([k, ten, min, max, buoc], v) => `<div class="dc-thanh"><span>${ten}</span>
            <input type="range" data-k="${k}" min="${min}" max="${max}" step="${buoc}" value="${v}"><b>${v}</b></div>`;
        const chon = (k, ds) => `<select data-k="${k}">${ds.map(([v, t]) => `<option value="${v}" ${(h[k] || '') === v ? 'selected' : ''}>${t}</option>`).join('')}</select>`;
        const chiXuat = CHI_KHI_XUAT.filter((k) => h[k]);
        this.hu.innerHTML = `<div class="am-giong">${GIONG.map(([id, ten]) => `<button class="nut nut-nho" data-giong="${id}">${ten}</button>`).join('')}</div>
            ${THANH.map((t) => thanh(t, h[t[0]] ?? MAC_DINH[t[0]] ?? 0)).join('')}
            <div class="hang"><label>Phòng (vang)${chon('phong', PHONG)}</label><label>Lọc dải tần${chon('loc_bang', LOC)}</label></div>
            ${BAT.map(([k, t]) => `<label class="check"><input type="checkbox" data-k="${k}" ${h[k] ? 'checked' : ''}> ${t}</label>`).join('')}
            ${thanh(['am_vao', 'Fade vào (giây)', 0, 5, 0.1], c.am_vao || 0)}${thanh(['am_ra', 'Fade ra (giây)', 0, 5, 0.1], c.am_ra || 0)}
            ${chiXuat.length ? `<div class="goi-y-nho">⚠ ${esc(chiXuat.map((k) => ({ cao_do: 'cao độ', robot: 'robot', dao_nguoc: 'phát ngược', chuan_hoa: 'chuẩn hoá' })[k]).join(', '))}
                chỉ nghe được ở bản xuất — bấm 🎯 Xem chính xác để nghe thử.</div>` : ''}
            <button class="nut nut-nho" data-hd="dat-lai" style="width:100%;margin-top:6px">Bỏ hết hiệu ứng</button>`;
    }

    /* patch: ghi đè vài khoá (undefined = xoá); thay: thay cả bộ (chọn giọng mẫu). */
    _dat(patch, nhan, gop = null, thay = null) {
        const c = this._clip();
        if (!c) return;
        const moi = thay || { ...(c.hieu_ung_am || {}) };
        for (const [k, v] of Object.entries(patch || {})) { if (v === undefined) delete moi[k]; else moi[k] = v; }
        if (JSON.stringify(moi) === JSON.stringify(c.hieu_ung_am || {})) return;
        this.ctx.sua(nhan, [tao.dat(this.tl, ['clips', { id: c.id }, 'hieu_ung_am'], moi)], gop ? { gop: `hua_${c.id}_${gop}` } : undefined);
        if (!gop) this.veHieuUng();
    }

    _datClip(patch, nhan, gop) {
        const c = this._clip();
        if (!c) return;
        const ops = Object.entries(patch).map(([k, v]) => tao.dat(this.tl, ['clips', { id: c.id }, k], v ?? 0));
        this.ctx.sua(nhan, ops, { gop: `hua_${c.id}_${gop}` });
    }
}
