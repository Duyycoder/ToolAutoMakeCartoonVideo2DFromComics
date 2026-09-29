import { $, esc, toast } from './chung.js';
import { tao } from './store.js';

const T_TRUOT = [
    { k: 'sang', ten: 'Độ sáng', min: -100, max: 100 },
    { k: 'tuong_phan', ten: 'Tương phản', min: -100, max: 100 },
    { k: 'bao_hoa', ten: 'Bão hoà', min: -100, max: 100 },
    { k: 'nhiet', ten: 'Nhiệt màu', min: -100, max: 100 },
    { k: 'phoi_sang', ten: 'Phơi sáng', min: -100, max: 100 },
    { k: 'hue', ten: 'Hue', min: -180, max: 180 },
    { k: 'vibrance', ten: 'Vibrance', min: -100, max: 100 },
];

export class BangDieuChinh {
    constructor(ctx) {
        this.ctx = ctx;
        this.el = document.createElement('div');
        this.el.style.cssText = 'display:flex;flex-direction:column;min-height:0;height:100%';
        this.el.innerHTML = `<div class="bang-dau"><h2>Điều chỉnh màu</h2></div><div class="bang-noi" data-khu="noi"></div>`;
        this.noi = this.el.querySelector('[data-khu=noi]');
        
        this.noi.addEventListener('input', (e) => {
            if (e.target.type === 'range') {
                const k = e.target.dataset.k;
                const v = parseInt(e.target.value);
                e.target.nextElementSibling.textContent = String(v);
                this.apDungMau(k, v);
            }
        });
        
        this.noi.addEventListener('click', (e) => {
            const b = e.target.closest('button');
            if (!b) return;
            const action = b.dataset.btn;
            if (action === 'dat_lai_mot') {
                this.apDungMau(b.dataset.k, 0);
            } else if (action === 'dat_lai_het') {
                this.datLaiHet();
            } else if (action === 'ap_het') {
                this.apChoMoiClip();
            }
        });
        
        ctx.bus.on('chon', () => { if (this.el.isConnected) this.ve(); });
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

    ve() {
        const c = this._clipChon();
        if (!c) {
            this.noi.innerHTML = `<div class="goi-y">Chọn một clip video/ảnh trên timeline để điều chỉnh màu.</div>`;
            return;
        }
        
        const mau = c.mau || {};
        const html = T_TRUOT.map(t => {
            const v = mau[t.k] || 0;
            return `
                <div style="margin-bottom: 12px;">
                    <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;">
                        <span>${esc(t.ten)}</span>
                        <button class="nut-icon nut-nho" data-btn="dat_lai_mot" data-k="${t.k}" title="Đặt lại 0">↺</button>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <input type="range" data-k="${t.k}" min="${t.min}" max="${t.max}" value="${v}" style="flex:1;">
                        <span style="width:2em;text-align:right;font-size:12px;">${v}</span>
                    </div>
                </div>
            `;
        }).join('');
        
        this.noi.innerHTML = `
            <div style="padding: 12px;">
                ${html}
                <div style="margin-top: 20px; display:flex; gap: 8px;">
                    <button class="nut nut-nho" data-btn="dat_lai_het" style="flex:1;">Đặt lại tất cả</button>
                    <button class="nut nut-nho" data-btn="ap_het" style="flex:1;">Áp cho mọi clip</button>
                </div>
            </div>
        `;
    }
    
    apDungMau(k, v) {
        const c = this._clipChon();
        if (!c) return;
        const cu = c.mau || {};
        if (cu[k] === v) return;
        const moi = { ...cu, [k]: v };
        if (v === 0) delete moi[k];
        this.ctx.sua(`Điều chỉnh ${k}`, [tao.dat(this.tl, ['clips', { id: c.id }, 'mau'], moi)], { gop: `mau_${c.id}_${k}` });
    }
    
    datLaiHet() {
        const c = this._clipChon();
        if (!c) return;
        this.ctx.sua('Đặt lại màu', [tao.dat(this.tl, ['clips', { id: c.id }, 'mau'], {})]);
    }
    
    apChoMoiClip() {
        const c = this._clipChon();
        if (!c) return;
        const mau = c.mau || {};
        const ops = this.tl.clips.filter(x => x.track === c.track && x.media && x.loai !== 'che_phu_de' && x.id !== c.id)
            .map(x => tao.dat(this.tl, ['clips', { id: x.id }, 'mau'], JSON.parse(JSON.stringify(mau))));
        if (ops.length) {
            this.ctx.sua('Áp màu cho mọi clip trên track', ops);
            toast(`Đã áp dụng cho ${ops.length} clip.`);
        }
    }
}
