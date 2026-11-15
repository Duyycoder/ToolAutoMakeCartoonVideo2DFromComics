/* Bảng chỉnh màu — phần BỘ LỌC MÀU có sẵn (ảnh thu nhỏ áp đúng bộ lọc lên khung hình của clip) và LUT .cube. */
import { api, esc, toast } from './chung.js';
import { PRESET, hamMau, docCube } from './mau_nang_cao.js';

const CO_ANH = [72, 44];

/* Vẽ ảnh thu nhỏ của media `url` qua bộ lọc `preset` vào canvas. */
function veAnh(cv, anh, preset) {
    const g = cv.getContext('2d', { willReadFrequently: true });
    g.drawImage(anh, 0, 0, CO_ANH[0], CO_ANH[1]);
    const f = preset && hamMau({ preset });
    if (!f) return;
    const d = g.getImageData(0, 0, CO_ANH[0], CO_ANH[1]);
    for (let i = 0; i < d.data.length; i += 4) {
        const v = f([d.data[i] / 255, d.data[i + 1] / 255, d.data[i + 2] / 255]);
        d.data[i] = v[0] * 255; d.data[i + 1] = v[1] * 255; d.data[i + 2] = v[2] * 255;
    }
    g.putImageData(d, 0, 0);
}

export class BoLoc {
    /* `datMau(patch, nhan, gop)` ghi các khoá của mau (undefined = xoá khoá). */
    constructor(ctx, datMau) {
        this.ctx = ctx;
        this.datMau = datMau;
        this.dsLut = [];
        this.el = document.createElement('div');
        this.el.addEventListener('click', (e) => {
            const b = e.target.closest('[data-preset]');
            if (b) {
                const p = b.dataset.preset || undefined;
                this.datMau({ preset: p, preset_manh: p ? (this.mau.preset_manh ?? 100) : undefined }, p ? `Bộ lọc ${PRESET[p].ten}` : 'Bỏ bộ lọc');
            }
            if (e.target.closest('[data-nhap-lut]')) this._nhapLut();
        });
        this.el.addEventListener('input', (e) => {
            const k = e.target.dataset.manh;
            if (!k) return;
            e.target.nextElementSibling.textContent = e.target.value;
            this.datMau({ [k]: Number(e.target.value) }, 'Độ mạnh', `manh_${k}`);
        });
        this.el.addEventListener('change', (e) => {
            if (e.target.dataset.chonLut === undefined) return;
            const t = e.target.value || undefined;
            this.datMau({ lut: t, lut_manh: t ? (this.mau.lut_manh ?? 100) : undefined }, t ? `LUT ${t}` : 'Bỏ LUT');
        });
        this.taiLut();
    }

    async taiLut() {
        try {
            this.dsLut = (await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/lut`)).lut || [];
            if (this.mau) this.ve(this.mau, this.urlAnh);
        } catch (e) { /* server bận */ }
    }

    ve(mau, urlAnh) {
        this.mau = mau;
        this.urlAnh = urlAnh;
        const p = mau.preset || '';
        const o = (k, ten) => `<button class="dc-preset ${p === k ? 'bat' : ''}" data-preset="${k}"><canvas width="${CO_ANH[0]}" height="${CO_ANH[1]}"></canvas><span>${esc(ten)}</span></button>`;
        this.el.innerHTML = `<div class="dc-preset-luoi">${o('', 'Gốc')}${Object.entries(PRESET).map(([k, v]) => o(k, v.ten)).join('')}</div>
            ${p ? this._thanh('preset_manh', 'Độ mạnh bộ lọc', mau.preset_manh ?? 100) : ''}
            <div class="dc-hang" style="margin-top:10px">
                <label style="flex:1">LUT <select data-chon-lut>
                    <option value="">Không dùng</option>
                    ${this.dsLut.map((t) => `<option value="${esc(t)}" ${mau.lut === t ? 'selected' : ''}>${esc(t)}</option>`).join('')}
                </select></label>
                <button class="nut nut-nho" data-nhap-lut>＋ Nhập .cube</button>
            </div>
            ${mau.lut ? this._thanh('lut_manh', 'Độ mạnh LUT', mau.lut_manh ?? 100) : ''}`;
        if (!urlAnh) return;
        const anh = new Image();
        anh.onload = () => {
            for (const b of this.el.querySelectorAll('[data-preset]')) veAnh(b.querySelector('canvas'), anh, b.dataset.preset);
        };
        anh.src = urlAnh;
    }

    _thanh(k, ten, v) {
        return `<div class="dc-thanh"><span>${ten}</span><input type="range" data-manh="${k}" min="0" max="100" value="${v}"><b>${v}</b></div>`;
    }

    _nhapLut() {
        if (this.ctx.store.chiDoc) { toast('Cửa sổ này chỉ xem.', 'warn'); return; }
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.cube';
        input.onchange = async () => {
            const f = input.files && input.files[0];
            if (!f) return;
            try {
                const text = await f.text();
                docCube(text);   // báo lỗi sớm, khỏi gửi file hỏng lên
                const res = await fetch(`/api/du-an/${encodeURIComponent(this.ctx.id)}/lut?ten=${encodeURIComponent(f.name)}&phien=${encodeURIComponent(this.ctx.boLuu.phien)}`,
                    { method: 'POST', body: text, headers: { 'Content-Type': 'text/plain' } });
                const d = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(d.detail || `HTTP ${res.status}`);
                await this.taiLut();
                this.datMau({ lut: d.ten, lut_manh: 100 }, `LUT ${d.ten}`);
                toast(`Đã nhập LUT ${d.ten}.`, 'success', 2500);
            } catch (e) { toast(`Nhập LUT lỗi: ${e.message}`, 'error'); }
        };
        input.click();
    }
}
