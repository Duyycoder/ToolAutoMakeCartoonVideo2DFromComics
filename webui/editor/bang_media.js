/* 🎞 Bảng Tệp phương tiện: nhập (chép vào media/), URL, tìm/lọc/sắp xếp, kéo thả xuống timeline.
 *
 * Sau khi một video sẵn sàng, bảng THỬ PHÁT nó trong chính WebView2 (canPlayType + nạp thử):
 * ffmpeg chỉ cho biết codec, không cho biết máy này có phát được không (có HEVC Video
 * Extensions thì .mov iPhone phát được). Không phát được → báo server tạo proxy H.264.
 */
import { api, esc, toast, hoi, chonFile, fmtNgan, coFile } from './chung.js';

const ICON = { video: '🎬', audio: '🎵', anh: '🖼', phu_de: '💬' };
const TEN_LOAI = { video: 'Video', audio: 'Âm thanh', anh: 'Ảnh', phu_de: 'Phụ đề' };
const CO_ANH = [76, 100, 136];
const DANG_XU_LY = ['dang_chep', 'dang_doc'];

export class BangMedia {
    constructor(ctx) {
        this.ctx = ctx;
        this.viec = [];
        this._hPoll = null;
        this._daThu = new Set();
        this._dangThu = false;
        this.el = document.createElement('div');
        this.el.style.cssText = 'display:flex;flex-direction:column;min-height:0;height:100%';
        this.el.innerHTML = `
            <div class="bang-dau"><h2>Tệp phương tiện</h2>
                <button class="nut nut-nho" data-l="url" title="Tải video từ link (TikTok, YouTube, Bilibili…)">🔗 URL</button>
                <button class="nut nut-chinh nut-nho" data-l="nhap" title="Chọn video/âm thanh/ảnh/phụ đề — file được CHÉP vào dự án">＋ Nhập</button>
                <button class="nut nut-nho" data-l="dc-mo" style="display:none">📂 Mở thư mục</button>
                <button class="nut nut-nho" data-l="dc-lam-moi" style="display:none">↻ Làm mới</button></div>
            <div class="tab-nho" data-khu="tab"><button data-tab="media">Media</button><button data-tab="dung_chung">Dùng chung</button></div>
            <div class="media-cong-cu">
                <input type="search" data-o="tim" placeholder="Tìm…">
                <select data-o="loc" title="Lọc loại"><option value="tat_ca">Tất cả</option><option value="video">Video</option>
                    <option value="audio">Âm thanh</option><option value="anh">Ảnh</option><option value="phu_de">Phụ đề</option></select>
                <select data-o="sap_xep" title="Sắp xếp"><option value="ngay">Mới nhập</option><option value="ten">Tên</option></select>
            </div>
            <div class="media-cong-cu">
                <button class="nut-icon" data-kieu="luoi" title="Dạng lưới">▦</button>
                <button class="nut-icon" data-kieu="ds" title="Dạng danh sách">☰</button>
                <input type="range" data-o="co_anh" min="0" max="2" step="1" title="Cỡ ảnh">
                <label style="display:flex;gap:5px;align-items:center;color:var(--chu-2);font-size:12px;cursor:pointer">
                    <input type="checkbox" data-o="nhom"> Nhóm theo loại</label>
            </div>
            <div class="bang-noi" data-khu="noi"></div>`;
        this.noi = this.el.querySelector('[data-khu=noi]');
        ctx.bus.on('bo_chon_nguon', () => this._veChon());
        this._gan();
        this.tai();
    }

    get km() { return this.ctx.ui.kho_media; }

    _gan() {
        const el = this.el;
        el.querySelector('[data-l=nhap]').addEventListener('click', () => this.nhap());
        el.querySelector('[data-l=url]').addEventListener('click', () => this.nhapUrl());
        el.querySelector('[data-l=dc-mo]').addEventListener('click', () => {
            api('/api/workspace/dung-chung/mo-thu-muc', { method: 'POST' }).catch(e => toast(e.message, 'error'));
        });
        el.querySelector('[data-l=dc-lam-moi]').addEventListener('click', () => {
            this._dungChung = null; this.ve();
        });
        el.querySelector('[data-khu=tab]').addEventListener('click', (e) => {
            const b = e.target.closest('[data-tab]');
            if (b) { this.km.tab = b.dataset.tab; this.ctx.luuUi(); this.ve(); }
        });
        el.querySelectorAll('[data-o]').forEach((o) => o.addEventListener('input', () => {
            const k = o.dataset.o;
            this.km[k] = o.type === 'checkbox' ? o.checked : o.type === 'range' ? Number(o.value) : o.value;
            this.ctx.luuUi();
            this.ve();
        }));
        el.querySelectorAll('[data-kieu]').forEach((b) => b.addEventListener('click', () => {
            this.km.kieu = b.dataset.kieu;
            this.ctx.luuUi();
            this.ve();
        }));
        this.noi.addEventListener('click', (e) => {
            const l = e.target.closest('[data-l]');
            if (l && l.dataset.l === 'nhap') return this.nhap();
            if (l && l.dataset.l === 'url') return this.nhapUrl();
            if (l && l.dataset.l === 'nhap-lai') return this.nhapLai(l.closest('.the-media').dataset.mid);
            if (l && l.dataset.l === 'tim-lai') return this.timLai(l.closest('.the-media').dataset.mid);
            if (l && ['an-tai', 'thu-lai-tai', 'huy-tai'].includes(l.dataset.l)) {
                const v = this.viec.find((x) => x.id === l.dataset.vid);
                if (!v) return undefined;
                if (l.dataset.l === 'huy-tai') {
                    return api(`/api/hang-doi/${v.id}/huy`, { method: 'POST' }).then(() => this.tai())
                        .catch((err) => toast(err.message, 'error'));
                }
                (this._anViec = this._anViec || new Set()).add(v.id);
                if (l.dataset.l === 'thu-lai-tai') this.taiUrl((v.tham_so || {}).urls || []);
                return this.ve();
            }
            const the = e.target.closest('.the-media');
            if (the) this.chon(the.dataset.mid);
        });
        this.noi.addEventListener('dblclick', (e) => {
            const the = e.target.closest('.the-media');
            if (the) { this.chon(the.dataset.mid); this.ctx.preview.batTat(); }
        });
        this.noi.addEventListener('contextmenu', (e) => {
            const the = e.target.closest('.the-media');
            if (!the) return;
            e.preventDefault();
            this.chon(the.dataset.mid);
            this.menu(the.dataset.mid, e.clientX, e.clientY);
        });
        this.noi.addEventListener('dragstart', (e) => {
            const the = e.target.closest('.the-media');
            if (!the) return;
            let m;
            if (the.classList.contains('dc') && this._dungChung) {
                m = this._dungChung.find(x => x.id === the.dataset.mid);
            } else {
                m = this.lay(the.dataset.mid);
            }
            if (!m || m.trang_thai !== 'san_sang') { e.preventDefault(); return; }
            e.dataTransfer.setData('application/x-media-id', m.id);
            if (the.classList.contains('dc')) {
                // Kéo 1 phát thì thêm vào dự án
                e.dataTransfer.setData('application/x-dung-chung', m.rel);
            }
            e.dataTransfer.setData(`application/x-loai-${m.loai}`, '1');
            e.dataTransfer.effectAllowed = 'copy';
        });
    }

    lay(mid) { return this.ctx.media.find((m) => m.id === mid); }

    /* Bấm một media = xem NGUỒN của nó ở khung xem trước (như Source monitor của phần mềm dựng). */
    chon(mid) {
        this.ctx.chon.media = mid;
        this.ctx.chon.clip = null;
        this.ctx.ui.dang_chon = [];
        this.ctx.luuUi();
        this.ctx.bus.emit('chon');
        const m = this.lay(mid);
        if (m) this.ctx.bus.emit('chon_nguon', m);
        this._veChon();
    }

    _veChon() {
        const mid = this.ctx.chon.media;
        this.noi.querySelectorAll('.the-media').forEach((t) => t.classList.toggle('chon', t.dataset.mid === mid));
    }

    // ------------------------------------------------------------ dữ liệu
    async tai() {
        clearTimeout(this._hPoll);
        try {
            const r = await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/media`);
            this.ctx.media = r.media;
            this.viec = r.viec;
            if (r.anh_bia) this.ctx.du.anh_bia = r.anh_bia;
            if (r.thong_so && JSON.stringify(r.thong_so) !== JSON.stringify(this.ctx.du.thong_so)) {
                this.ctx.du.thong_so = r.thong_so;   // "Lấy theo video đầu tiên" vừa áp
                this.ctx.bus.emit('thong_so');
            }
            this._baoKetQuaTai();
            this.ctx.bus.emit('media');
            if (this.el.isConnected) this.ve();
            this._thuPhat();
        } catch (e) { /* server bận — thử lại ở vòng sau */ }
        const conViec = this.viec.some((v) => ['cho', 'dang_chay'].includes(v.trang_thai))
            || this.ctx.media.some((m) => DANG_XU_LY.includes(m.trang_thai) || m.proxy === 'dang_tao');
        this._hPoll = setTimeout(() => this.tai(), conViec ? 1000 : 15000);
    }

    async nhap() {
        if (this.ctx.store.chiDoc) { toast('Cửa sổ này chỉ xem.', 'warn'); return; }
        try {
            const files = await chonFile('media');
            if (!files.length) return;
            const r = await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/media/nhap`,
                { method: 'POST', body: { phien: this.ctx.boLuu.phien, files } });
            toast(`Đang chép ${r.media.length} file vào dự án…`, 'info', 2500);
            this.tai();
        } catch (e) { toast(e.message, 'error'); }
    }

    async nhapUrl() {
        if (this.ctx.store.chiDoc) { toast('Cửa sổ này chỉ xem.', 'warn'); return; }
        const text = await hoi({ tieuDe: 'Tải video từ link', nut: 'Tải về dự án',
            noiDung: 'Mỗi dòng một link (TikTok, YouTube, Bilibili, Douyin…).\n'
                + 'Tiến độ hiện ở đầu bảng Tệp phương tiện. Tải xong, video được lưu vào thư mục media/ '
                + 'của dự án (tên theo tiêu đề video) và hiện ngay trong bảng này để kéo xuống timeline.',
            o: { nhieuDong: 5, goiY: 'https://…' } });
        const urls = (text || '').split(/\s+/).map((s) => s.trim()).filter((s) => /^https?:\/\//i.test(s));
        if (!text) return;
        if (!urls.length) { toast('Không thấy link hợp lệ (phải bắt đầu bằng http).', 'warn'); return; }
        this.taiUrl(urls);
    }

    async taiUrl(urls) {
        try {
            await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/media/url`,
                { method: 'POST', body: { phien: this.ctx.boLuu.phien, urls } });
            toast(`Đã bắt đầu tải ${urls.length} link — tiến độ hiện ở đầu bảng Tệp phương tiện.`, 'info', 4000);
            this.tai();
        } catch (e) { toast(e.message, 'error'); }
    }

    /* Lượt tải link vừa kết thúc → báo một lần (lần nạp trang đầu thì không báo lại việc cũ). */
    _baoKetQuaTai() {
        const lanDau = !this._daBao;
        this._daBao = this._daBao || new Set();
        for (const v of this.viec) {
            if (v.loai !== 'tai_url' || !['xong', 'loi', 'da_huy'].includes(v.trang_thai) || this._daBao.has(v.id)) continue;
            this._daBao.add(v.id);
            if (lanDau) continue;
            const kq = v.ket_qua || {};
            if (v.trang_thai === 'xong') {
                toast(`Đã tải xong ${kq.so_tai || 0} video vào media/ của dự án.`
                    + ((kq.loi || []).length ? `\n${kq.loi.length} link lỗi — xem thẻ đỏ ở đầu bảng.` : ''), 'success', 6000);
            } else if (v.trang_thai === 'loi') {
                toast(`Tải link lỗi: ${v.loi}`, 'error', 12000);
            }
        }
    }

    _theTai() {
        this._anViec = this._anViec || new Set();
        return this.viec.filter((v) => v.loai === 'tai_url' && !this._anViec.has(v.id)).map((v) => {
            const urls = ((v.tham_so || {}).urls || []);
            const kq = v.ket_qua || {};
            if (['cho', 'dang_chay'].includes(v.trang_thai)) {
                return `<div class="the-tai">⬇ ${esc(v.thong_diep || (v.trang_thai === 'cho' ? 'Đang chờ lượt…' : v.nhan))}
                    <span class="so">${v.tien_do != null ? ` ${Math.floor(v.tien_do)}%` : ''}</span>
                    <div class="thanh-tien-do" style="width:100%;margin-top:6px"><i style="width:${v.tien_do || 0}%"></i></div>
                    <div class="the-tai-nut"><button class="nut nut-nho" data-l="huy-tai" data-vid="${esc(v.id)}">Huỷ</button></div></div>`;
            }
            const loi = v.trang_thai === 'loi' ? [v.loi] : (kq.loi || []);
            if (v.trang_thai === 'xong' && !loi.length) return '';
            return `<div class="the-tai loi">${v.trang_thai === 'xong' ? `✔ Tải được ${kq.so_tai || 0} video, ` : '✘ '}
                ${loi.length} link lỗi (${esc(urls.length)} link):<div class="the-tai-loi">${loi.map((x) => esc(x)).join('<br>')}</div>
                <div class="the-tai-nut">
                    ${v.trang_thai === 'loi' ? `<button class="nut nut-nho" data-l="thu-lai-tai" data-vid="${esc(v.id)}">↻ Thử lại</button>` : ''}
                    <button class="nut nut-nho" data-l="an-tai" data-vid="${esc(v.id)}">Ẩn</button></div></div>`;
        }).join('');
    }

    async nhapLai(mid, nguon = '') {
        try {
            await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/media/${mid}/nhap-lai`,
                { method: 'POST', body: { phien: this.ctx.boLuu.phien, nguon } });
            this.tai();
        } catch (e) { toast(e.message, 'error'); }
    }

    async timLai(mid) {
        const files = await chonFile('media').catch((e) => { toast(e.message, 'error'); return []; });
        if (files.length) this.nhapLai(mid, files[0]);
    }

    async xoa(mid, xoaFile) {
        const m = this.lay(mid);
        const ok = await hoi({ tieuDe: `Bỏ "${m.ten}" khỏi dự án?`, nguyHiem: xoaFile,
            nut: xoaFile ? 'Bỏ và chuyển file vào Thùng rác' : 'Bỏ khỏi dự án',
            noiDung: xoaFile ? 'File trong media/ sẽ được chuyển vào Thùng rác.' : 'File vẫn còn trong thư mục media/ của dự án.' });
        if (!ok) return;
        try {
            await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/media/${mid}?phien=${encodeURIComponent(this.ctx.boLuu.phien)}&xoa_file=${xoaFile}`,
                { method: 'DELETE' });
            if (this.ctx.chon.media === mid) { this.ctx.chon.media = null; this.ctx.ui.xem_truoc.media = null; this.ctx.bus.emit('chon'); }
            this.tai();
        } catch (e) { toast(e.message, 'error'); }
    }

    menu(mid, x, y) {
        document.querySelectorAll('.menu').forEach((mm) => mm.remove());
        const m = this.lay(mid);
        const menu = document.createElement('div');
        menu.className = 'menu';
        const san = m.trang_thai === 'san_sang' && !m.mat_file;
        menu.innerHTML = `
            ${san ? '<button data-l="xem">▶ Xem trước</button>' : ''}
            ${san && ['video', 'anh', 'audio'].includes(m.loai) ? '<button data-l="them">⤵ Thêm vào cuối timeline</button>' : ''}
            ${san && m.loai === 'video' && m.proxy !== 'xong' ? '<button data-l="proxy">⚡ Tạo bản xem trước nhẹ (proxy)</button>' : ''}
            ${['bi_ngat', 'loi'].includes(m.trang_thai) ? '<button data-l="nhap-lai">↻ Nhập lại</button>' : ''}
            ${m.mat_file || ['bi_ngat', 'loi'].includes(m.trang_thai) ? '<button data-l="tim-lai">🔍 Tìm lại bằng file khác…</button>' : ''}
            <hr><button data-l="xoa">✕ Bỏ khỏi dự án</button>
            ${(m.file || '').startsWith('media/') ? '<button data-l="xoa-file" class="nguy">🗑 Bỏ và chuyển file vào Thùng rác</button>' : ''}`;
        document.body.appendChild(menu);
        const r = menu.getBoundingClientRect();
        menu.style.left = `${Math.min(x, innerWidth - r.width - 8)}px`;
        menu.style.top = `${Math.min(y, innerHeight - r.height - 8)}px`;
        menu.addEventListener('click', (e) => {
            const l = e.target.closest('[data-l]');
            if (!l) return;
            menu.remove();
            ({
                xem: () => this.ctx.preview.batTat(),
                them: () => this.ctx.timeline.themMedia(m, null, null),
                proxy: () => api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/media/${mid}/phat-duoc`,
                    { method: 'POST', body: { ok: false } }).then(() => this.tai()),
                'nhap-lai': () => this.nhapLai(mid),
                'tim-lai': () => this.timLai(mid),
                xoa: () => this.xoa(mid, false),
                'xoa-file': () => this.xoa(mid, true),
            }[l.dataset.l] || (() => {}))();
        });
        setTimeout(() => document.addEventListener('click', () => menu.remove(), { once: true }), 0);
    }

    // ------------------------------------------------------------ vẽ
    ve() {
        const km = this.km, el = this.el;
        el.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('bat', b.dataset.tab === km.tab));
        el.querySelectorAll('[data-kieu]').forEach((b) => b.classList.toggle('bat', b.dataset.kieu === km.kieu));
        el.querySelectorAll('[data-o]').forEach((o) => {
            if (document.activeElement === o) return;
            if (o.type === 'checkbox') o.checked = !!km[o.dataset.o];
            else o.value = km[o.dataset.o] ?? '';
        });
        
        const isDc = km.tab === 'dung_chung';
        el.querySelector('[data-l=nhap]').style.display = isDc ? 'none' : '';
        el.querySelector('[data-l=url]').style.display = isDc ? 'none' : '';
        el.querySelector('[data-l=dc-mo]').style.display = isDc ? '' : 'none';
        el.querySelector('[data-l=dc-lam-moi]').style.display = isDc ? '' : 'none';

        if (isDc) {
            if (!this._dungChung) {
                this.noi.innerHTML = '<p class="sap-co">Đang tải...</p>';
                api('/api/workspace/dung-chung').then(r => {
                    this._dungChung = r.media;
                    this.ve();
                }).catch(e => {
                    this.noi.innerHTML = `<div class="sap-co">Lỗi tải Kho Dùng chung: ${e.message}</div>`;
                });
                return;
            }
            const dc = this._dungChung;
            if (!dc.length) {
                this.noi.innerHTML = `<div class="sap-co"><b>Kho Dùng chung — có ở GĐ 2.</b><br>
                    Logo, intro, nhạc nền dùng cho nhiều dự án: nằm ở <code>_dung_chung/</code> trong Nơi làm việc,
                    kéo vào dự án nào cũng được mà không chép thêm.<br><br>
                    <i>Hiện chưa có file nào trong thư mục _dung_chung.</i></div>`;
                return;
            }
            
            // Tạm thời dùng lại code hiển thị grid cho media dùng chung
            const co = CO_ANH[km.co_anh] || CO_ANH[1];
            this.noi.innerHTML = `<div class="luoi-media ${km.kieu === 'ds' ? 'ds' : ''}" style="--co-anh:${co}px">${dc.map((m) => this._theDc(m)).join('')}</div>`;
            return;
        }
        const tim = (km.tim || '').toLowerCase();
        let ds = this.ctx.media.filter((m) => (km.loc === 'tat_ca' || m.loai === km.loc)
            && (!tim || `${m.ten} ${m.file}`.toLowerCase().includes(tim)));
        ds = km.sap_xep === 'ten'
            ? ds.slice().sort((a, b) => (a.ten || '').localeCompare(b.ten || '', 'vi', { numeric: true }))
            : ds.slice().sort((a, b) => (b.nhap_luc || '').localeCompare(a.nhap_luc || '') || b.id.localeCompare(a.id, 'en', { numeric: true }));

        let html = this._theTai();
        if (!this.ctx.media.length) {
            this.noi.innerHTML = html + `<div class="vung-tha"><b>Chưa có media</b>
                Nhập video, âm thanh, ảnh hoặc phụ đề — file được chép vào thư mục <code>media/</code> của dự án.
                <div style="display:flex;gap:8px;justify-content:center;margin-top:12px">
                <button class="nut nut-chinh" data-l="nhap">＋ Nhập file</button><button class="nut" data-l="url">🔗 Từ link</button></div></div>`;
            return;
        }
        const nhom = km.nhom ? ['video', 'audio', 'anh', 'phu_de'].map((l) => [l, ds.filter((m) => m.loai === l)]).filter(([, d]) => d.length)
            : [[null, ds]];
        const co = CO_ANH[km.co_anh] || CO_ANH[1];
        html += nhom.map(([l, d]) => `${l ? `<div class="nhom-dau">${TEN_LOAI[l]} · ${d.length}</div>` : ''}
            <div class="luoi-media ${km.kieu === 'ds' ? 'ds' : ''}" style="--co-anh:${co}px">${d.map((m) => this._the(m)).join('')}</div>`).join('');
        if (!ds.length) html += '<p style="color:var(--chu-2);padding:8px 0">Không có media khớp bộ lọc.</p>';
        this.noi.innerHTML = html;
    }

    _the(m) {
        const pid = encodeURIComponent(this.ctx.id);
        const v = this.viec.find((x) => x.media === m.id && x.loai === 'nhap');
        let anh = `<div class="anh">${ICON[m.loai] || '📄'}</div>`;
        if (m.thumb) anh = `<div class="anh" style="background-image:url('/api/du-an/${pid}/media/${m.id}/thumb?v=${esc(m.nhap_luc)}')"></div>`;
        else if (m.song_am) anh = `<div class="anh song" style="background-image:url('/api/du-an/${pid}/media/${m.id}/song-am?v=${esc(m.nhap_luc)}')"></div>`;
        let phu = '';
        if (m.trang_thai === 'dang_chep') {
            const pct = v && v.tien_do != null ? v.tien_do : 0;
            phu = `<div class="phu-tt">Đang chép ${Math.floor(pct)}%<div class="thanh-tien-do"><i style="width:${pct}%"></i></div></div>`;
        } else if (m.trang_thai === 'dang_doc') {
            phu = '<div class="phu-tt">Đang đọc thông số…</div>';
        } else if (m.trang_thai === 'bi_ngat' || m.trang_thai === 'loi') {
            phu = `<div class="phu-tt loi" title="${esc(m.loi || '')}">${m.trang_thai === 'bi_ngat' ? 'Bị ngắt khi nhập' : 'Lỗi nhập'}
                <button class="nut nut-nho" data-l="nhap-lai">↻ Nhập lại</button></div>`;
        } else if (m.mat_file) {
            phu = '<div class="phu-tt loi">Không tìm thấy file<button class="nut nut-nho" data-l="tim-lai">Tìm lại…</button></div>';
        }
        const nhanProxy = m.proxy === 'dang_tao' ? ' · tạo proxy…' : m.proxy === 'xong' ? ' · proxy' : '';
        const tt = [m.file, m.rong ? `${m.rong}×${m.cao}` : '', m.fps ? `${m.fps} fps` : '', m.codec || '',
            m.kich_thuoc ? coFile(m.kich_thuoc) : ''].filter(Boolean).join(' · ');
        return `<div class="the-media ${this.ctx.chon.media === m.id ? 'chon' : ''}" data-mid="${esc(m.id)}"
                draggable="${m.trang_thai === 'san_sang' && !m.mat_file}" title="${esc(tt)}">
            ${anh}${phu}
            ${m.thoi_luong ? `<span class="dai so">${fmtNgan(m.thoi_luong)}</span>` : ''}
            ${this.km.kieu === 'ds' ? `<span class="loai">${ICON[m.loai] || ''}</span>` : ''}
            <div class="ten">${esc(m.ten || m.file)}${nhanProxy ? `<span style="color:var(--chu-3)">${nhanProxy}</span>` : ''}</div>
        </div>`;
    }

    _theDc(m) {
        let anh = `<div class="anh">${ICON[m.loai] || '📄'}</div>`;
        const tt = [m.rel || m.file, m.kich_thuoc ? coFile(m.kich_thuoc) : ''].filter(Boolean).join(' · ');
        return `<div class="the-media dc" data-mid="${esc(m.id)}"
                draggable="true" title="${esc(tt)}">
            ${anh}
            ${m.thoi_luong ? `<span class="dai so">${fmtNgan(m.thoi_luong)}</span>` : ''}
            ${this.km.kieu === 'ds' ? `<span class="loai">${ICON[m.loai] || ''}</span>` : ''}
            <div class="ten">${esc(m.ten || m.file)}</div>
        </div>`;
    }

    // ------------------------------------------------ thử phát trong WebView2
    async _thuPhat() {
        if (this._dangThu) return;
        const m = this.ctx.media.find((x) => x.loai === 'video' && x.trang_thai === 'san_sang' && !x.mat_file
            && x.phat_duoc == null && !x.proxy && !this._daThu.has(x.id));
        if (!m) return;
        this._dangThu = true;
        this._daThu.add(m.id);
        try {
            const ok = await thuPhat(`/api/du-an/${encodeURIComponent(this.ctx.id)}/media/${m.id}/file?goc=1`, m.codec);
            await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/media/${m.id}/phat-duoc`, { method: 'POST', body: { ok } });
            if (!ok) toast(`"${m.ten}" không phát được trong app — đang tạo bản xem trước nhẹ (bản xuất vẫn dùng file gốc).`, 'info', 6000);
        } catch (e) { /* thử lại lần tải sau */ this._daThu.delete(m.id); }
        this._dangThu = false;
        this.tai();
    }
}

const CODEC_MIME = { hevc: 'video/mp4; codecs="hvc1"', h264: 'video/mp4; codecs="avc1.42E01E"', vp9: 'video/webm; codecs="vp9"', av1: 'video/mp4; codecs="av01.0.05M.08"' };

export function thuPhat(url, codec, timeout = 4000) {
    return new Promise((resolve) => {
        const v = document.createElement('video');
        if (codec && CODEC_MIME[codec] && !v.canPlayType(CODEC_MIME[codec])) { resolve(false); return; }
        let xong = false;
        const ket = (ok) => {
            if (xong) return;
            xong = true;
            clearTimeout(h);
            v.removeAttribute('src');
            v.load();
            resolve(ok);
        };
        const h = setTimeout(() => ket(false), timeout);
        v.muted = true;
        v.preload = 'auto';
        v.addEventListener('loadeddata', () => ket(v.videoWidth > 0));
        v.addEventListener('error', () => ket(false));
        v.src = url;
    });
}
