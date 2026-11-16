/* Tab Âm thanh — hiệu ứng ở 2 phạm vi:
     · RIÊNG: clip đang chọn (clip.hieu_ung_am, âm lượng, fade) — có nút áp cho mọi clip trên cùng track;
     · CHUNG: cả dự án (timeline.am_tong: hiệu ứng + âm lượng tổng, áp lên tiếng đã trộn — render._tieng_tong).
   Xuất: hieu_ung_am.py; xem trước: am_hieu_ung.js / am_xu_ly.js (datTong)
   + fade vào/ra (clip.am_vao/am_ra) + thư viện SFX/nhạc nền có sẵn (thu_vien_am_ui.js).
   Kéo thanh trượt gộp thành một bước hoàn tác. */
import { esc, toast } from './chung.js';
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
            <details class="dc-muc" open><summary class="dc-muc-dau">Hiệu ứng âm thanh</summary>
                <div class="tv-am-tab" data-khu="pham-vi"><button data-pv="clip">Riêng clip đang chọn</button><button data-pv="tong">Chung cả dự án</button></div>
                <div data-khu="hu"></div></details>
            <details class="dc-muc" open><summary class="dc-muc-dau">Thư viện SFX &amp; nhạc nền</summary><div data-khu="tv"></div></details></div>`;
        this.hu = this.el.querySelector('[data-khu=hu]');
        this.el.querySelector('[data-khu=pham-vi]').addEventListener('click', (e) => {
            const b = e.target.closest('[data-pv]');
            if (!b) return;
            ctx.ui.pham_vi_am = b.dataset.pv;
            ctx.luuUi();
            this.veHieuUng();
        });
        this.el.querySelector('[data-khu=tv]').appendChild(this.thuVien.el);
        this.hu.addEventListener('input', (e) => {
            const k = e.target.dataset.k;
            if (!k || e.target.type !== 'range') return;
            const v = Number(e.target.value);
            e.target.nextElementSibling.textContent = String(v);
            if (k === 'am_luong' && this._tong()) this._dat({ am_luong: v === 100 ? undefined : v / 100 }, 'Âm lượng tổng', k);
            else if (k === 'am_luong') this._datClip({ am_luong: v / 100 }, 'Âm lượng', k);
            else if (k === 'am_vao' || k === 'am_ra') this._datClip({ [k]: v || undefined }, 'Fade', k);
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
            if (e.target.closest('[data-hd=thuoc-tinh]')) this.ctx.bus.emit('mo_thuoc_tinh', 'am_thanh');
            if (e.target.closest('[data-hd=ca-track]')) this._apCaTrack();
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

    /* Clip đang sửa tiếng. Chọn clip có liên kết (tiếng tách từ video) là chọn CẢ NHÓM → ưu tiên clip trên track
       âm thanh, rồi clip vừa bấm; nhóm có nhiều clip âm thanh thì không đoán (trả null). */
    _clip() {
        const coTieng = (c) => {
            const m = c && c.media && this.ctx.media.find((x) => x.id === c.media);
            return !!m && (m.loai === 'audio' || (m.loai === 'video' && m.co_am_thanh !== false));
        };
        const ds = this.tl.clips.filter((x) => this.ctx.ui.dang_chon.includes(x.id) && coTieng(x));
        if (ds.length <= 1) return ds[0] || null;
        const am = ds.filter((c) => (this.tl.tracks.find((t) => t.id === c.track) || {}).loai === 'audio');
        if (am.length === 1) return am[0];
        if (ds.length === 2 && ds.every((c) => c.lien_ket && c.lien_ket === ds[0].lien_ket)) return ds.find((c) => c.id === this.ctx.chon.clip) || null;
        return null;
    }

    ve() { this.veHieuUng(); this.thuVien.ve(); }

    _tong() { return this.ctx.ui.pham_vi_am === 'tong'; }

    veHieuUng() {
        const tong = this._tong();
        this.el.querySelectorAll('[data-pv]').forEach((b) => b.classList.toggle('bat', (b.dataset.pv === 'tong') === tong));
        const c = tong ? null : this._clip();
        if (!tong && !c) { this.hu.innerHTML = '<div class="goi-y">Chọn một clip âm thanh / video có tiếng trên timeline — hoặc chọn "Chung cả dự án" để chỉnh toàn bộ tiếng.</div>'; return; }
        const h = (tong ? this.tl.am_tong : c.hieu_ung_am) || {};
        const thanh = ([k, ten, min, max, buoc], v) => `<div class="dc-thanh"><span>${ten}</span>
            <input type="range" data-k="${k}" min="${min}" max="${max}" step="${buoc}" value="${v}"><b>${v}</b></div>`;
        const chon = (k, ds) => `<select data-k="${k}">${ds.map(([v, t]) => `<option value="${v}" ${(h[k] || '') === v ? 'selected' : ''}>${t}</option>`).join('')}</select>`;
        const chiXuat = CHI_KHI_XUAT.filter((k) => h[k]);
        const dau = tong
            ? `<div class="goi-y-nho" style="margin:4px 0">Áp lên TOÀN BỘ tiếng của video sau khi trộn (mọi track) — vd nén + chuẩn hoá cho đều tiếng.</div>
               ${thanh(['am_luong', 'Âm lượng tổng (%)', 0, 200, 5], Math.round((h.am_luong ?? 1) * 100))}`
            : `${thanh(['am_luong', 'Âm lượng đoạn này (%)', 0, 200, 5], Math.round((c.am_luong ?? 1) * 100))}
               <div class="hang-nut" style="margin:-2px 0 6px"><button class="nut nut-nho" data-hd="thuoc-tinh">⚙ Thuộc tính đầy đủ (keyframe âm lượng, EQ…)</button>
               <button class="nut nut-nho" data-hd="ca-track">⇶ Áp hiệu ứng này cho cả track ${esc(c.track)}</button></div>`;
        this.hu.innerHTML = `${dau}
            <div class="am-giong">${GIONG.map(([id, ten]) => `<button class="nut nut-nho" data-giong="${id}">${ten}</button>`).join('')}</div>
            ${THANH.map((t) => thanh(t, h[t[0]] ?? MAC_DINH[t[0]] ?? 0)).join('')}
            <div class="hang"><label>Phòng (vang)${chon('phong', PHONG)}</label><label>Lọc dải tần${chon('loc_bang', LOC)}</label></div>
            ${BAT.map(([k, t]) => `<label class="check"><input type="checkbox" data-k="${k}" ${h[k] ? 'checked' : ''}> ${t}</label>`).join('')}
            ${tong ? '' : thanh(['am_vao', 'Fade vào (giây)', 0, 5, 0.1], c.am_vao || 0) + thanh(['am_ra', 'Fade ra (giây)', 0, 5, 0.1], c.am_ra || 0)}
            ${chiXuat.length ? `<div class="goi-y-nho">⚠ ${esc(chiXuat.map((k) => ({ cao_do: 'cao độ', robot: 'robot', dao_nguoc: 'phát ngược', chuan_hoa: 'chuẩn hoá' })[k]).join(', '))}
                chỉ nghe được ở bản xuất — bấm 🎯 Xem chính xác để nghe thử.</div>` : ''}
            <button class="nut nut-nho" data-hd="dat-lai" style="width:100%;margin-top:6px">Bỏ hết hiệu ứng</button>`;
    }

    /* patch: ghi đè vài khoá (undefined = xoá); thay: thay cả bộ (chọn giọng mẫu). */
    _dat(patch, nhan, gop = null, thay = null) {
        const tong = this._tong(), c = tong ? null : this._clip();
        if (!tong && !c) return;
        const cu = (tong ? this.tl.am_tong : c.hieu_ung_am) || {};
        const moi = thay ? { ...thay, ...(tong && cu.am_luong != null ? { am_luong: cu.am_luong } : {}) } : { ...cu };
        for (const [k, v] of Object.entries(patch || {})) { if (v === undefined) delete moi[k]; else moi[k] = v; }
        if (JSON.stringify(moi) === JSON.stringify(cu)) return;
        const duong = tong ? ['am_tong'] : ['clips', { id: c.id }, 'hieu_ung_am'];
        this.ctx.sua(tong ? `${nhan} (cả dự án)` : nhan, [tao.dat(this.tl, duong, moi)],
            gop ? { gop: `hua_${tong ? 'tong' : c.id}_${gop}` } : undefined);
        if (!gop) this.veHieuUng();
    }

    /* Chép hiệu ứng của clip đang chọn sang mọi clip khác trên cùng track — một bước hoàn tác. */
    _apCaTrack() {
        const c = this._clip();
        if (!c) return;
        const h = JSON.stringify(c.hieu_ung_am || {});
        const ops = this.tl.clips.filter((x) => x.track === c.track && x.id !== c.id && x.media)
            .map((x) => tao.dat(this.tl, ['clips', { id: x.id }, 'hieu_ung_am'], JSON.parse(h)));
        if (!ops.length) { toast('Track này chỉ có một clip.', 'info'); return; }
        this.ctx.sua(`Áp hiệu ứng âm thanh cho cả track ${c.track}`, ops);
        toast(`Đã áp cho ${ops.length} clip khác trên ${c.track}.`, 'success');
    }

    _datClip(patch, nhan, gop) {
        const c = this._clip();
        if (!c) return;
        const ops = Object.entries(patch).map(([k, v]) => tao.dat(this.tl, ['clips', { id: c.id }, k], v ?? 0));
        this.ctx.sua(nhan, ops, { gop: `hua_${c.id}_${gop}` });
    }
}
