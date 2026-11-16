/* Một bánh xe màu (Lift / Gamma / Gain / Offset): kéo chấm để đẩy màu, thanh trượt dưới là độ sáng.
   Giá trị [x, y, l]: x, y ∈ [-1, 1] (hướng + độ mạnh màu), l ∈ [-100, 100]. Nhấp đúp vào bánh xe = về giữa. */
import { vecMau } from './mau_nang_cao.js';

const R = 46;     // bán kính (px CSS)

export class BanhXeMau {
    /* doi(v, xong): gọi khi kéo (xong=false) và khi thả (xong=true). */
    constructor(ten, doi) {
        this.v = [0, 0, 0];
        this.doi = doi;
        this.el = document.createElement('div');
        this.el.className = 'banh-xe';
        this.el.innerHTML = `<div class="banh-xe-ten">${ten}</div><canvas width="${R * 4}" height="${R * 4}"></canvas>
            <input type="range" min="-100" max="100" value="0" title="Độ sáng"><div class="banh-xe-so"></div>`;
        this.cv = this.el.querySelector('canvas');
        this.cv.style.cssText = `width:${R * 2}px;height:${R * 2}px;touch-action:none;cursor:crosshair`;
        this.thanh = this.el.querySelector('input');
        this.so = this.el.querySelector('.banh-xe-so');
        const keo = (e) => {
            const b = this.cv.getBoundingClientRect();
            let x = ((e.clientX - b.left) / b.width) * 2 - 1, y = -(((e.clientY - b.top) / b.height) * 2 - 1);
            const r = Math.hypot(x, y);
            if (r > 1) { x /= r; y /= r; }
            this.v = [Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000, this.v[2]];
            this.ve();
            this.doi([...this.v], false);
        };
        this.cv.addEventListener('pointerdown', (e) => {
            this.cv.setPointerCapture(e.pointerId);
            this._keo = true;
            keo(e);
        });
        this.cv.addEventListener('pointermove', (e) => { if (this._keo) keo(e); });
        const tha = () => { if (this._keo) { this._keo = false; this.doi([...this.v], true); } };
        this.cv.addEventListener('pointerup', tha);
        this.cv.addEventListener('pointercancel', tha);
        this.cv.addEventListener('dblclick', () => { this.v = [0, 0, this.v[2]]; this.ve(); this.doi([...this.v], true); });
        this.thanh.addEventListener('input', () => { this.v = [this.v[0], this.v[1], Number(this.thanh.value)]; this.ve(); this.doi([...this.v], false); });
        this.thanh.addEventListener('change', () => this.doi([...this.v], true));
    }

    dat(v) {
        if (this._keo) return;
        this.v = Array.isArray(v) && v.length >= 3 ? v.map(Number) : [0, 0, 0];
        this.thanh.value = String(this.v[2]);
        this.ve();
    }

    ve() {
        const c = this.cv.getContext('2d'), s = this.cv.width, r = s / 2 - 4;
        c.clearRect(0, 0, s, s);
        const g = c.createConicGradient ? c.createConicGradient(0, s / 2, s / 2) : null;
        if (g) {
            // Màu quanh vành khớp vecMau: góc 0 (phải) = đỏ, ngược chiều kim đồng hồ (canvas y hướng xuống nên đảo dấu).
            for (let i = 0; i <= 12; i++) {
                const a = -i / 12 * 2 * Math.PI, d = vecMau(Math.cos(a), Math.sin(a));
                g.addColorStop(i / 12, `rgb(${d.map((x) => Math.round(128 + 190 * x)).join(',')})`);
            }
            c.fillStyle = g;
        } else c.fillStyle = '#777';
        c.beginPath(); c.arc(s / 2, s / 2, r, 0, 2 * Math.PI); c.fill();
        const rg = c.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, r);
        rg.addColorStop(0, 'rgba(128,128,128,1)'); rg.addColorStop(1, 'rgba(128,128,128,0)');
        c.fillStyle = rg; c.fill();
        c.strokeStyle = 'rgba(255,255,255,.35)'; c.lineWidth = 2;
        c.beginPath(); c.moveTo(s / 2 - 8, s / 2); c.lineTo(s / 2 + 8, s / 2); c.moveTo(s / 2, s / 2 - 8); c.lineTo(s / 2, s / 2 + 8); c.stroke();
        const px = s / 2 + this.v[0] * r, py = s / 2 - this.v[1] * r;
        c.fillStyle = '#fff'; c.strokeStyle = '#000'; c.lineWidth = 3;
        c.beginPath(); c.arc(px, py, 9, 0, 2 * Math.PI); c.fill(); c.stroke();
        const d = vecMau(this.v[0], this.v[1]);
        this.so.textContent = `R ${(d[0] * 100).toFixed(0)} · G ${(d[1] * 100).toFixed(0)} · B ${(d[2] * 100).toFixed(0)} · L ${this.v[2]}`;
    }
}
