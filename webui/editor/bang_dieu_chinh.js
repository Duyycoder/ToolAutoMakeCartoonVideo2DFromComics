/* Bảng Điều chỉnh màu của clip đang chọn:
   bộ lọc màu có sẵn + LUT (dc_bo_loc.js) · chỉnh cơ bản · đường cong (dc_duong_cong.js) · HSL (dc_hsl.js)
   · cải thiện hình ảnh (làm nét, khử nhiễu). Mọi thứ lưu trong clip.mau; kéo thanh trượt gộp thành một bước hoàn tác. */
import { esc, toast } from './chung.js';
import { tao } from './store.js';
import { opsThemLopPhu } from './bang_chu.js';
import { BoLoc } from './dc_bo_loc.js';
import { DuongCong } from './dc_duong_cong.js';
import { ChinhHsl } from './dc_hsl.js';

const T_TRUOT = [
    { k: 'sang', ten: 'Độ sáng', min: -100, max: 100 },
    { k: 'tuong_phan', ten: 'Tương phản', min: -100, max: 100 },
    { k: 'bao_hoa', ten: 'Bão hoà', min: -100, max: 100 },
    { k: 'nhiet', ten: 'Nhiệt màu', min: -100, max: 100 },
    { k: 'phoi_sang', ten: 'Phơi sáng', min: -100, max: 100 },
    { k: 'hue', ten: 'Hue', min: -180, max: 180 },
    { k: 'vibrance', ten: 'Vibrance', min: -100, max: 100 },
];
const T_CAI_THIEN = [
    { k: 'lam_net', ten: 'Làm nét (ảnh mờ, nhoè)', min: 0, max: 100 },
    { k: 'khu_nhieu', ten: 'Khử nhiễu hạt', min: 0, max: 100 },
];
const MUC = [['bo_loc', 'Bộ lọc màu'], ['co_ban', 'Chỉnh cơ bản'], ['cong', 'Đường cong'], ['hsl', 'HSL – từng vùng màu'],
    ['cai_thien', 'Cải thiện hình ảnh']];

export class BangDieuChinh {
    constructor(ctx) {
        this.ctx = ctx;
        this.dong = new Set(['cong', 'hsl']);
        this.el = document.createElement('div');
        this.el.style.cssText = 'display:flex;flex-direction:column;min-height:0;height:100%';
        this.el.innerHTML = `<div class="bang-dau"><h2>Điều chỉnh màu</h2>
            <button class="nut nut-nho" data-l="them-lop-dc" title="Thêm một lớp điều chỉnh tại đầu phát: màu và hiệu ứng của lớp này áp lên MỌI hình bên dưới trong khoảng thời gian của nó">＋ Lớp điều chỉnh</button></div><div class="bang-noi" data-khu="noi"></div>`;
        this.el.querySelector('[data-l=them-lop-dc]').addEventListener('click', () => {
            const { ops, clip } = opsThemLopPhu(this.tl, this.ctx.ui.dau_phat || 0, 5,
                (id, tr, bd, dai) => ({ id, track: tr, loai: 'dieu_chinh', bat_dau: bd, ket_thuc: Math.round((bd + dai) * 1000) / 1000, mau: {}, hieu_ung: [] }));
            if (this.ctx.sua('Thêm lớp điều chỉnh', ops)) { this.ctx.timeline.chonClip(clip.id); toast('Đã thêm lớp điều chỉnh — chỉnh màu ở đây hoặc thêm hiệu ứng ở bảng Hiệu ứng.', 'success', 4000); }
        });
        this.noi = this.el.querySelector('[data-khu=noi]');
        this.boLoc = new BoLoc(ctx, (p, nhan, gop) => this.datMau(p, nhan, gop));
        this.cong = new DuongCong((kenh, diem, xong) => {
            const cong = { ...((this._clipChon() || {}).mau || {}).cong };
            if (diem) cong[kenh] = diem; else delete cong[kenh];
            this.datMau({ cong: Object.keys(cong).length ? cong : undefined }, 'Đường cong', `cong_${kenh}`);
            if (!diem) this.cong.dat(cong);
        });
        this.hsl = new ChinhHsl((hsl, nhan, gop) => this.datMau({ hsl }, nhan, gop));

        this.noi.addEventListener('input', (e) => {
            const k = e.target.dataset.k;
            if (e.target.type !== 'range' || !k) return;
            const v = parseInt(e.target.value, 10);
            e.target.nextElementSibling.textContent = String(v);
            this.datMau({ [k]: v || undefined }, `Điều chỉnh ${k}`, `mau_${k}`);
        });
        this.noi.addEventListener('click', (e) => {
            const muc = e.target.closest('[data-muc-mau]');
            if (muc) {
                const k = muc.dataset.mucMau;
                if (this.dong.has(k)) this.dong.delete(k); else this.dong.add(k);
                this.ve();
                return;
            }
            const b = e.target.closest('button[data-btn]');
            if (!b) return;
            const hd = b.dataset.btn;
            if (hd === 'dat_lai_mot') this.datMau({ [b.dataset.k]: undefined }, 'Đặt lại');
            else if (hd === 'dat_lai_het') this.datLaiHet();
            else if (hd === 'ap_het') this.apChoMoiClip();
            else if (hd === 'tu_dong') this.datMau({ lam_net: 35, khu_nhieu: 25 }, 'Tự động cải thiện hình ảnh');
        });

        const veLai = () => {
            if (!this.el.isConnected || this.cong._dangKeo) return;
            const a = document.activeElement;
            if (a && this.el.contains(a) && ['INPUT', 'SELECT', 'TEXTAREA'].includes(a.tagName)) return;
            this.ve();
        };
        ctx.bus.on('chon', () => { if (this.el.isConnected) this.ve(); });
        ctx.bus.on('timeline', veLai);
    }

    get tl() { return this.ctx.store.timeline; }

    _clipChon() {
        if (this.ctx.ui.dang_chon.length !== 1) return null;
        const c = this.tl.clips.find((x) => x.id === this.ctx.ui.dang_chon[0]);
        return c && (c.loai === 'dieu_chinh' || (c.media && c.loai !== 'che_phu_de')) ? c : null;
    }

    _thanh(t, v) {
        return `<div class="dc-thanh"><span>${esc(t.ten)}</span>
            <input type="range" data-k="${t.k}" min="${t.min}" max="${t.max}" value="${v}"><b>${v}</b>
            <button class="nut-icon nut-nho" data-btn="dat_lai_mot" data-k="${t.k}" title="Đặt lại">↺</button></div>`;
    }

    ve() {
        const c = this._clipChon();
        if (!c) {
            this.noi.innerHTML = `<div class="goi-y">Chọn một clip video/ảnh trên timeline để điều chỉnh màu, hoặc bấm ＋ Lớp điều chỉnh để chỉnh màu cho mọi clip trong một khoảng thời gian.</div>`;
            return;
        }
        const mau = c.mau || {};
        const than = {
            co_ban: T_TRUOT.map((t) => this._thanh(t, mau[t.k] || 0)).join(''),
            cai_thien: T_CAI_THIEN.map((t) => this._thanh(t, mau[t.k] || 0)).join('')
                + '<button class="nut nut-nho" data-btn="tu_dong" style="width:100%;margin-top:4px">✨ Tự động cải thiện hình ảnh</button>'
                + '<div class="goi-y-nho">Xem trước gần đúng — bấm 🎯 Xem chính xác để thấy đúng như bản xuất.</div>',
        };
        this.noi.innerHTML = `<div style="padding:8px 12px">${MUC.map(([k, ten]) => `
            <div class="dc-muc"><button class="dc-muc-dau" data-muc-mau="${k}">${this.dong.has(k) ? '▸' : '▾'} ${ten}</button>
            <div class="dc-muc-than" data-than="${k}" ${this.dong.has(k) ? 'hidden' : ''}>${than[k] || ''}</div></div>`).join('')}
            <div style="margin-top:16px;display:flex;gap:8px">
                <button class="nut nut-nho" data-btn="dat_lai_het" style="flex:1">Đặt lại tất cả</button>
                <button class="nut nut-nho" data-btn="ap_het" style="flex:1">Áp cho mọi clip</button>
            </div></div>`;
        const gan = (k, el) => this.noi.querySelector(`[data-than=${k}]`).appendChild(el);
        const m = this.ctx.media.find((x) => x.id === c.media);
        gan('bo_loc', this.boLoc.el);
        this.boLoc.ve(mau, m && m.thumb ? `/api/du-an/${encodeURIComponent(this.ctx.id)}/media/${m.id}/thumb?v=${encodeURIComponent(m.nhap_luc || '')}` : '');
        gan('cong', this.cong.el);
        this.cong.dat(mau.cong);
        gan('hsl', this.hsl.el);
        this.hsl.ve(mau.hsl);
    }

    /* Ghi các khoá vào clip.mau (giá trị undefined = xoá khoá). */
    datMau(patch, nhan, gop) {
        const c = this._clipChon();
        if (!c) return;
        const moi = { ...(c.mau || {}) };
        for (const [k, v] of Object.entries(patch)) { if (v === undefined) delete moi[k]; else moi[k] = v; }
        if (JSON.stringify(moi) === JSON.stringify(c.mau || {})) return;
        this.ctx.sua(nhan, [tao.dat(this.tl, ['clips', { id: c.id }, 'mau'], moi)], gop ? { gop: `mau_${c.id}_${gop}` } : undefined);
        if (!gop) this.ve();
    }

    datLaiHet() {
        const c = this._clipChon();
        if (!c) return;
        this.ctx.sua('Đặt lại màu', [tao.dat(this.tl, ['clips', { id: c.id }, 'mau'], {})]);
        this.ve();
    }

    apChoMoiClip() {
        const c = this._clipChon();
        if (!c) return;
        const mau = c.mau || {};
        const ops = this.tl.clips.filter((x) => x.track === c.track && x.media && x.loai !== 'che_phu_de' && x.id !== c.id)
            .map((x) => tao.dat(this.tl, ['clips', { id: x.id }, 'mau'], JSON.parse(JSON.stringify(mau))));
        if (ops.length) {
            this.ctx.sua('Áp màu cho mọi clip trên track', ops);
            toast(`Đã áp dụng cho ${ops.length} clip.`);
        }
    }
}
