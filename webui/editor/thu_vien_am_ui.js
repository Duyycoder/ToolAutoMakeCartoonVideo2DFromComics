/* Thư viện âm thanh có sẵn (SFX + nhạc nền CC0, assets/thu_vien_am/) trong tab Âm thanh:
   tìm theo tên/nhóm/thẻ, nghe thử, bấm + để thêm vào đầu phát, hoặc kéo thả xuống timeline. */
import { api, esc, fmtThoiGian, toast } from './chung.js';

const TOI_DA = 150;          // dòng hiện một lần (danh sách vài trăm mục)
let danhMuc = null;

const boDau = (s) => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();

export class ThuVienAm {
    constructor(ctx) {
        this.ctx = ctx;
        this.loai = 'sfx';
        this.nhom = '';
        this.tim = '';
        this.dangNghe = null;
        this.audio = new Audio();
        this.audio.addEventListener('ended', () => this._datNghe(null));
        this.el = document.createElement('div');
        this.el.className = 'tv-am';
        this.el.innerHTML = `<div class="tv-am-tab">
                <button data-loai="sfx" class="bat">Sound effect</button><button data-loai="nhac">Nhạc nền</button></div>
            <div class="tv-am-loc"><input type="search" placeholder="Tìm: cười, vỗ tay, whoosh, boing…" data-tim>
                <select data-nhom></select></div>
            <div class="tv-am-ds" data-ds><div class="goi-y">Đang tải thư viện…</div></div>
            <div class="goi-y-nho">Toàn bộ CC0 — dùng tự do kể cả thương mại. Bấm ＋ để thêm ở đầu phát, hoặc kéo xuống timeline.</div>`;
        this.ds = this.el.querySelector('[data-ds]');
        this.el.addEventListener('click', (e) => {
            const tab = e.target.closest('[data-loai]');
            if (tab) { this.loai = tab.dataset.loai; this.nhom = ''; this.ve(); return; }
            const nghe = e.target.closest('[data-nghe]');
            if (nghe) { this._nghe(nghe.dataset.nghe); return; }
            const them = e.target.closest('[data-them]');
            if (them) { this.ctx.timeline.themTuThuVien(them.dataset.them); toast('Đang thêm vào timeline…'); }
        });
        this.el.querySelector('[data-tim]').addEventListener('input', (e) => { this.tim = e.target.value; this._veDs(); });
        this.el.querySelector('[data-nhom]').addEventListener('change', (e) => { this.nhom = e.target.value; this._veDs(); });
        this.ds.addEventListener('dragstart', (e) => {
            const d = e.target.closest('[data-tv]');
            if (!d) return;
            e.dataTransfer.setData('application/x-thu-vien-am', d.dataset.tv);
            e.dataTransfer.setData('application/x-loai-audio', '1');
            e.dataTransfer.effectAllowed = 'copy';
        });
    }

    async ve() {
        this.el.querySelectorAll('[data-loai]').forEach((b) => b.classList.toggle('bat', b.dataset.loai === this.loai));
        if (!danhMuc) {
            try { danhMuc = (await api('/api/thu-vien-am')).muc || []; } catch (e) { this.ds.innerHTML = `<div class="goi-y">${esc(e.message)}</div>`; return; }
            for (const m of danhMuc) m._tim = boDau([m.ten, m.nhom, m.mo_ta, ...(m.the || [])].join(' '));
        }
        const nhom = [...new Set(danhMuc.filter((m) => m.loai === this.loai).map((m) => m.nhom))];
        this.el.querySelector('[data-nhom]').innerHTML = `<option value="">Tất cả nhóm</option>`
            + nhom.map((n) => `<option ${n === this.nhom ? 'selected' : ''}>${esc(n)}</option>`).join('');
        this._veDs();
    }

    _veDs() {
        if (!danhMuc) return;
        const tu = boDau(this.tim).split(/\s+/).filter(Boolean);
        const ds = danhMuc.filter((m) => m.loai === this.loai && (!this.nhom || m.nhom === this.nhom)
            && tu.every((t) => m._tim.includes(t)));
        if (!ds.length) { this.ds.innerHTML = '<div class="goi-y">Không có âm thanh nào khớp.</div>'; return; }
        this.ds.innerHTML = ds.slice(0, TOI_DA).map((m) => `<div class="tv-am-muc" draggable="true" data-tv="${esc(m.id)}"
                title="${esc(m.mo_ta || m.ten)} — ${esc(m.tac_gia)} (${esc(m.giay_phep)})">
                <button class="nut-icon nut-nho" data-nghe="${esc(m.id)}">${this.dangNghe === m.id ? '■' : '▶'}</button>
                <span class="tv-am-ten">${esc(m.ten)}<small>${esc(m.nhom)}</small></span>
                <span class="tv-am-dai">${fmtThoiGian(m.thoi_luong)}</span>
                <button class="nut-icon nut-nho" data-them="${esc(m.id)}" title="Thêm ở đầu phát">＋</button></div>`).join('')
            + (ds.length > TOI_DA ? `<div class="goi-y-nho">Còn ${ds.length - TOI_DA} mục — gõ thêm để lọc.</div>` : '');
    }

    _nghe(id) {
        if (this.dangNghe === id) { this.audio.pause(); this._datNghe(null); return; }
        const m = danhMuc.find((x) => x.id === id);
        if (!m) return;
        this.audio.src = `/api/thu-vien-am/tep/${m.file.split('/').map(encodeURIComponent).join('/')}`;
        this.audio.play().catch((e) => toast(`Không phát được: ${e.message}`, 'warn'));
        this._datNghe(id);
    }

    _datNghe(id) {
        this.dangNghe = id;
        this.ds.querySelectorAll('[data-nghe]').forEach((b) => { b.textContent = b.dataset.nghe === id ? '■' : '▶'; });
    }

    dung() { this.audio.pause(); this._datNghe(null); }
}
