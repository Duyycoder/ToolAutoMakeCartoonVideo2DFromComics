/* Bảng chỉnh màu — phần HSL: chọn một vùng màu (đỏ, cam, vàng…), chỉnh sắc độ / bão hoà / độ sáng riêng vùng đó. */
import { esc } from './chung.js';
import { VUNG_HSL } from './mau_nang_cao.js';

const TRUC = [['Sắc độ', 0], ['Bão hoà', 1], ['Độ sáng', 2]];

export class ChinhHsl {
    /* `datHsl(hslMoi, nhan, gop)` ghi mau.hsl (undefined = xoá). */
    constructor(datHsl) {
        this.datHsl = datHsl;
        this.vung = 'do';
        this.el = document.createElement('div');
        this.el.addEventListener('click', (e) => {
            const b = e.target.closest('[data-vung]');
            if (b) { this.vung = b.dataset.vung; this.ve(this.hsl); }
            if (e.target.closest('[data-hsl-dat-lai]')) this._ghi(null, 'Đặt lại HSL');
        });
        this.el.addEventListener('input', (e) => {
            const k = e.target.dataset.truc;
            if (k === undefined) return;
            e.target.nextElementSibling.textContent = e.target.value;
            const v = [...((this.hsl || {})[this.vung] || [0, 0, 0])];
            v[Number(k)] = Number(e.target.value);
            this._ghi(v, `HSL ${this.vung}`, `hsl_${this.vung}_${k}`);
        });
    }

    _ghi(v, nhan, gop) {
        const moi = { ...(this.hsl || {}) };
        if (v === null) Object.keys(moi).forEach((k) => delete moi[k]);
        else if (v.every((x) => !x)) delete moi[this.vung];
        else moi[this.vung] = v;
        this.hsl = moi;
        this.datHsl(Object.keys(moi).length ? moi : undefined, nhan, gop);
        if (v === null) this.ve(this.hsl);
    }

    ve(hsl) {
        this.hsl = hsl || {};
        const v = this.hsl[this.vung] || [0, 0, 0];
        this.el.innerHTML = `<div class="dc-hsl-vung">${VUNG_HSL.map(([k, , ten, mau]) => {
            const da = (this.hsl[k] || []).some(Boolean);
            return `<button data-vung="${k}" title="${esc(ten)}" class="${k === this.vung ? 'bat' : ''} ${da ? 'da-chinh' : ''}" style="--m:${mau}"></button>`;
        }).join('')}<button class="nut-icon nut-nho" data-hsl-dat-lai title="Đặt lại mọi vùng màu">↺</button></div>
            ${TRUC.map(([ten, i]) => `<div class="dc-thanh"><span>${ten}</span>
                <input type="range" data-truc="${i}" min="-100" max="100" value="${v[i]}"><b>${v[i]}</b></div>`).join('')}`;
    }
}
