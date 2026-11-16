/* Tab Màu chuyên sâu: scopes (đo màu thật của khung đang xem), bánh xe Lift/Gamma/Gain/Offset, tông vùng
   Blacks/Shadows/Highlights/Whites, cân bằng trắng bằng ống hút, so sánh trước/sau chia đôi, sao chép/dán màu nhiều clip.
   Ghi vào clip.mau (can_trang, tong, banh_xe) → gộp vào LUT 3D như tab Màu (mau_nang_cao.py/.js). */
import { toast } from './chung.js';
import { tao } from './store.js';
import { BanhXeMau } from './banh_xe_mau.js';
import { BANH_XE, TONG } from './mau_nang_cao.js';
import { KIEU_SCOPE, layMau, veScope } from './scopes_mau.js';

const TEN_BX = { lift: 'Lift (vùng tối)', gamma: 'Gamma (trung tính)', gain: 'Gain (vùng sáng)', offset: 'Offset (toàn ảnh)' };
const TEN_TONG = { den: 'Blacks (đen)', toi: 'Shadows (tối)', sang: 'Highlights (sáng)', trang: 'Whites (trắng)' };
const KHOA_PRO = ['can_trang', 'tong', 'banh_xe'];
let banSao = null;          // màu đã sao chép (toàn bộ clip.mau)

export class BangMauPro {
    constructor(ctx) {
        this.ctx = ctx;
        this.kieu = 'waveform';
        this.el = document.createElement('div');
        this.el.style.cssText = 'display:flex;flex-direction:column;min-height:0;height:100%';
        this.el.innerHTML = `<div class="bang-dau"><h2>Màu chuyên sâu</h2></div><div class="bang-noi" style="padding:8px 12px">
            <div class="dc-muc"><div class="hang" style="align-items:center"><b style="flex:1">Scopes</b>
                <select data-kieu>${KIEU_SCOPE.map(([k, t]) => `<option value="${k}">${t}</option>`).join('')}</select></div>
                <canvas data-scope width="512" height="300" style="width:100%;border-radius:4px;background:#0b0b0d"></canvas></div>
            <div data-khu="than"></div></div>`;
        this.scope = this.el.querySelector('[data-scope]');
        this.than = this.el.querySelector('[data-khu=than]');
        this.el.querySelector('[data-kieu]').value = this.kieu;
        this.el.querySelector('[data-kieu]').addEventListener('change', (e) => { this.kieu = e.target.value; this._khoaScope = null; });
        this.banhXe = Object.fromEntries(BANH_XE.map((k) => [k, new BanhXeMau(TEN_BX[k], (v, xong) => this._datBx(k, v, xong))]));
        this.than.addEventListener('input', (e) => {
            const k = e.target.dataset.tong;
            if (k) { e.target.nextElementSibling.textContent = e.target.value; this._datTong(k, Number(e.target.value)); }
            if (e.target.dataset.ss !== undefined) this._soSanh();
        });
        this.than.addEventListener('change', (e) => { if (e.target.dataset.ss !== undefined) this._soSanh(); });
        this.than.addEventListener('click', (e) => {
            const b = e.target.closest('[data-hd]');
            if (b) this[`_hd_${b.dataset.hd}`]?.();
        });
        ctx.bus.on('chon', () => { if (this.el.isConnected) { this._tatSoSanh(); this.ve(); } });
        ctx.bus.on('timeline', () => {
            if (!this.el.isConnected) return;
            const a = document.activeElement;
            if (a && this.than.contains(a) && a.tagName === 'INPUT') return;
            this._capNhat();
        });
        setInterval(() => this._veScope(), 250);
    }

    get tl() { return this.ctx.store.timeline; }

    _clip() {
        if (this.ctx.ui.dang_chon.length !== 1) return null;
        const c = this.tl.clips.find((x) => x.id === this.ctx.ui.dang_chon[0]);
        return c && c.media && c.loai !== 'che_phu_de' ? c : null;
    }

    _cacClipChon() {
        return this.tl.clips.filter((x) => this.ctx.ui.dang_chon.includes(x.id) && x.media && x.loai !== 'che_phu_de');
    }

    ve() {
        const c = this._clip();
        this.than.innerHTML = `
            <div class="dc-muc"><b>Bánh xe màu</b> <span class="goi-y-nho">kéo chấm · nhấp đúp = về giữa · thanh dưới = độ sáng</span>
                <div class="banh-xe-luoi" data-bx></div></div>
            <div class="dc-muc"><b>Tông vùng sáng / tối</b>${TONG.map((k) => `<div class="dc-thanh"><span>${TEN_TONG[k]}</span>
                <input type="range" data-tong="${k}" min="-100" max="100" value="0"><b>0</b></div>`).join('')}</div>
            <div class="dc-muc"><b>Cân bằng trắng</b>
                <div class="hang-nut"><button class="nut nut-nho" data-hd="ong_hut">🎯 Ống hút: bấm vào vùng trắng/xám trên màn xem trước</button>
                <button class="nut-icon nut-nho" data-hd="bo_can_trang" title="Bỏ cân bằng trắng">↺</button></div>
                <div class="goi-y-nho" data-ct></div></div>
            <div class="dc-muc"><b>So sánh trước / sau</b>
                <label class="check"><input type="checkbox" data-ss> Chia đôi màn xem trước (trái: gốc · phải: đã chỉnh)</label>
                <input type="range" data-ss="x" min="5" max="95" value="50" style="width:100%"></div>
            <div class="dc-muc"><b>Áp màu cho nhiều clip</b>
                <div class="hang-nut" style="flex-wrap:wrap">
                <button class="nut nut-nho" data-hd="sao_chep">⧉ Sao chép màu</button>
                <button class="nut nut-nho" data-hd="dan">📋 Dán vào clip đang chọn</button>
                <button class="nut nut-nho" data-hd="ap_track">Áp cho cả track</button>
                <button class="nut nut-nho" data-hd="dat_lai">Đặt lại phần chuyên sâu</button></div>
                <div class="goi-y-nho">Sao chép/dán lấy TOÀN BỘ màu của clip (cả tab Màu). Chọn nhiều clip (Ctrl/Shift + bấm) rồi Dán để áp một lượt.</div></div>`;
        const luoi = this.than.querySelector('[data-bx]');
        for (const k of BANH_XE) luoi.appendChild(this.banhXe[k].el);
        this.than.querySelectorAll('[data-tong], [data-bx] input, [data-hd=ong_hut], [data-hd=bo_can_trang], [data-ss]')
            .forEach((x) => { x.disabled = !c; });
        luoi.style.opacity = c ? '' : '.45';
        this._capNhat();
    }

    _capNhat() {
        const c = this._clip(), mau = (c && c.mau) || {};
        for (const k of BANH_XE) this.banhXe[k].dat((mau.banh_xe || {})[k]);
        this.than.querySelectorAll('[data-tong]').forEach((x) => {
            const v = Number((mau.tong || {})[x.dataset.tong] || 0);
            x.value = String(v);
            x.nextElementSibling.textContent = String(v);
        });
        const ct = this.than.querySelector('[data-ct]');
        if (ct) ct.textContent = !c ? 'Chọn một clip video/ảnh để chỉnh.' : mau.can_trang
            ? `Đang nhân kênh R ${mau.can_trang[0].toFixed(2)} · G ${mau.can_trang[1].toFixed(2)} · B ${mau.can_trang[2].toFixed(2)}` : 'Chưa cân bằng trắng.';
        this._khoaScope = null;
    }

    _datMau(patch, nhan, gop) {
        const c = this._clip();
        if (!c) return;
        const moi = { ...(c.mau || {}) };
        for (const [k, v] of Object.entries(patch)) { if (v === undefined) delete moi[k]; else moi[k] = v; }
        if (JSON.stringify(moi) === JSON.stringify(c.mau || {})) return;
        this.ctx.sua(nhan, [tao.dat(this.tl, ['clips', { id: c.id }, 'mau'], moi)], gop ? { gop: `mpro_${c.id}_${gop}` } : undefined);
    }

    _datBx(k, v, xong) {
        const c = this._clip();
        if (!c) return;
        const bx = { ...((c.mau || {}).banh_xe || {}) };
        if (v.some(Boolean)) bx[k] = v; else delete bx[k];
        this._datMau({ banh_xe: Object.keys(bx).length ? bx : undefined }, `Bánh xe ${k}`, xong ? null : `bx_${k}`);
    }

    _datTong(k, v) {
        const c = this._clip();
        if (!c) return;
        const tg = { ...((c.mau || {}).tong || {}) };
        if (v) tg[k] = v; else delete tg[k];
        this._datMau({ tong: Object.keys(tg).length ? tg : undefined }, `Tông ${k}`, `tong_${k}`);
    }

    _hd_ong_hut() {
        const c = this._clip();
        if (!c) return;
        const man = this.ctx.preview.man;
        toast('Bấm vào một điểm lẽ ra phải trắng hoặc xám trên màn xem trước (Esc để huỷ).');
        man.style.cursor = 'crosshair';
        const xong = () => { man.style.cursor = ''; man.removeEventListener('pointerdown', bam, true); document.removeEventListener('keydown', esc_, true); };
        const esc_ = (e) => { if (e.key === 'Escape') xong(); };
        const bam = (e) => {
            e.preventDefault();
            e.stopPropagation();
            xong();
            const rgb = this.ctx.preview.layMauGoc(c.id, e.clientX, e.clientY);
            if (!rgb || Math.max(...rgb) < 0.04) { toast('Điểm này quá tối hoặc không nằm trên clip — thử vùng sáng hơn.', 'warn'); return; }
            const tb = (rgb[0] + rgb[1] + rgb[2]) / 3;
            const he = rgb.map((v) => Math.max(0.5, Math.min(2, tb / Math.max(v, 1e-3))));
            this._datMau({ can_trang: he.map((v) => Math.round(v * 1000) / 1000) }, 'Cân bằng trắng');
        };
        man.addEventListener('pointerdown', bam, true);
        document.addEventListener('keydown', esc_, true);
    }

    _hd_bo_can_trang() { this._datMau({ can_trang: undefined }, 'Bỏ cân bằng trắng'); }

    _hd_sao_chep() {
        const c = this._cacClipChon()[0];
        if (!c) { toast('Chọn clip cần sao chép màu.', 'warn'); return; }
        banSao = JSON.parse(JSON.stringify(c.mau || {}));
        toast('Đã sao chép màu của clip.');
    }

    _hd_dan() {
        if (!banSao) { toast('Chưa sao chép màu nào.', 'warn'); return; }
        const ds = this._cacClipChon();
        if (!ds.length) { toast('Chọn (các) clip cần dán màu.', 'warn'); return; }
        this.ctx.sua(`Dán màu cho ${ds.length} clip`, ds.map((x) => tao.dat(this.tl, ['clips', { id: x.id }, 'mau'], JSON.parse(JSON.stringify(banSao)))));
        toast(`Đã dán màu cho ${ds.length} clip.`);
    }

    _hd_ap_track() {
        const c = this._clip();
        if (!c) { toast('Chọn một clip làm mẫu.', 'warn'); return; }
        const ops = this.tl.clips.filter((x) => x.track === c.track && x.media && x.loai !== 'che_phu_de' && x.id !== c.id)
            .map((x) => tao.dat(this.tl, ['clips', { id: x.id }, 'mau'], JSON.parse(JSON.stringify(c.mau || {}))));
        if (ops.length) { this.ctx.sua(`Áp màu cho cả track ${c.track}`, ops); toast(`Đã áp cho ${ops.length} clip.`); }
    }

    _hd_dat_lai() { this._datMau(Object.fromEntries(KHOA_PRO.map((k) => [k, undefined])), 'Đặt lại màu chuyên sâu'); this._capNhat(); }

    _soSanh() {
        const c = this._clip(), bat = this.than.querySelector('[data-ss]:not([data-ss=x])');
        const x = Number(this.than.querySelector('[data-ss=x]').value) / 100;
        this.ctx.preview.datSoSanh(c && bat && bat.checked ? c.id : null, x);
    }

    _tatSoSanh() { if (this.ctx.preview?.soSanh) this.ctx.preview.datSoSanh(null); }

    _veScope() {
        if (!this.el.isConnected || document.hidden || !this.ctx.preview) return;
        const c = this._clip(), k = this.ctx.preview.khungChoScope(c && c.id);
        const n = k && k.nguon;
        const khoa = k ? [this.kieu, n.currentSrc || n.src, n.currentTime, JSON.stringify(k.mau), k.css, !!k.lut].join('|') : 'trong';
        if (khoa === this._khoaScope) return;
        this._khoaScope = khoa;
        veScope(this.scope, this.kieu, k ? layMau(n, k.mau, k.lut, k.css) : null);
    }
}
