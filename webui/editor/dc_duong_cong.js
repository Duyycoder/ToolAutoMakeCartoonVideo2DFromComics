/* Ô chỉnh đường cong (curves) — kéo bằng chuột hoặc ngón tay.
   - Chạm chỗ trống: thêm điểm và kéo luôn. Chạm hai lần vào một điểm: xoá điểm đó.
   - Hai điểm đầu/cuối chỉ kéo lên xuống. Điểm lưu thang 0..255 (giống mau_nang_cao.js). */
import { bangDuongCong } from './mau_nang_cao.js';

export const KENH_CONG = [['tong', 'RGB', '#ddd'], ['do', 'Đỏ', '#ef5350'], ['luc', 'Lục', '#66bb6a'], ['lam', 'Lam', '#42a5f5']];
const MAC_DINH = [[0, 0], [255, 255]];
const BAN_KINH = 14;

export class DuongCong {
    /* `doi(kenh, diem, xong)` được gọi khi kéo (xong=false) và khi thả (xong=true). */
    constructor(doi) {
        this.doi = doi;
        this.kenh = 'tong';
        this.cong = {};
        this.el = document.createElement('div');
        this.el.innerHTML = `<div class="dc-kenh">${KENH_CONG.map(([k, t, mau]) => `<button data-kenh="${k}" style="--m:${mau}">${t}</button>`).join('')}
            <button data-kenh-dat-lai title="Đặt lại kênh này">↺</button></div>
            <canvas class="dc-cong" width="256" height="256"></canvas>
            <div class="goi-y-nho">Chạm để thêm điểm, kéo để chỉnh, chạm 2 lần để xoá điểm.</div>`;
        this.cv = this.el.querySelector('canvas');
        this.el.addEventListener('click', (e) => {
            const b = e.target.closest('button');
            if (!b) return;
            if (b.hasAttribute('data-kenh-dat-lai')) { this.doi(this.kenh, null, true); return; }
            this.kenh = b.dataset.kenh;
            this.ve();
        });
        this._ganKeo();
    }

    dat(cong) { this.cong = cong || {}; this.ve(); }

    get diem() { return (this.cong[this.kenh] || MAC_DINH).map((p) => [...p]); }

    _toaDo(e) {
        const r = this.cv.getBoundingClientRect();
        return [Math.max(0, Math.min(255, (e.clientX - r.left) / r.width * 255)),
            Math.max(0, Math.min(255, 255 - (e.clientY - r.top) / r.height * 255))];
    }

    _ganKeo() {
        let keo = null, lanCham = { i: -1, t: 0 };
        this.cv.addEventListener('pointerdown', (e) => {
            e.preventDefault();
            this.cv.setPointerCapture(e.pointerId);
            const [x, y] = this._toaDo(e);
            const ds = this.diem;
            const r = this.cv.getBoundingClientRect(), tl = 255 / r.width;
            let i = ds.findIndex(([px, py]) => Math.hypot(px - x, py - y) < BAN_KINH * tl * 1.5);
            const bay = Date.now();
            if (i > 0 && i < ds.length - 1 && lanCham.i === i && bay - lanCham.t < 350) {
                ds.splice(i, 1);
                this.cong = { ...this.cong, [this.kenh]: ds };
                this.doi(this.kenh, ds, true);
                this.ve();
                lanCham = { i: -1, t: 0 };
                return;
            }
            if (i < 0) {
                const bang = bangDuongCong(ds);
                const yCong = bang ? bang[Math.round(x / 255 * 1024)] * 255 : x;
                ds.push([Math.round(x), Math.round(Math.abs(y - yCong) < 30 ? yCong : y)]);
                ds.sort((a, b) => a[0] - b[0]);
                i = ds.findIndex((p) => p[0] === Math.round(x));
            }
            lanCham = { i, t: bay };
            keo = { i, ds };
            this._dangKeo = true;
        });
        this.cv.addEventListener('pointermove', (e) => {
            if (!keo) return;
            const [x, y] = this._toaDo(e);
            const { ds, i } = keo;
            const dau = i === 0, cuoi = i === ds.length - 1;
            const xMin = dau ? 0 : ds[i - 1][0] + 1, xMax = cuoi ? 255 : ds[i + 1][0] - 1;
            ds[i] = [dau ? 0 : cuoi ? 255 : Math.round(Math.max(xMin, Math.min(xMax, x))), Math.round(y)];
            this.cong = { ...this.cong, [this.kenh]: ds.map((p) => [...p]) };
            this.ve();
            this.doi(this.kenh, this.cong[this.kenh], false);
        });
        const tha = () => {
            if (!keo) return;
            this.doi(this.kenh, this.cong[this.kenh] || keo.ds, true);
            keo = null;
            this._dangKeo = false;
        };
        this.cv.addEventListener('pointerup', tha);
        this.cv.addEventListener('pointercancel', tha);
    }

    ve() {
        for (const b of this.el.querySelectorAll('[data-kenh]')) b.classList.toggle('bat', b.dataset.kenh === this.kenh);
        const g = this.cv.getContext('2d'), W = 256;
        g.clearRect(0, 0, W, W);
        g.fillStyle = '#16181d';
        g.fillRect(0, 0, W, W);
        g.strokeStyle = 'rgba(255,255,255,.08)';
        g.lineWidth = 1;
        for (let i = 1; i < 4; i++) { g.beginPath(); g.moveTo(i * 64, 0); g.lineTo(i * 64, W); g.moveTo(0, i * 64); g.lineTo(W, i * 64); g.stroke(); }
        g.beginPath(); g.moveTo(0, W); g.lineTo(W, 0); g.stroke();
        // Các kênh khác mờ phía sau để thấy tổng thể.
        for (const [k, , mau] of KENH_CONG) {
            const ds = this.cong[k];
            if (!ds && k !== this.kenh) continue;
            const bang = bangDuongCong(ds || MAC_DINH);
            g.strokeStyle = mau;
            g.globalAlpha = k === this.kenh ? 1 : 0.35;
            g.lineWidth = k === this.kenh ? 2 : 1;
            g.beginPath();
            for (let x = 0; x <= 255; x++) {
                const y = bang ? bang[Math.round(x / 255 * 1024)] * 255 : x;
                if (x) g.lineTo(x, 255 - y); else g.moveTo(x, 255 - y);
            }
            g.stroke();
        }
        g.globalAlpha = 1;
        const mauKenh = KENH_CONG.find(([k]) => k === this.kenh)[2];
        for (const [x, y] of this.diem) {
            g.beginPath();
            g.arc(x, 255 - y, 5, 0, Math.PI * 2);
            g.fillStyle = '#111';
            g.fill();
            g.strokeStyle = mauKenh;
            g.lineWidth = 2;
            g.stroke();
        }
    }
}
