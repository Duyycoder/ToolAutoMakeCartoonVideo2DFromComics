/* Thư viện âm thanh trong tab Âm thanh — 3 ngăn:
   - Sound effect / Nhạc nền: có sẵn (CC0, assets/thu_vien_am/) + CỦA TÔI (<workspace>/_thu_vien_am/, dùng mọi dự án).
   - Dự án: âm thanh đã nhập vào dự án này — nghe thử, thêm ở đầu phát, lưu vào thư viện của tôi, nhập file mới.
   Tìm theo tên/nhóm/thẻ, ▶ nghe thử, ＋ thêm ở đầu phát, hoặc kéo thả xuống timeline. */
import { api, esc, fmtThoiGian, hoi, moChonFile, toast } from './chung.js';
import { taiLenFile } from './tai_len.js';

const TOI_DA = 150;          // dòng hiện một lần (danh sách vài trăm mục)
const NGAN = [['sfx', 'Sound effect'], ['nhac', 'Nhạc nền'], ['du_an', 'Âm thanh dự án']];
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
        this.el.innerHTML = `<div class="tv-am-tab">${NGAN.map(([k, t]) => `<button data-loai="${k}">${t}</button>`).join('')}</div>
            <div class="tv-am-loc"><input type="search" placeholder="Tìm: cười, vỗ tay, whoosh, boing…" data-tim>
                <select data-nhom></select></div>
            <div class="hang-nut" data-nut-ngan style="margin-bottom:6px"></div>
            <div class="tv-am-ds" data-ds><div class="goi-y">Đang tải thư viện…</div></div>
            <div class="goi-y-nho" data-chu-thich></div>`;
        this.ds = this.el.querySelector('[data-ds]');
        this.el.addEventListener('click', (e) => {
            const b = e.target.closest('[data-loai],[data-nghe],[data-them],[data-xoa],[data-luu],[data-hd]');
            if (!b) return;
            if (b.dataset.loai) { this.loai = b.dataset.loai; this.nhom = ''; this.ve(); }
            else if (b.dataset.nghe) this._nghe(b.dataset.nghe);
            else if (b.dataset.them) this._them(b.dataset.them);
            else if (b.dataset.xoa) this._xoa(b.dataset.xoa);
            else if (b.dataset.luu) this._luuVaoThuVien(b.dataset.luu);
            else if (b.dataset.hd === 'nhap') this._nhapFile(false);
            else if (b.dataset.hd === 'nhap-tv') this._nhapFile(true);
        });
        this.el.querySelector('[data-tim]').addEventListener('input', (e) => { this.tim = e.target.value; this._veDs(); });
        this.el.querySelector('[data-nhom]').addEventListener('change', (e) => { this.nhom = e.target.value; this._veDs(); });
        this.ds.addEventListener('dragstart', (e) => {
            const d = e.target.closest('[data-tv],[data-mid]');
            if (!d) return;
            if (d.dataset.tv) e.dataTransfer.setData('application/x-thu-vien-am', d.dataset.tv);
            else e.dataTransfer.setData('application/x-media-id', d.dataset.mid);
            e.dataTransfer.setData('application/x-loai-audio', '1');
            e.dataTransfer.effectAllowed = 'copy';
        });
        ctx.bus.on('media', () => { if (this.el.isConnected && this.loai === 'du_an') this._veDs(); });
    }

    async _taiDanhMuc(lai = false) {
        if (danhMuc && !lai) return;
        danhMuc = (await api('/api/thu-vien-am')).muc || [];
        for (const m of danhMuc) m._tim = boDau([m.ten, m.nhom, m.mo_ta, ...(m.the || [])].join(' '));
    }

    async ve() {
        this.el.querySelectorAll('[data-loai]').forEach((b) => b.classList.toggle('bat', b.dataset.loai === this.loai));
        const duAn = this.loai === 'du_an';
        this.el.querySelector('[data-nut-ngan]').innerHTML = duAn
            ? '<button class="nut nut-nho" data-hd="nhap">📥 Nhập âm thanh vào dự án</button>'
            : `<button class="nut nut-nho" data-hd="nhap-tv">＋ Thêm ${this.loai === 'nhac' ? 'nhạc' : 'SFX'} của tôi vào thư viện</button>`;
        this.el.querySelector('[data-chu-thich]').textContent = duAn
            ? '⭐ = lưu vào thư viện của tôi để dùng ở mọi dự án. Kéo xuống timeline hoặc bấm ＋ để thêm ở đầu phát.'
            : 'Mục có sẵn là CC0 — dùng tự do kể cả thương mại. Nhóm "Của tôi" là âm thanh bạn tự thêm.';
        try { await this._taiDanhMuc(); } catch (e) { this.ds.innerHTML = `<div class="goi-y">${esc(e.message)}</div>`; return; }
        const dem = new Map();          // nhóm → số mục; "Của tôi" lên đầu, còn lại theo ABC
        if (!duAn) for (const m of danhMuc) if (m.loai === this.loai) dem.set(m.nhom, (dem.get(m.nhom) || 0) + 1);
        const nhom = [...dem.keys()].sort((a, b) => (b === 'Của tôi') - (a === 'Của tôi') || a.localeCompare(b, 'vi'));
        const chonNhom = this.el.querySelector('[data-nhom]');
        chonNhom.hidden = duAn;
        chonNhom.innerHTML = `<option value="">Tất cả nhóm</option>`
            + nhom.map((n) => `<option value="${esc(n)}" ${n === this.nhom ? 'selected' : ''}>${esc(n)} (${dem.get(n)})</option>`).join('');
        this._veDs();
    }

    _veDs() {
        if (!danhMuc) return;
        const tu = boDau(this.tim).split(/\s+/).filter(Boolean);
        const dong = (id, ten, phu, dai, them, tv) => `<div class="tv-am-muc" draggable="true" ${tv ? `data-tv="${esc(id)}"` : `data-mid="${esc(id)}"`}>
                <button class="nut-icon nut-nho" data-nghe="${esc(id)}">${this.dangNghe === id ? '■' : '▶'}</button>
                <span class="tv-am-ten">${esc(ten)}<small>${esc(phu)}</small></span>
                <span class="tv-am-dai">${fmtThoiGian(dai || 0)}</span>${them}
                <button class="nut-icon nut-nho" data-them="${esc(id)}" title="Thêm ở đầu phát">＋</button></div>`;
        let html;
        if (this.loai === 'du_an') {
            const coTieng = (m) => m.loai === 'audio' || (m.loai === 'video' && m.co_am_thanh !== false);
            const ds = this.ctx.media.filter((m) => coTieng(m) && m.trang_thai === 'san_sang' && tu.every((t) => boDau(m.ten).includes(t)))
                .sort((a, b) => (a.loai === 'audio' ? 0 : 1) - (b.loai === 'audio' ? 0 : 1));
            html = ds.map((m) => dong(m.id, m.ten, m.loai === 'audio' ? 'âm thanh' : 'tiếng của video', m.thoi_luong,
                `<button class="nut-icon nut-nho" data-luu="${esc(m.id)}" title="Lưu vào thư viện của tôi">⭐</button>`, false)).join('')
                || '<div class="goi-y">Dự án chưa có âm thanh — bấm 📥 Nhập âm thanh, hoặc trích tiếng từ video (bảng Thuộc tính).</div>';
        } else {
            const ds = danhMuc.filter((m) => m.loai === this.loai && (!this.nhom || m.nhom === this.nhom) && tu.every((t) => m._tim.includes(t)));
            html = ds.slice(0, TOI_DA).map((m) => dong(m.id, m.ten, m.nhom, m.thoi_luong,
                m.rieng ? `<button class="nut-icon nut-nho" data-xoa="${esc(m.id)}" title="Xoá khỏi thư viện của tôi">🗑</button>` : '', true)).join('')
                + (ds.length > TOI_DA ? `<div class="goi-y-nho">Còn ${ds.length - TOI_DA} mục — gõ thêm để lọc.</div>` : '')
                || '<div class="goi-y">Không có âm thanh nào khớp.</div>';
        }
        this.ds.innerHTML = html;
    }

    _url(id) {
        if (this.loai === 'du_an') return `/api/du-an/${encodeURIComponent(this.ctx.id)}/media/${encodeURIComponent(id)}/file`;
        const m = danhMuc.find((x) => x.id === id);
        return m && `/api/thu-vien-am/tep/${m.file.split('/').map(encodeURIComponent).join('/')}`;
    }

    _nghe(id) {
        if (this.dangNghe === id) { this.audio.pause(); this._datNghe(null); return; }
        const url = this._url(id);
        if (!url) return;
        this.audio.src = url;
        this.audio.play().catch((e) => toast(`Không phát được: ${e.message}`, 'warn'));
        this._datNghe(id);
    }

    _datNghe(id) {
        this.dangNghe = id;
        this.ds.querySelectorAll('[data-nghe]').forEach((b) => { b.textContent = b.dataset.nghe === id ? '■' : '▶'; });
    }

    _them(id) {
        if (this.loai === 'du_an') {
            const m = this.ctx.media.find((x) => x.id === id);
            if (m) this.ctx.timeline.themAmTaiDauPhat(m);
        } else {
            this.ctx.timeline.themTuThuVien(id);
            toast('Đang thêm vào timeline…');
        }
    }

    async _luuVaoThuVien(mid, loai = null) {
        const m = this.ctx.media.find((x) => x.id === mid);
        if (!m) return;
        if (!loai) {
            const kq = await hoi({ tieuDe: 'Lưu vào thư viện của tôi', nut: 'Là sound effect', huy: 'Huỷ',
                noiDung: `"${esc(m.ten)}" sẽ có trong thư viện ở mọi dự án (nhóm "Của tôi").`,
                themNut: '<button class="nut" data-kq="nhac">Là nhạc nền</button>' });
            if (!kq) return;
            loai = kq === 'nhac' ? 'nhac' : 'sfx';
        }
        try {
            await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/media/${encodeURIComponent(mid)}/vao-thu-vien`,
                { method: 'POST', body: { ten: m.ten, nhom: 'Của tôi', loai } });
            await this._taiDanhMuc(true);
            toast(`Đã lưu "${m.ten}" vào thư viện (${loai === 'nhac' ? 'Nhạc nền' : 'Sound effect'} › Của tôi).`, 'success');
            if (this.loai !== 'du_an') this.ve();
        } catch (e) { toast(e.message, 'error'); }
    }

    async _xoa(id) {
        const m = danhMuc.find((x) => x.id === id);
        if (!m || !(await hoi({ tieuDe: 'Xoá khỏi thư viện của tôi?', noiDung: `"${esc(m.ten)}" — clip đã đặt trong các dự án vẫn giữ nguyên.`, nut: 'Xoá', nguyHiem: true }))) return;
        try {
            await api(`/api/thu-vien-am/rieng/${encodeURIComponent(id)}`, { method: 'DELETE' });
            await this._taiDanhMuc(true);
            this.ve();
        } catch (e) { toast(e.message, 'error'); }
    }

    /* Nhập file âm thanh (cả video — lấy tiếng) vào dự án; vaoThuVien = lưu luôn vào thư viện của tôi theo ngăn đang mở. */
    async _nhapFile(vaoThuVien) {
        if (this.ctx.store.chiDoc) { toast('Cửa sổ này chỉ xem.', 'warn'); return; }
        const loai = this.loai;
        const files = await moChonFile({ accept: 'audio/*,video/*,.m4a,.mp3,.wav,.aac,.ogg,.flac,.caf,.amr', multiple: true });
        if (!files.length) return;
        const tb = toast(`Đang tải ${files.length} file…`, 'info', 24 * 3600 * 1000);
        let xong = 0;
        for (const [i, f] of files.entries()) {
            try {
                const ds = await taiLenFile(this.ctx.id, this.ctx.boLuu.phien, f, (pt) => { tb.textContent = `Đang tải ${i + 1}/${files.length}: ${f.name} — ${pt}%`; });
                this.ctx.bus.emit('media_can_tai');
                if (vaoThuVien && ds && ds[0]) await this._choRoiLuu(ds[0].id, loai);
                xong++;
            } catch (e) { toast(`${f.name}: ${e.message}`, 'error', 10000); }
        }
        tb.remove();
        if (xong) toast(vaoThuVien ? `Đã thêm ${xong} file vào thư viện của tôi.` : `Đã nhập ${xong} file vào dự án.`, 'success');
    }

    /* Media vừa tải còn đang đọc thông số → chờ sẵn sàng rồi mới lưu vào thư viện. */
    async _choRoiLuu(mid, loai) {
        for (let i = 0; i < 120; i++) {
            const m = this.ctx.media.find((x) => x.id === mid);
            if (m && m.trang_thai === 'san_sang') { await this._luuVaoThuVien(mid, loai); return; }
            if (m && m.trang_thai === 'loi') throw new Error('File lỗi, không đọc được.');
            await new Promise((r) => setTimeout(r, 1000));
        }
        throw new Error('Chờ đọc file quá lâu.');
    }

    dung() { this.audio.pause(); this._datNghe(null); }
}
