import { $, esc } from './chung.js';
import { tao } from './store.js';
import { cssFilter } from './hieu_ung.js';

const C_HIEU_UNG = [
    { id: 'vintage', loai: 'vintage', ten: 'Vintage' },
    { id: 'noir', loai: 'noir', ten: 'Noir' },
    { id: 'cold', loai: 'cold', ten: 'Cold' },
    { id: 'warm', loai: 'warm', ten: 'Warm' },
    { id: 'dramatic', loai: 'dramatic', ten: 'Dramatic' },
    { id: 'faded', loai: 'faded', ten: 'Faded' },
    { id: 'sepia', loai: 'sepia', ten: 'Sepia' },
    { id: 'grayscale', loai: 'grayscale', ten: 'Đen trắng' },
    { id: 'invert', loai: 'invert', ten: 'Âm bản' },
    { id: 'mo_hop', loai: 'mo_hop', ten: 'Làm mờ Box' },
    { id: 'mo_gauss', loai: 'mo_gauss', ten: 'Làm mờ Gauss' },
    { id: 'mosaic', loai: 'mosaic', ten: 'Mosaic' },
];

export class BangHieuUng {
    constructor(ctx) {
        this.ctx = ctx;
        this.el = document.createElement('div');
        this.el.style.cssText = 'display:flex;flex-direction:column;min-height:0;height:100%';
        this.el.innerHTML = `<div class="bang-dau"><h2>Hiệu ứng</h2></div><div class="bang-noi" data-khu="noi" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 12px;"></div>`;
        this.noi = this.el.querySelector('[data-khu=noi]');
        
        this.noi.addEventListener('click', (e) => {
            const b = e.target.closest('.the-hieu-ung');
            if (b) this.themHieuUng(b.dataset.loai);
        });
        
        ctx.bus.on('chon', () => { if (this.el.isConnected) this.ve(true); });
        ctx.bus.on('timeline', () => { 
            if (this.el.isConnected) {
                if (document.activeElement && this.el.contains(document.activeElement) && ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
                this.ve(); 
            }
        });
    }
    
    get tl() { return this.ctx.store.timeline; }
    
    _clipChon() {
        if (this.ctx.ui.dang_chon.length !== 1) return null;
        const c = this.tl.clips.find(x => x.id === this.ctx.ui.dang_chon[0]);
        if (c && c.media && c.loai !== 'che_phu_de') return c;
        return null;
    }

    ve(ep = false) {
        const c = this._clipChon();
        if (!c) {
            this._cCu = null;
            this.noi.style.display = 'block';
            this.noi.innerHTML = `<div class="goi-y">Chọn một clip video/ảnh trên timeline để thêm hiệu ứng.</div>`;
            return;
        }
        if (!ep && this._cCu === c.id + c.media) return;
        this._cCu = c.id + c.media;
        
        this.noi.style.display = 'grid';
        const thumbUrl = `/api/du-an/${encodeURIComponent(this.ctx.id)}/media/${encodeURIComponent(c.media || '')}/thumb`;
        
        const html = C_HIEU_UNG.map(h => {
            const hu = [{ loai: h.loai, do_manh: 100, bat: true }];
            const f = cssFilter(null, hu);
            return `
                <div class="the-hieu-ung" data-loai="${h.loai}" style="cursor: pointer; border: 1px solid var(--vien); border-radius: 4px; overflow: hidden;">
                    <div style="height: 80px; background: url('${thumbUrl}') center/cover; filter: ${esc(f)};"></div>
                    <div style="padding: 4px; text-align: center; font-size: 12px; background: var(--nen-2);">${esc(h.ten)}</div>
                </div>
            `;
        }).join('');
        this.noi.innerHTML = html;
    }
    
    themHieuUng(loai) {
        const c = this._clipChon();
        if (!c) return;
        const huCu = c.hieu_ung || [];
        const so = huCu.reduce((max, h) => {
            const m = h.id.match(/^hu_(\d+)$/);
            return m ? Math.max(max, parseInt(m[1])) : max;
        }, 0);
        const id = `hu_${so + 1}`;
        const moi = [...huCu, { id, loai, do_manh: 100, bat: true }];
        this.ctx.sua(`Thêm hiệu ứng ${loai}`, [tao.dat(this.tl, ['clips', { id: c.id }, 'hieu_ung'], moi)]);
    }
}
