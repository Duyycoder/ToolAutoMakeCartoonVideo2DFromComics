/* ▭ Bảng Phụ đề: danh sách câu (sửa chữ/giờ), thêm câu, nhập/xuất .srt, tìm & thay, kiểu chữ.
 *
 * Câu nhập từ .srt/Whisper/OCR NEO theo media gốc (tu_media + t_vao/t_ra) nên cắt/dời video
 * thì phụ đề đi theo. Câu gõ tay khi đầu phát nằm trên một clip video cũng neo vào media đó;
 * không có video thì dùng giờ tuyệt đối. Mọi sửa đổi là lệnh hoàn tác được. */
import { api, esc, toast, hoi, chonFile } from './chung.js';
import {
    tao, dongPhuDe, opsThemCau, opsXoaNhieu, cauCuaMedia, srtTuTimeline, opsDatGio, clipTai, thoiDiemMedia,
    idClipMoi, kieuPhuDeMacDinh,
} from './store.js';

const FONT = ['Arial', 'Roboto', 'Segoe UI', 'Tahoma', 'Verdana', 'Times New Roman', 'Be Vietnam Pro', 'Montserrat'];

export class BangPhuDe {
    constructor(ctx) {
        this.ctx = ctx;
        this.el = document.createElement('div');
        this.el.style.cssText = 'display:flex;flex-direction:column;min-height:0;height:100%';
        this.el.innerHTML = `
            <div class="bang-dau"><h2>Phụ đề</h2>
                <button class="nut nut-nho" data-l="xuat" title="Ghi .srt theo giờ timeline vào phu_de/ của dự án">⤒ .srt</button>
                <button class="nut nut-nho" data-l="nhap" title="Nhập .srt/.vtt/.ass">⤓ .srt</button>
                <button class="nut nut-chinh nut-nho" data-l="them" title="Thêm câu tại đầu phát">＋ Câu</button></div>
            <div class="media-cong-cu">
                <input type="search" data-o="tim" placeholder="Tìm chữ…">
                <input type="text" data-o="thay" placeholder="Thay bằng…" style="flex:1;min-width:80px">
                <button class="nut nut-nho" data-l="thay" title="Thay tất cả câu khớp">Thay</button>
            </div>
            <div class="bang-noi" data-khu="noi" style="padding-top:0"></div>
            <details class="kieu-chu" data-khu="kieu"><summary>Kiểu chữ</summary><div data-khu="kieu-noi"></div></details>`;
        this.noi = this.el.querySelector('[data-khu=noi]');
        this.tim = '';
        this._gan();
        ctx.bus.on('timeline', () => { if (this.el.isConnected) this.ve(); });
        ctx.bus.on('media', () => { if (this.el.isConnected) this.ve(); });
        ctx.bus.on('dau_phat', () => { if (this.el.isConnected) this._veDangHien(); });
        ctx.bus.on('nhap_srt_media', (m) => this.nhapTuMedia(m));
    }

    get tl() { return this.ctx.store.timeline; }
    get fps() { return Number((this.ctx.du.thong_so || {}).fps) || 30; }

    _gan() {
        this.el.addEventListener('click', (e) => {
            const l = e.target.closest('[data-l]') && e.target.closest('[data-l]').dataset.l;
            if (l === 'them') this.them();
            if (l === 'nhap') this.nhapFile();
            if (l === 'xuat') this.xuat();
            if (l === 'thay') this.thayTatCa();
            const dong = e.target.closest('.dong-pd');
            if (l === 'xoa' && dong) { this.xoa(dong.dataset.id); return; }
            if (l === 'gio' && dong) { this.suaGio(dong); return; }
            if (dong && !e.target.closest('textarea, button, input')) {
                if (dong.dataset.bd !== '') this.ctx.timeline.datDauPhat(Number(dong.dataset.bd) + 0.001);
                this.ctx.timeline.chonClip(dong.dataset.id);
            }
        });
        this.el.querySelector('[data-o=tim]').addEventListener('input', (e) => { this.tim = e.target.value; this.ve(); });
        // Sửa chữ: gộp các lần gõ trong cùng một câu thành MỘT bước hoàn tác.
        this.noi.addEventListener('input', (e) => {
            const ta = e.target.closest('textarea');
            if (!ta) return;
            const id = ta.closest('.dong-pd').dataset.id;
            this._dangGo = true;
            this.ctx.sua('Sửa phụ đề', [tao.dat(this.tl, ['clips', { id }, 'text'], ta.value)], { gop: `pd:${id}` });
            this._dangGo = false;
        });
        this.noi.addEventListener('focusin', (e) => {
            const dong = e.target.closest('.dong-pd');
            if (dong && e.target.tagName === 'TEXTAREA' && dong.dataset.bd !== '') this.ctx.timeline.datDauPhat(Number(dong.dataset.bd) + 0.001);
        });
        const kieu = this.el.querySelector('[data-khu=kieu]');
        kieu.addEventListener('toggle', () => { if (kieu.open) this._veKieu(); });
        kieu.addEventListener('input', (e) => {
            const o = e.target.closest('[data-k]');
            if (!o) return;
            let v = o.type === 'range' || o.type === 'number' ? Number(o.value) : o.value;
            if (o.dataset.k === 'nen') v = o.checked ? 'Box' : 'None';
            if (!this.tl.kieu_phu_de) this.ctx.sua('Kiểu chữ', [tao.dat(this.tl, ['kieu_phu_de'], { k_mac_dinh: kieuPhuDeMacDinh() })]);
            if (!this.tl.kieu_phu_de.k_mac_dinh) this.ctx.sua('Kiểu chữ', [tao.dat(this.tl, ['kieu_phu_de', 'k_mac_dinh'], kieuPhuDeMacDinh())]);
            this.ctx.sua('Kiểu chữ phụ đề', [tao.dat(this.tl, ['kieu_phu_de', 'k_mac_dinh', o.dataset.k], v)], { gop: `kieu:${o.dataset.k}` });
            const nhan = o.closest('label') && o.closest('label').querySelector('.gt');
            if (nhan) nhan.textContent = o.type === 'range' ? (o.dataset.k === 'vi_tri_y' ? `${Math.round(v * 100)}%` : v) : '';
        });
    }

    /* Track phụ đề đích (track đang chọn nếu là phụ đề, không thì S1 / track phụ đề đầu tiên). */
    trackPhuDe() {
        const ds = this.tl.tracks.filter((t) => t.loai === 'phu_de');
        return ds.find((t) => t.id === this.ctx.ui.track_dang_chon) || ds.find((t) => t.id === 'S1') || ds[0];
    }

    clipVideoTai(t) {
        for (const tr of this.tl.tracks.filter((x) => x.loai === 'video').reverse()) {
            const c = clipTai(this.tl, tr.id, t);
            if (c && c.media) return c;
        }
        return null;
    }

    them() {
        const tr = this.trackPhuDe();
        if (!tr) return;
        const t = this.ctx.ui.dau_phat;
        const v = this.clipVideoTai(t);
        const id = idClipMoi(this.tl);
        let clip;
        if (v) {
            const tm = thoiDiemMedia(v, t);
            clip = { id, track: tr.id, loai: 'phu_de', tu_media: v.media, t_vao: Math.round(tm * 1000) / 1000,
                t_ra: Math.round(Math.min(Number(v.ra), tm + 2 * (Number(v.toc_do) || 1)) * 1000) / 1000,
                text: 'Câu mới', text_goc: '', kieu: 'k_mac_dinh' };
        } else {
            clip = { id, track: tr.id, loai: 'phu_de', bat_dau: Math.round(t * 1000) / 1000,
                ket_thuc: Math.round((t + 2) * 1000) / 1000, text: 'Câu mới', text_goc: '', kieu: 'k_mac_dinh' };
        }
        if (this.ctx.sua('Thêm câu phụ đề', [tao.them(this.tl, ['clips'], clip)])) {
            this.ctx.timeline.chonClip(id);
            requestAnimationFrame(() => {
                const ta = this.noi.querySelector(`.dong-pd[data-id="${id}"] textarea`);
                if (ta) { ta.focus(); ta.select(); }
            });
        }
    }

    xoa(id) {
        this.ctx.sua('Xoá câu phụ đề', [tao.xoaTheoId(this.tl, ['clips'], id)]);
    }

    async suaGio(dong) {
        const c = this.tl.clips.find((x) => x.id === dong.dataset.id);
        if (!c || dong.dataset.bd === '') { toast('Câu này đang nằm ngoài đoạn video trên timeline.', 'info'); return; }
        const bd = Number(dong.dataset.bd), kt = Number(dong.dataset.kt);
        const kq = await hoi({ tieuDe: 'Giờ hiện câu (trên timeline)', nut: 'Lưu',
            noiDung: 'Dạng phút:giây.mili — vd 1:02.500 → 1:05.000', o: { giaTri: `${gioNgan(bd)} → ${gioNgan(kt)}` } });
        if (!kq) return;
        const m = kq.split(/→|->|-/).map((x) => docGio(x.trim()));
        if (m.length !== 2 || m.some((x) => x == null) || m[1] <= m[0]) { toast('Không đọc được giờ.', 'warn'); return; }
        this.ctx.sua('Sửa giờ phụ đề', opsDatGio(this.tl, c, dong.dataset.vid, m[0], m[1]));
    }

    thayTatCa() {
        const tim = this.el.querySelector('[data-o=tim]').value;
        const thay = this.el.querySelector('[data-o=thay]').value;
        if (!tim) { toast('Nhập chữ cần tìm trước.', 'info'); return; }
        const ops = this.tl.clips.filter((c) => c.loai === 'phu_de' && (c.text || '').includes(tim))
            .map((c) => tao.dat(this.tl, ['clips', { id: c.id }, 'text'], c.text.split(tim).join(thay)));
        if (!ops.length) { toast('Không câu nào khớp.', 'info'); return; }
        if (this.ctx.sua(`Thay "${tim}" (${ops.length} câu)`, ops)) toast(`Đã thay trong ${ops.length} câu.`, 'success', 2500);
    }

    // ------------------------------------------------------------ nhập / xuất
    async nhapFile() {
        try {
            const files = await chonFile('media');
            const f = files.find((x) => /\.(srt|vtt|ass)$/i.test(x));
            if (!f) { if (files.length) toast('Hãy chọn file .srt / .vtt / .ass.', 'warn'); return; }
            const r = await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/phu-de/doc`, { method: 'POST', body: { path: f } });
            await this.apCau(r.cau, `Nhập ${f.split(/[\\/]/).pop()}`);
        } catch (e) { toast(e.message, 'error'); }
    }

    async nhapTuMedia(m) {
        try {
            const r = await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/phu-de/doc`, { method: 'POST', body: { mid: m.id } });
            await this.apCau(r.cau, `Nhập ${m.ten}`, m.tu_media);
        } catch (e) { toast(e.message, 'error'); }
    }

    /* Đưa một loạt câu (giờ tính từ đầu video nguồn) vào track phụ đề, neo theo video người dùng chọn. */
    async apCau(cau, ten, goiYMedia = '') {
        if (!cau.length) { toast('File không có câu nào.', 'warn'); return; }
        const tr = this.trackPhuDe();
        const videoTl = [...new Set(this.tl.clips.filter((c) => c.media && this.ctx.media.find((m) => m.id === c.media && m.loai === 'video'))
            .map((c) => c.media))];
        const duoiDauPhat = this.clipVideoTai(this.ctx.ui.dau_phat);
        let mid = goiYMedia || (duoiDauPhat && duoiDauPhat.media) || videoTl[0] || '';
        if (videoTl.length > 1 || (videoTl.length && !goiYMedia)) {
            const tenMedia = (id) => (this.ctx.media.find((m) => m.id === id) || {}).ten || id;
            const chon = await hoiChon(`${ten}: ${cau.length} câu`, 'Giờ trong file tính từ đầu video nào?',
                [...videoTl.map((id) => [id, `🎬 ${tenMedia(id)}`]), ['', '⏱ Giờ tuyệt đối trên timeline']], mid);
            if (chon === null) return;
            mid = chon;
        }
        const cu = mid ? cauCuaMedia(this.tl, mid) : [];
        let ops = [];
        if (cu.length) {
            const thay = await hoi({ tieuDe: `Video này đã có ${cu.length} câu phụ đề`, nut: 'Thay các câu cũ', huy: 'Thêm vào',
                noiDung: 'Thay thế bộ phụ đề cũ, hay giữ lại và thêm các câu mới?' });
            if (thay) ops = opsXoaNhieu(this.tl, cu.map((c) => c.id));
        }
        // Áp phần xoá vào bản nháp để chỉ số chèn của câu mới tính đúng.
        const nhap = JSON.parse(JSON.stringify(this.tl));
        ops.forEach((op) => nhap.clips.splice(op.vi_tri, 1));
        ops = ops.concat(opsThemCau(nhap, tr.id, mid, cau));
        if (this.ctx.sua(ten, ops)) {
            toast(`Đã thêm ${cau.length} câu phụ đề.`, 'success', 2500);
            if (this.ctx.ui.bang_trai !== 'phu_de') this.ctx.moBang('phu_de');
        }
    }

    async xuat() {
        const noiDung = srtTuTimeline(this.tl);
        if (!noiDung.trim()) { toast('Chưa có câu phụ đề nào đang hiện trên timeline.', 'info'); return; }
        const ten = await hoi({ tieuDe: 'Xuất phụ đề .srt', nut: 'Lưu', noiDung: 'Lưu vào thư mục phu_de/ của dự án (giờ theo timeline).',
            o: { giaTri: `${this.ctx.du.name}.srt` } });
        if (!ten) return;
        try {
            const r = await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/phu-de/luu`,
                { method: 'POST', body: { phien: this.ctx.boLuu.phien, ten, noi_dung: noiDung } });
            toast(`Đã lưu ${r.file}`, 'success');
        } catch (e) { toast(e.message, 'error'); }
    }

    // ------------------------------------------------------------ vẽ
    ve() {
        if (this._dangGo) return;          // đang gõ trong textarea: đừng vẽ lại làm mất con trỏ
        const tim = this.tim.toLowerCase();
        const ds = dongPhuDe(this.tl).filter((d) => !tim || (d.c.text || '').toLowerCase().includes(tim)
            || (d.c.text_goc || '').toLowerCase().includes(tim));
        const media = Object.fromEntries(this.ctx.media.map((m) => [m.id, m]));
        const chon = new Set(this.ctx.ui.dang_chon || []);
        if (!this.tl.clips.some((c) => c.loai === 'phu_de')) {
            this.noi.innerHTML = `<div class="vung-tha"><b>Chưa có phụ đề</b>
                Tạo tự động ở bảng 🪄 AI (Whisper hoặc OCR sub cứng), nhập file .srt, hoặc thêm câu tại đầu phát.
                <div style="display:flex;gap:8px;justify-content:center;margin-top:12px">
                <button class="nut nut-chinh" data-l="them">＋ Câu</button><button class="nut" data-l="nhap">⤓ Nhập .srt</button></div></div>`;
            return;
        }
        this.noi.innerHTML = `<div class="dem-pd">${ds.length} dòng${tim ? ' khớp' : ''}</div>` + ds.map((d) => {
            const c = d.c;
            const nguon = c.tu_media ? (media[c.tu_media] || {}).ten || c.tu_media : 'tuyệt đối';
            return `<div class="dong-pd ${chon.has(c.id) ? 'chon' : ''} ${d.bd == null ? 'ngoai' : ''}" data-id="${esc(c.id)}"
                    data-vid="${esc(d.clip || '')}" data-bd="${d.bd ?? ''}" data-kt="${d.kt ?? ''}">
                <div class="dong-pd-dau">
                    <button class="gio-pd so" data-l="gio" title="Sửa giờ">${d.bd == null ? 'ngoài timeline' : `${gioNgan(d.bd)} → ${gioNgan(d.kt)}`}</button>
                    <span class="nguon-pd" title="Neo theo">${esc(nguon)}</span>
                    <button class="nut-icon" data-l="xoa" title="Xoá câu">✕</button>
                </div>
                <textarea rows="${Math.min(4, (c.text || '').split('\n').length)}" spellcheck="false">${esc(c.text || '')}</textarea>
                ${c.text_goc && c.text_goc !== c.text ? `<div class="goc-pd">${esc(c.text_goc)}</div>` : ''}
            </div>`;
        }).join('');
        this._veDangHien();
        if (this.el.querySelector('[data-khu=kieu]').open) this._veKieu();
    }

    _veDangHien() {
        const t = this.ctx.ui.dau_phat;
        this.noi.querySelectorAll('.dong-pd').forEach((d) => {
            const dang = d.dataset.bd !== '' && t >= Number(d.dataset.bd) && t < Number(d.dataset.kt);
            if (dang !== d.classList.contains('dang')) {
                d.classList.toggle('dang', dang);
                if (dang && this.ctx.preview && this.ctx.preview.dangPhat) d.scrollIntoView({ block: 'nearest' });
            }
        });
    }

    _veKieu() {
        const k = { ...kieuPhuDeMacDinh(), ...((this.tl.kieu_phu_de || {}).k_mac_dinh || {}) };
        this.el.querySelector('[data-khu=kieu-noi]').innerHTML = `<div class="o-form kieu-form">
            <label>Phông chữ<select data-k="font">${['', ...FONT].map((f) => `<option value="${esc(f)}" ${f === (k.font || '') ? 'selected' : ''}>${f || 'Mặc định (Arial)'}</option>`).join('')}</select></label>
            <label>Cỡ chữ (theo khung 1080p) <span class="gt">${k.co}</span><input type="range" data-k="co" min="16" max="140" step="1" value="${k.co}"></label>
            <div class="hang"><label>Màu chữ<input type="color" data-k="mau" value="${esc(k.mau)}"></label>
                <label>Màu viền<input type="color" data-k="vien" value="${esc(k.vien)}"></label></div>
            <label>Độ dày viền <span class="gt">${k.do_day_vien}</span><input type="range" data-k="do_day_vien" min="0" max="10" step="0.5" value="${k.do_day_vien}"></label>
            <div class="hang"><label class="check"><input type="checkbox" data-k="nen" ${(k.nen || 'None') !== 'None' ? 'checked' : ''}> Nền hộp</label>
                <label>Màu nền<input type="color" data-k="mau_nen" value="${esc(k.mau_nen || '#000000')}"></label></div>
            <label>Vị trí dọc <span class="gt">${Math.round(k.vi_tri_y * 100)}%</span><input type="range" data-k="vi_tri_y" min="0.05" max="0.98" step="0.01" value="${k.vi_tri_y}"></label>
        </div>`;
    }
}

function gioNgan(t) {
    const m = Math.floor(t / 60), s = t - m * 60;
    return `${m}:${s.toFixed(3).padStart(6, '0')}`;
}

function docGio(s) {
    const m = /^(?:(\d+):)?(\d+(?:[.,]\d+)?)$/.exec(s.trim());
    if (!m) return null;
    return (Number(m[1] || 0) * 60) + Number(m[2].replace(',', '.'));
}

/* Hộp chọn một trong nhiều phương án (select). */
function hoiChon(tieuDe, noiDung, ds, macDinh) {
    return new Promise((resolve) => {
        const nen = document.createElement('div');
        nen.className = 'modal-nen';
        nen.innerHTML = `<div class="modal"><h3>${esc(tieuDe)}</h3><p class="modal-noi-dung">${esc(noiDung)}</p>
            <select class="o-nhap">${ds.map(([v, t]) => `<option value="${esc(v)}" ${v === macDinh ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select>
            <div class="modal-nut"><button class="nut" data-kq="huy">Huỷ</button><button class="nut nut-chinh" data-kq="ok">Tiếp</button></div></div>`;
        document.body.appendChild(nen);
        const sel = nen.querySelector('select');
        nen.addEventListener('click', (e) => {
            const kq = e.target.dataset && e.target.dataset.kq;
            if (e.target === nen || kq === 'huy') { nen.remove(); resolve(null); }
            if (kq === 'ok') { nen.remove(); resolve(sel.value); }
        });
        sel.focus();
    });
}

export { hoiChon, gioNgan };
