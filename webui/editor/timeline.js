/* Timeline nhiều track, thao tác kiểu phần mềm dựng (CapCut/Vietsub ProMax):
 * - bấm thước hoặc vùng trống → đầu phát nhảy tới; kéo đầu phát để tua
 * - kéo thân clip để dời (kể cả sang track cùng loại), kéo mép để tỉa; bắt dính vào mép clip/đầu phát
 * - S / ✂ cắt tại đầu phát; Delete xoá; mọi thao tác là MỘT lệnh hoàn tác được, tự lưu
 * Khi kéo chỉ đổi style DOM; thả tay mới ghi lệnh vào store (một bước hoàn tác). */
import { $, esc, toast, fmtThoiGian, api, hoi } from './chung.js';
import {
    tao, thoiLuong, ketThucClip, choTrong, idClipMoi, hutDinh, diemDinh, chongClip, gioiHanTia, opsTach, clipTai,
    hienThiNeo, opsDatGio, opsThemTrack, opsKhepKhoang, opsXoaGon, opsChenGon, opsTiaToiDauPhat, idMoiNhieu,
    moRongNhom, opsTachAm, idNhomMoi, trackVideoTuDuoiLen, opsThemChuyenCanh, opsXoaChuyenCanh, nhanClip, viTriKeyframes,
    mucMenuChoClip, opsNhanDoi,
} from './store.js';

const LOP = { video: 'v', phu_de: 's', lop_phu: 'o', audio: 'a' };
const BUOC_NHAN = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200];
const MEP = 7;                // px vùng nắm mép để tỉa
const DINH_PX = 8;            // khoảng bắt dính (px)
const H_KHUNG = 40;           // chiều cao ô khung hình trong clip
const CAO_SPRITE = 54;        // media.tao_dai_hinh: scale=-2:54

export const pxGiay = (zoom) => 5 * 2 ** (Math.max(0, Math.min(1, zoom)) * 7);

export class Timeline {
    constructor(ctx) {
        this.ctx = ctx;
        this.el = $('vungTimeline');
        this.el.innerHTML = `
            <div class="tl-cong-cu">
                <button class="nut-icon bat" title="Chọn (V)">↖</button>
                <button class="nut-icon" data-l="cat" title="Cắt tại đầu phát (S)">✂</button>
                <button class="nut-icon" data-l="hoan-tac" title="Hoàn tác (Ctrl+Z)">↶</button>
                <button class="nut-icon" data-l="lam-lai" title="Làm lại (Ctrl+Y)">↷</button>
                <button class="nut-icon" data-l="xoa" title="Xoá clip đang chọn (Delete)">✕</button>
                <button class="nut-icon" data-l="khep-khoang" title="Khép khoảng trống trên track đang chọn">⇤</button>
                <span class="ngan"></span>
                <span class="tl-goi-y">Kéo clip để dời, mép để tỉa · S cắt · Q/W tỉa tới ĐP · M đánh dấu · Shift+Del xoá gợn</span>
                <div class="gian"></div>
                <button class="nut-icon" data-l="bat-dinh" title="Bắt dính">🧲</button>
                <button class="nut-icon" data-l="lien-ket" title="Liên kết hình–tiếng">🔗</button>
                <span class="ngan"></span>
                <button class="nut-icon" data-l="thu" title="Thu nhỏ">−</button>
                <input type="range" data-l="zoom" min="0" max="1" step="0.01" title="Zoom (Ctrl+cuộn chuột)">
                <button class="nut-icon" data-l="phong" title="Phóng to">+</button>
                <button class="nut-icon" data-l="vua" title="Vừa khung (hiện cả timeline)">⛶</button>
                <button class="nut-icon" data-l="bang-phai" title="Ẩn/hiện bảng thuộc tính">◧</button>
            </div>
            <div class="tl-than">
                <div class="tl-dau-cot"><div class="thuoc-cho">TRACKS</div><div data-khu="dau" style="overflow:hidden;flex:1"></div></div>
                <div class="tl-cuon" data-khu="cuon"><div class="tl-noi" data-khu="noi"></div></div>
            </div>`;
        this.dau = this.el.querySelector('[data-khu=dau]');
        this.cuon = this.el.querySelector('[data-khu=cuon]');
        this.noi = this.el.querySelector('[data-khu=noi]');
        this.zoom = this.el.querySelector('[data-l=zoom]');
        this._daKhoiPhucCuon = false;
        this._keo = null;
        this._gan();
        ctx.bus.on('timeline', () => { if (!this._keo) this.ve(); });
        ctx.bus.on('media', () => { if (!this._keo) this.ve(); });
        ctx.bus.on('chon', () => this._veChon());
        ctx.bus.on('bo_cuc', () => this.ve());
    }

    get ui() { return this.ctx.ui; }
    get tl() { return this.ctx.store.timeline; }
    get px() { return pxGiay(this.ui.zoom_timeline); }

    _t(clientX) {
        return Math.max(0, (clientX - this.noi.getBoundingClientRect().left) / this.px);
    }

    _gan() {
        const ctx = this.ctx;
        this.el.querySelector('.tl-cong-cu').addEventListener('click', (e) => {
            const l = e.target.closest('[data-l]') && e.target.closest('[data-l]').dataset.l;
            if (l === 'hoan-tac') ctx.hoanTac();
            if (l === 'lam-lai') ctx.lamLai();
            if (l === 'xoa') this.xoaDangChon();
            if (l === 'khep-khoang') this.khepKhoangDangChon();
            if (l === 'cat') this.catTaiDauPhat();
            if (l === 'thu') this.datZoom(this.ui.zoom_timeline - 0.08);
            if (l === 'phong') this.datZoom(this.ui.zoom_timeline + 0.08);
            if (l === 'vua') this.vuaKhung();
            if (l === 'bang-phai') ctx.bus.emit('bat_bang_phai');
            if (l === 'bat-dinh' || l === 'lien-ket') {
                const k = l === 'bat-dinh' ? 'bat_dinh' : 'lien_ket_am_thanh';
                this.ui[k] = !this.ui[k];
                ctx.luuUi();
                this._veCongCu();
            }
        });
        this.zoom.addEventListener('input', () => this.datZoom(Number(this.zoom.value)));
        this.cuon.addEventListener('scroll', () => {
            this.dau.scrollTop = this.cuon.scrollTop;
            this.ui.cuon_timeline = { x: Math.round(this.cuon.scrollLeft), y: Math.round(this.cuon.scrollTop) };
            if (this._daKhoiPhucCuon) ctx.luuUi();
            document.querySelectorAll('.menu').forEach((mm) => mm.remove());
        });
        this.cuon.addEventListener('wheel', (e) => {
            if (!e.ctrlKey) return;
            e.preventDefault();
            const r = this.cuon.getBoundingClientRect();
            const tChuot = (e.clientX - r.left + this.cuon.scrollLeft) / this.px;
            this.datZoom(this.ui.zoom_timeline + (e.deltaY < 0 ? 0.05 : -0.05), { t: tChuot, x: e.clientX - r.left });
        }, { passive: false });

        this.noi.addEventListener('pointerdown', (e) => {
            if (e.button !== 0) return;
            const cc = e.target.closest('.cc-diem');
            if (cc) { this.chonChuyenCanh(cc.dataset.cc); return; }
            const clip = e.target.closest('.clip');
            if (clip && clip.classList.contains('neo')) { this._keoNeo(e, clip); return; }
            if (clip) { this._batDauKeoClip(e, clip); return; }
            // Thước, đầu phát, vùng trống của track: đặt đầu phát và kéo để tua.
            if (e.target.closest('.thuoc, .tl-track, .dau-phat, .tl-noi')) {
                if (e.target.closest('.tl-track')) this.chonClip(null);
                this._keoDauPhat(e);
            }
        });

        this.noi.addEventListener('dblclick', (e) => {
            const dd = e.target.closest('.danh-dau');
            if (dd) {
                const id = dd.dataset.dd;
                const d = (this.tl.danh_dau || []).find(x => x.id === id);
                if (!d) return;
                const tenMoi = prompt('Tên đánh dấu:', d.ten);
                if (tenMoi != null && tenMoi !== d.ten) {
                    this.ctx.sua('Đổi tên đánh dấu', [tao.dat(this.tl, ['danh_dau', { id }, 'ten'], tenMoi)]);
                }
            }
        });

        this.noi.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            const dd = e.target.closest('.danh-dau');
            if (dd) {
                this.ctx.sua('Xoá đánh dấu', [tao.xoaTheoId(this.tl, ['danh_dau'], dd.dataset.dd)]);
                return;
            }
            const clip = e.target.closest('.clip');
            if (clip) {
                const cid = clip.dataset.id;
                if (!(this.ui.dang_chon || []).includes(cid)) this.chonClip(cid);
                this.menuClip(cid, e.clientX, e.clientY);
            } else {
                const tr = e.target.closest('.tl-track');
                const t = this._t(e.clientX);
                this.menuVungTrong(tr ? tr.dataset.track : null, t, e.clientX, e.clientY);
            }
        });

        // Thả thẻ chuyển cảnh (bảng ⊘) gần một điểm nối trên track nền.
        this.noi.addEventListener('dragover', (e) => {
            if (!e.dataTransfer.types.includes('application/x-chuyen-canh')) return;
            const noi = this._diemNoiGan(e.clientX);
            this.noi.querySelectorAll('.cc-goi-y').forEach((x) => x.remove());
            if (!noi) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
            const tr = this.noi.querySelector(`.tl-track[data-track="${CSS.escape(noi.track)}"]`);
            if (tr) tr.insertAdjacentHTML('beforeend', `<b class="cc-goi-y" style="left:${noi.t * this.px}px"></b>`);
        });
        this.noi.addEventListener('drop', (e) => {
            const loai = e.dataTransfer.getData('application/x-chuyen-canh');
            if (!loai) return;
            this.noi.querySelectorAll('.cc-goi-y').forEach((x) => x.remove());
            const noi = this._diemNoiGan(e.clientX);
            if (!noi) { toast('Thả chuyển cảnh ngay điểm nối giữa hai clip trên track nền.', 'info'); return; }
            e.preventDefault();
            e.stopImmediatePropagation();
            this.ctx.sua(`Thêm chuyển cảnh ${loai}`, opsThemChuyenCanh(this.tl, noi.truoc, noi.sau, loai, 0.5));
        });

        // Thả media từ bảng Tệp phương tiện.
        this.noi.addEventListener('dragover', (e) => {
            if (!e.dataTransfer.types.includes('application/x-media-id')) return;
            const tr = e.target.closest('.tl-track');
            if (!tr) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
            this.noi.querySelectorAll('.tha-vao').forEach((x) => x !== tr && x.classList.remove('tha-vao'));
            tr.classList.add('tha-vao');
        });
        this.noi.addEventListener('dragleave', (e) => {
            const tr = e.target.closest('.tl-track');
            if (tr && !tr.contains(e.relatedTarget)) tr.classList.remove('tha-vao');
        });
        this.noi.addEventListener('drop', (e) => {
            const tr = e.target.closest('.tl-track');
            this.noi.querySelectorAll('.tha-vao').forEach((x) => x.classList.remove('tha-vao'));
            const mid = e.dataTransfer.getData('application/x-media-id');
            const dc = e.dataTransfer.getData('application/x-dung-chung');
            if (!tr || (!mid && !dc)) return;
            e.preventDefault();
            
            if (dc && (!mid || !this.ctx.media.find(x => x.id === mid))) {
                toast('Đang nạp file dùng chung...', 'info');
                api('/api/workspace').then(r => {
                    const absPath = r.duong_dan + '/_dung_chung/' + dc.replace('../', '');
                    return api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/media/nhap`, {
                        method: 'POST', body: { phien: this.ctx.boLuu.phien, files: [absPath] }
                    });
                }).then(r => {
                    this.ctx.bus.emit('media_can_tai');
                    if (r.media && r.media.length > 0) {
                        const m = r.media[0];
                        const trackId = tr.dataset.track;
                        const tDat = this._t(e.clientX);
                        const checkAndPlace = () => {
                            const foundMoi = this.ctx.media.find(x => x.id === m.id);
                            if (foundMoi && foundMoi.trang_thai === 'san_sang') {
                                this.ctx.bus.off('media', checkAndPlace);
                                this.themMedia(foundMoi, trackId, tDat);
                            } else if (foundMoi && foundMoi.trang_thai === 'loi') {
                                this.ctx.bus.off('media', checkAndPlace);
                                toast('Lỗi nhập file.', 'error');
                            }
                        };
                        this.ctx.bus.on('media', checkAndPlace);
                        checkAndPlace();
                    }
                }).catch(err => toast(err.message, 'error'));
                return;
            }
            
            const m = this.ctx.media.find((x) => x.id === mid);
            if (m) this.themMedia(m, tr.dataset.track, this._t(e.clientX));
        });

        this.dau.addEventListener('click', (e) => {
            const hd = e.target.closest('[data-hd]');
            if (hd) {
                const act = hd.dataset.hd;
                if (act === 'them-v' || act === 'them-a') {
                    const loai = act === 'them-v' ? 'video' : 'audio';
                    const lenh = opsThemTrack(this.tl, loai);
                    this.ctx.sua(`Thêm track ${lenh.id}`, lenh.ops);
                    return;
                }
                if (act === 'xoa-track') {
                    const tid = hd.closest('.tl-dau-track').dataset.track;
                    if (this.tl.clips.some(c => c.track === tid)) {
                        toast('Track đang chứa clip — phải xoá hết clip trước.', 'warn');
                        return;
                    }
                    this.ctx.sua(`Xoá track ${tid}`, [tao.xoaTheoId(this.tl, ['tracks'], tid)]);
                    return;
                }
            }

            const b = e.target.closest('[data-bat]');
            if (!b) return;
            const tid = b.closest('.tl-dau-track').dataset.track;
            const k = b.dataset.bat;
            const tr = this.tl.tracks.find((t) => t.id === tid);
            const ten = { an: tr[k] ? 'Hiện' : 'Ẩn', khoa: tr[k] ? 'Mở khoá' : 'Khoá', tat_tieng: tr[k] ? 'Bật tiếng' : 'Tắt tiếng' }[k];
            this.ctx.sua(`${ten} track ${tid}`, [tao.dat(this.tl, ['tracks', { id: tid }, k], !tr[k])]);
        });

        this.dau.addEventListener('dblclick', (e) => {
            if (e.target.tagName !== 'B') return;
            const hd = e.target.closest('.tl-dau-track');
            if (!hd) return;
            const tid = hd.dataset.track;
            const tr = this.tl.tracks.find(t => t.id === tid);
            if (!tr) return;
            const tenMoi = prompt('Đổi tên track:', tr.ten || tr.id);
            if (tenMoi != null && tenMoi !== (tr.ten || tr.id)) {
                this.ctx.sua(`Đổi tên track ${tid}`, [tao.dat(this.tl, ['tracks', { id: tid }, 'ten'], tenMoi)]);
            }
        });
    }

    // --------------------------------------------------------------- đầu phát
    _keoDauPhat(e) {
        const ctx = this.ctx;
        if (ctx.preview) ctx.preview.dung();
        const laThuoc = !!e.target.closest('.thuoc, .dau-phat');
        const dinh = this.ui.bat_dinh ? diemDinh(this.tl, -1) : [];
        const t0 = this._t(e.clientX);
        const y0 = e.clientY;
        const x0 = e.clientX;
        
        let dangKeoKhung = false;
        let vungKhung = null;

        const dat = (ev) => {
            const t = this._t(ev.clientX);
            this.datDauPhat(ev.shiftKey || !this.ui.bat_dinh ? t : hutDinh(t, dinh, DINH_PX / this.px), true);
        };
        const el = this.noi;
        el.setPointerCapture(e.pointerId);

        const di = (ev) => {
            if (!dangKeoKhung && !laThuoc && (Math.abs(ev.clientX - x0) > 4 || Math.abs(ev.clientY - y0) > 4)) {
                dangKeoKhung = true;
                vungKhung = document.createElement('div');
                vungKhung.className = 'khung-chon';
                el.appendChild(vungKhung);
            }
            if (dangKeoKhung) {
                const r = el.getBoundingClientRect();
                const x = Math.min(x0, ev.clientX) - r.left + el.scrollLeft;
                const y = Math.min(y0, ev.clientY) - r.top + el.scrollTop;
                const w = Math.abs(ev.clientX - x0);
                const h = Math.abs(ev.clientY - y0);
                vungKhung.style.left = `${x}px`;
                vungKhung.style.top = `${y}px`;
                vungKhung.style.width = `${w}px`;
                vungKhung.style.height = `${h}px`;

                const chons = [];
                const khoa = new Set(this.tl.tracks.filter((x) => x.khoa).map((x) => x.id));
                const kLeft = x, kRight = x + w, kTop = y, kBottom = y + h;
                el.querySelectorAll('.clip').forEach((cEl) => {
                    const cid = cEl.dataset.id;
                    const c = this.tl.clips.find(x => x.id === cid);
                    if (c && !khoa.has(c.track)) {
                        const cr = cEl.getBoundingClientRect();
                        const cx = cr.left - r.left + el.scrollLeft, cy = cr.top - r.top + el.scrollTop;
                        if (!(cx > kRight || cx + cr.width < kLeft || cy > kBottom || cy + cr.height < kTop)) {
                            chons.push(cid);
                        }
                    }
                });
                this.ui.dang_chon = chons;
                this.ctx.chon.clip = chons[chons.length - 1] || null;
                this.ctx.bus.emit('chon');
            } else {
                dat(ev);
            }
        };
        const xong = () => {
            el.removeEventListener('pointermove', di);
            el.removeEventListener('pointerup', xong);
            if (vungKhung) vungKhung.remove();
            if (!dangKeoKhung && !laThuoc) dat(e); // click thả không kéo -> đặt đầu phát
            if (laThuoc && !dangKeoKhung) dat(e); // click trên thước
            ctx.luuUi();
        };
        el.addEventListener('pointermove', di);
        el.addEventListener('pointerup', xong);
    }

    datDauPhat(t, tuThuoc = false, cuonTheo = false) {
        this.ui.dau_phat = Math.max(0, Math.min(Number(t) || 0, thoiLuong(this.tl)));
        this._veDauPhat();
        if (cuonTheo) this._cuonTheo();
        this.ctx.bus.emit('dau_phat', { tuThuoc });
        if (!tuThuoc) this.ctx.luuUi();
    }

    /* Lúc phát: đầu phát chạy ra khỏi khung nhìn thì lật trang như các phần mềm dựng. */
    _cuonTheo() {
        const x = this.ui.dau_phat * this.px;
        const trai = this.cuon.scrollLeft, rong = this.cuon.clientWidth;
        if (x > trai + rong - 40 || x < trai) this.cuon.scrollLeft = Math.max(0, x - 60);
    }

    // ------------------------------------------------------------ kéo / tỉa clip
    _batDauKeoClip(e, el) {
        const ctx = this.ctx;
        const cid = el.dataset.id;
        const c = this.tl.clips.find((x) => x.id === cid);
        if (!c) return;
        const tr = this.tl.tracks.find((t) => t.id === c.track);
        if (!(this.ui.dang_chon || []).includes(cid) || e.shiftKey || e.ctrlKey) this.chonClip(cid, e.shiftKey || e.ctrlKey);
        if (tr && tr.khoa) return;
        if (ctx.store.chiDoc) return;
        const r = el.getBoundingClientRect();
        const kieu = e.clientX - r.left < MEP ? 'trai' : r.right - e.clientX < MEP ? 'phai' : 'doi';
        const m = ctx.media.find((x) => x.id === c.media) || {};
        const toc = Number(c.toc_do) || 1;
        const goc = { bd: Number(c.bat_dau) || 0, kt: ketThucClip(c), vao: Number(c.vao) || 0, ra: Number(c.ra) || 0 };
        const gh = gioiHanTia(this.tl, c, Number(m.thoi_luong) || 0, m.loai === 'anh');
        const dinh = diemDinh(this.tl, this.ui.dau_phat, [cid]);
        const t0 = this._t(e.clientX);
        const ngDinh = DINH_PX / this.px;
        const minDai = 1 / (Number((ctx.du.thong_so || {}).fps) || 30);
        this._keo = { cid, kieu, daDi: false, moi: null };
        el.setPointerCapture(e.pointerId);
        el.classList.add('dang-keo');

        const di = (ev) => {
            const dt = this._t(ev.clientX) - t0;
            if (!this._keo.daDi && Math.abs(dt * this.px) < 3) return;
            this._keo.daDi = true;
            const dinhOk = this.ui.bat_dinh && !ev.shiftKey;
            let moi;
            if (kieu === 'doi') {
                let bd = Math.max(0, goc.bd + dt);
                if (dinhOk) {
                    const a = hutDinh(bd, dinh, ngDinh), b = hutDinh(bd + (goc.kt - goc.bd), dinh, ngDinh) - (goc.kt - goc.bd);
                    bd = Math.abs(a - bd) <= Math.abs(b - bd) ? a : b;
                }
                // Kéo lên/xuống sang track cùng loại.
                const duoi = document.elementsFromPoint(ev.clientX, ev.clientY).find((x) => x.classList && x.classList.contains('tl-track'));
                const trMoi = duoi && this.tl.tracks.find((t) => t.id === duoi.dataset.track);
                const track = trMoi && trMoi.loai === tr.loai && !trMoi.khoa ? trMoi.id : c.track;
                const dai = goc.kt - goc.bd;
                const hong = chongClip(this.tl, track, bd, bd + dai, [cid]);
                moi = { bat_dau: bd, track, hong };
                el.style.left = `${bd * this.px}px`;
                const hang = this.noi.querySelector(`.tl-track[data-track="${track}"]`);
                if (hang && el.parentElement !== hang) hang.appendChild(el);
            } else if (kieu === 'trai') {
                let bd = Math.min(Math.max(goc.bd + dt, gh.sanTrai), goc.kt - minDai);
                if (dinhOk) bd = Math.min(Math.max(hutDinh(bd, dinh, ngDinh), gh.sanTrai), goc.kt - minDai);
                moi = { bat_dau: bd, vao: Math.max(0, goc.vao + (bd - goc.bd) * toc) };
                el.style.left = `${bd * this.px}px`;
                el.style.width = `${(goc.kt - bd) * this.px}px`;
            } else {
                let kt = Math.max(Math.min(goc.kt + dt, gh.tranPhai), goc.bd + minDai);
                if (dinhOk) kt = Math.max(Math.min(hutDinh(kt, dinh, ngDinh), gh.tranPhai), goc.bd + minDai);
                moi = { ra: goc.ra + (kt - goc.kt) * toc };
                el.style.width = `${(kt - goc.bd) * this.px}px`;
            }
            el.classList.toggle('hong', !!moi.hong);
            this._keo.moi = moi;
            this._veNhanKeo(el, moi, goc);
        };
        const xong = () => {
            el.removeEventListener('pointermove', di);
            el.removeEventListener('pointerup', xong);
            el.removeEventListener('pointercancel', xong);
            const { moi, daDi } = this._keo;
            this._keo = null;
            if (!daDi || !moi) { this.ve(); return; }
            if (moi.hong) { toast('Chỗ đó đang có clip khác — thả vào khoảng trống.', 'warn', 2500); this.ve(); return; }
            const ops = [];
            const lamTron = (v) => Math.round(v * 1000) / 1000;
            for (const k of ['bat_dau', 'vao', 'ra', 'track']) {
                if (moi[k] === undefined) continue;
                const v = k === 'track' ? moi[k] : lamTron(moi[k]);
                if (v !== c[k]) {
                    ops.push(tao.dat(this.tl, ['clips', { id: cid }, k], v));
                    if ((kieu === 'doi' || this.ui.lien_ket_am_thanh) && k !== 'track' && this.ui.dang_chon.length > 1) {
                        const delta = lamTron(v - c[k]);
                        this.ui.dang_chon.forEach(otherId => {
                            if (otherId === cid) return;
                            const oc = this.tl.clips.find(x => x.id === otherId);
                            if (oc) {
                                const trOther = this.tl.tracks.find(t => t.id === oc.track);
                                if (!trOther || !trOther.khoa) {
                                    ops.push(tao.dat(this.tl, ['clips', { id: otherId }, k], lamTron((Number(oc[k]) || 0) + delta)));
                                }
                            }
                        });
                    }
                }
            }
            if (!ops.length) { this.ve(); return; }
            const ten = kieu === 'doi' ? 'Dời clip' : 'Tỉa clip';
            if (!ctx.sua(ten, ops)) this.ve();
        };
        el.addEventListener('pointermove', di);
        el.addEventListener('pointerup', xong);
        el.addEventListener('pointercancel', xong);
    }

    _veNhanKeo(el, moi, goc) {
        let n = el.querySelector('.nhan-keo');
        if (!n) { n = document.createElement('span'); n.className = 'nhan-keo so'; el.appendChild(n); }
        const bd = moi.bat_dau ?? goc.bd;
        const kt = moi.ra !== undefined ? goc.kt + (moi.ra - goc.ra) : bd + (goc.kt - goc.bd) - (moi.vao !== undefined ? 0 : 0);
        n.textContent = moi.ra !== undefined ? `dài ${(kt - goc.bd).toFixed(2)}s`
            : moi.vao !== undefined ? `dài ${(goc.kt - bd).toFixed(2)}s` : fmtThoiGian(bd, true, Number((this.ctx.du.thong_so || {}).fps) || 30);
    }

    // ------------------------------------------------------------ thao tác
    datZoom(z, neo) {
        z = Math.max(0, Math.min(1, z));
        const r = this.cuon.getBoundingClientRect();
        const x = neo ? neo.x : r.width / 2;
        const t = neo ? neo.t : (this.cuon.scrollLeft + x) / this.px;
        this.ui.zoom_timeline = Math.round(z * 1000) / 1000;
        this.ve();
        this.cuon.scrollLeft = Math.max(0, t * this.px - x);
        this.ctx.luuUi();
    }

    vuaKhung() {
        const dai = Math.max(10, thoiLuong(this.tl) * 1.05);
        const rong = this.cuon.clientWidth - 20;
        this.datZoom(Math.log2(Math.max(1e-6, rong / dai / 5)) / 7);
        this.cuon.scrollLeft = 0;
    }

    chonClip(cid, them = false) {
        const ds = this.ui.dang_chon || [];
        let chonMoi = !cid ? [] : them ? (ds.includes(cid) ? ds.filter((x) => x !== cid) : [...ds, cid]) : [cid];
        if (this.ui.chuyen_canh_chon) { this.ui.chuyen_canh_chon = null; this.ve(); }
        if (this.ui.lien_ket_am_thanh && chonMoi.length > 0) {
            chonMoi = moRongNhom(this.tl, chonMoi);
        }
        this.ui.dang_chon = chonMoi;
        this.ctx.chon.clip = this.ui.dang_chon[this.ui.dang_chon.length - 1] || null;
        this.ctx.luuUi();
        this.ctx.bus.emit('chon');
    }

    themMedia(m, trackId, t) {
        if (m.loai === 'phu_de') { this.ctx.bus.emit('nhap_srt_media', m); return; }
        const loaiTrack = m.loai === 'audio' ? 'audio' : 'video';
        let tr = this.tl.tracks.find((x) => x.id === trackId);
        if (!tr || tr.loai !== loaiTrack) tr = this.tl.tracks.find((x) => x.loai === loaiTrack);
        if (!tr) { toast('Không có track phù hợp.', 'warn'); return; }
        if (tr.khoa) { toast(`Track ${tr.id} đang khoá.`, 'warn'); return; }
        const dai = m.loai === 'anh' ? 5 : Number(m.thoi_luong) || 0;
        if (!dai) { toast('Media chưa có thời lượng (đang đọc thông số?).', 'warn'); return; }
        const cuoi = this.tl.clips.filter((c) => c.track === tr.id).reduce((a, c) => Math.max(a, ketThucClip(c)), 0);
        let tt = t == null ? cuoi : t;
        if (t != null && this.ui.bat_dinh) tt = hutDinh(tt, diemDinh(this.tl, this.ui.dau_phat), (DINH_PX * 2) / this.px);
        const bd = choTrong(this.tl, tr.id, tt, dai);
        const cid = idClipMoi(this.tl);
        const clip = {
            id: cid, track: tr.id, media: m.id, bat_dau: bd, vao: 0, ra: Math.round(dai * 1000) / 1000,
            toc_do: 1, am_luong: 1, nhac_nen_giam: 0,
            bien_doi: { x: 0.5, y: 0.5, ti_le: 1, xoay: 0 },
            cat_khung: { trai: 0, phai: 0, tren: 0, duoi: 0, mem: 0 },
            hien_thi: { do_mo: 1, hoa_tron: 'normal', bo_goc: 0 }, hieu_ung: [], keyframes: {},
        };
        if (this.ctx.sua(`Thêm ${m.ten} vào ${tr.id}`, [tao.them(this.tl, ['clips'], clip)])) this.chonClip(cid);
    }

    /* Cắt tại đầu phát: clip đang chọn nằm dưới đầu phát; không chọn gì thì mọi clip dưới đầu phát. */
    catTaiDauPhat() {
        const t = this.ui.dau_phat;
        const chon = (this.ui.dang_chon || []).filter((id) => this.tl.clips.some((c) => c.id === id && !c.loai));
        const khoa = new Set(this.tl.tracks.filter((x) => x.khoa).map((x) => x.id));
        let ids = (chon.length ? chon : this.tl.tracks.map((tr) => (clipTai(this.tl, tr.id, t) || {}).id).filter(Boolean))
            .filter((id) => !khoa.has(this.tl.clips.find((c) => c.id === id).track));
        if (this.ui.lien_ket_am_thanh) ids = moRongNhom(this.tl, ids);
        const ops = [];
        const nhap = JSON.parse(JSON.stringify(this.tl));
        const moi = [];
        const lienKetCuMoi = {};
        for (const id of ids) {
            const idMoi = idClipMoi(nhap);
            const o = opsTach(nhap, id, t, idMoi);
            if (!o) continue;
            const c = nhap.clips.find((x) => x.id === id);
            const newClipOp = o.find(x => x.op === 'them' && x.path[0] === 'clips');
            if (newClipOp && c.lien_ket) {
                if (!lienKetCuMoi[c.lien_ket]) lienKetCuMoi[c.lien_ket] = idNhomMoi(nhap);
                newClipOp.gia_tri.lien_ket = lienKetCuMoi[c.lien_ket];
            }
            o.forEach((op) => {
                ops.push(op);
                if (op.op === 'dat') nhap.clips.find((x) => x.id === id).ra = op.moi;
                else nhap.clips.splice(op.vi_tri, 0, op.gia_tri);
            });
            moi.push(idMoi);
        }
        if (!ops.length) { toast('Đầu phát không nằm trong clip nào để cắt.', 'info', 2000); return; }
        ids = moi;
        if (this.ctx.sua(moi.length > 1 ? `Cắt ${moi.length} clip` : 'Cắt clip', ops)) this.chonClip(ids[0]);
    }

    async chiaDeu(cid) {
        const strN = await hoi({ tieuDe: 'Chia đều thành N đoạn', o: { giaTri: "2", goiY: 'Ví dụ: 3' }, nut: 'Chia', noiDung: 'Nhập số đoạn (2–100):' });
        if (!strN) return;
        const n = parseInt(strN, 10);
        if (isNaN(n) || n < 2 || n > 100) {
            toast('Vui lòng nhập số từ 2 đến 100.', 'info');
            return;
        }

        const { opsChiaDeu } = await import('./store.js');
        const ops = opsChiaDeu(this.tl, cid, n);
        
        if (!ops) {
            toast('Không thể chia (đoạn quá ngắn hoặc lỗi).', 'info');
            return;
        }

        this.ctx.sua(`Chia đều thành ${n} đoạn`, ops);
    }

    _donLienKet(dsXoa) {
        const lienKetBiXoa = new Set();
        dsXoa.forEach(id => {
            const c = this.tl.clips.find(x => x.id === id);
            if (c && c.lien_ket) lienKetBiXoa.add(c.lien_ket);
        });
        const conLaiTheoNhom = {};
        this.tl.clips.forEach(c => {
            if (c.lien_ket && lienKetBiXoa.has(c.lien_ket) && !dsXoa.includes(c.id)) {
                conLaiTheoNhom[c.lien_ket] = (conLaiTheoNhom[c.lien_ket] || 0) + 1;
            }
        });
        const ops = [];
        this.tl.clips.forEach(c => {
            if (c.lien_ket && (conLaiTheoNhom[c.lien_ket] || 0) < 2 && !dsXoa.includes(c.id)) {
                ops.push(tao.dat(this.tl, ['clips', { id: c.id }, 'lien_ket'], undefined));
            }
        });
        return ops;
    }

    /* Chọn một chuyển cảnh (bỏ chọn clip) — bảng thuộc tính hiện kiểu + thời lượng, Delete xoá nó. */
    chonChuyenCanh(id) {
        this.ui.dang_chon = [];
        this.ctx.chon.clip = null;
        this.ui.chuyen_canh_chon = id;
        this.ctx.luuUi();
        this.ve();
        this.ctx.bus.emit('chon');
    }

    /* Điểm nối (hết clip trước = đầu clip sau) trên track nền gần clientX nhất, trong ±12 px. */
    _diemNoiGan(clientX) {
        const nen = (trackVideoTuDuoiLen(this.tl)[0] || {}).id;
        if (!nen) return null;
        const t = this._t(clientX);
        const cac = this.tl.clips.filter((c) => c.track === nen).sort((a, b) => Number(a.bat_dau || 0) - Number(b.bat_dau || 0));
        let tot = null;
        for (let i = 0; i + 1 < cac.length; i += 1) {
            const kt = ketThucClip(cac[i]);
            if (Math.abs(kt - Number(cac[i + 1].bat_dau || 0)) > 0.05) continue;
            const lech = Math.abs(kt - t) * this.px;
            if (lech <= 12 && (!tot || lech < tot.lech)) tot = { truoc: cac[i].id, sau: cac[i + 1].id, t: kt, track: nen, lech };
        }
        return tot;
    }

    xoaDangChon() {
        const ds = (this.ui.dang_chon || []).filter((id) => this.tl.clips.some((c) => c.id === id));
        const cc = !ds.length && (this.tl.chuyen_canh || []).find((x) => x.id === this.ui.chuyen_canh_chon);
        if (cc) {
            if (this.ctx.sua('Xoá chuyển cảnh', opsXoaChuyenCanh(this.tl, cc.truoc, cc.sau))) this.chonChuyenCanh(null);
            return;
        }
        if (!ds.length) return;
        const khoa = ds.filter((id) => {
            const c = this.tl.clips.find((x) => x.id === id);
            const tr = this.tl.tracks.find((t) => t.id === c.track);
            return tr && tr.khoa;
        });
        if (khoa.length) { toast('Clip nằm trên track đang khoá.', 'warn'); return; }
        const theoViTri = ds.map((id) => [id, this.tl.clips.findIndex((c) => c.id === id)]).sort((a, b) => b[1] - a[1]);
        const ops = theoViTri.map(([id]) => tao.xoaTheoId(this.tl, ['clips'], id));
        ops.push(...this._donLienKet(ds));
        if (this.ctx.sua(ds.length > 1 ? `Xoá ${ds.length} clip` : 'Xoá clip', ops)) this.chonClip(null);
    }

    khepKhoangDangChon() {
        const trId = this.ctx.chon.clip ? this.tl.clips.find((c) => c.id === this.ctx.chon.clip)?.track : null;
        if (!trId) { toast('Chọn một clip để khép khoảng trên track đó.', 'info'); return; }
        const ops = opsKhepKhoang(this.tl, trId);
        if (ops.length) this.ctx.sua('Khép khoảng trống', ops);
    }

    xoaGonDangChon() {
        const ds = (this.ui.dang_chon || []).filter((id) => this.tl.clips.some((c) => c.id === id));
        if (!ds.length) return;
        const khoa = ds.filter((id) => {
            const c = this.tl.clips.find((x) => x.id === id);
            const tr = this.tl.tracks.find((t) => t.id === c.track);
            return tr && tr.khoa;
        });
        if (khoa.length) { toast('Clip nằm trên track đang khoá.', 'warn'); return; }
        const ops = opsXoaGon(this.tl, ds);
        ops.push(...this._donLienKet(ds));
        if (this.ctx.sua(ds.length > 1 ? `Xoá gợn ${ds.length} clip` : 'Xoá gợn', ops)) this.chonClip(null);
    }

    tiaToiDauPhat(phia, gon) {
        const t = this.ui.dau_phat;
        const chon = (this.ui.dang_chon || []).filter((id) => this.tl.clips.some((c) => c.id === id && !c.loai));
        const khoa = new Set(this.tl.tracks.filter((x) => x.khoa).map((x) => x.id));
        const ids = (chon.length ? chon : this.tl.tracks.map((tr) => (clipTai(this.tl, tr.id, t) || {}).id).filter(Boolean))
            .filter((id) => !khoa.has(this.tl.clips.find((c) => c.id === id).track));
        if (!ids.length) { toast('Không có clip nào dưới đầu phát.', 'info'); return; }
        const ops = opsTiaToiDauPhat(this.tl, ids, t, phia, gon);
        if (ops.length) this.ctx.sua(phia === 'truoc' ? 'Tỉa đầu clip' : 'Tỉa cuối clip', ops);
    }

    chonTatCa() {
        const khoa = new Set(this.tl.tracks.filter((x) => x.khoa).map((x) => x.id));
        this.ui.dang_chon = this.tl.clips.filter((c) => !khoa.has(c.track)).map((c) => c.id);
        this.ctx.chon.clip = this.ui.dang_chon[this.ui.dang_chon.length - 1] || null;
        this.ctx.luuUi();
        this.ctx.bus.emit('chon');
    }

    nhayDiemCat(huong) {
        const dinh = diemDinh(this.tl, -1).sort((a, b) => a - b);
        const t = this.ui.dau_phat;
        let tim;
        if (huong === 'truoc') tim = dinh.slice().reverse().find((d) => d < t - 0.001);
        else tim = dinh.find((d) => d > t + 0.001);
        if (tim != null) this.datDauPhat(tim, false, true);
    }

    saoChep() {
        const ds = (this.ui.dang_chon || []).filter((id) => this.tl.clips.some((c) => c.id === id));
        if (!ds.length) return false;
        const clips = ds.map((id) => JSON.parse(JSON.stringify(this.tl.clips.find((c) => c.id === id))));
        const minBd = Math.min(...clips.map((c) => Number(c.bat_dau || 0)));
        this._boNhoTam = { clips, minBd };
        toast(`Đã chép ${ds.length} clip.`);
        return true;
    }

    dan(tai = null, idTrackDan = null) {
        if (!this._boNhoTam) return;
        const { clips, minBd } = this._boNhoTam;
        const ops = [];
        const idsMoi = idMoiNhieu(this.tl, clips.length);
        const gocLenMoi = Object.fromEntries(clips.map((c, i) => [c.id, idsMoi[i]]));
        const t = tai != null ? tai : this.ui.dau_phat;
        const nhap = JSON.parse(JSON.stringify(this.tl));
        const lienKetCuMoi = {};

        clips.forEach((c, i) => {
            const m = JSON.parse(JSON.stringify(c));
            m.id = idsMoi[i];
            if (m.lien_ket) {
                if (!lienKetCuMoi[m.lien_ket]) lienKetCuMoi[m.lien_ket] = idNhomMoi(nhap);
                m.lien_ket = lienKetCuMoi[m.lien_ket];
            }
            const bdCu = Number(c.bat_dau || 0);
            const rOffset = bdCu - minBd;
            
            // Nếu là neo theo media:
            if (c.loai === 'phu_de' || c.loai === 'che_phu_de') {
                // xoá dòng gán tu_media sai logic
            } else {
                let d = t + rOffset;
                let trId = idTrackDan || c.track;
                const tr = nhap.tracks.find((x) => x.id === trId);
                if (tr && tr.khoa) trId = c.track; // track khoá thì về track gốc
                m.track = trId;
                const dai = ketThucClip(c) - bdCu;
                m.bat_dau = choTrong(nhap, trId, d, dai);
            }
            ops.push(tao.them(this.tl, ['clips'], m));
            nhap.clips.push(m);
        });
        if (this.ctx.sua(`Dán ${clips.length} clip`, ops)) {
            this.ui.dang_chon = idsMoi;
            this.ctx.chon.clip = idsMoi[idsMoi.length - 1];
            this.ctx.luuUi();
            this.ctx.bus.emit('chon');
        }
    }

    nhanDoi() {
        const chon = (this.ui.dang_chon || []).filter(id => this.tl.clips.some(c => c.id === id));
        if (!chon.length) return;
        const res = opsNhanDoi(this.tl, chon);
        if (this.ctx.sua(`Nhân đôi ${chon.length} clip`, res.ops)) {
            this.ui.dang_chon = res.idsMoi;
            this.ctx.chon.clip = res.idsMoi[res.idsMoi.length - 1];
            this.ctx.luuUi();
            this.ctx.bus.emit('chon');
        }
    }

    danhDau() {
        const t = Math.round(this.ui.dau_phat * 1000) / 1000;
        const danhDau = this.tl.danh_dau || [];
        const daCo = danhDau.find((d) => Math.abs(d.t - t) < 0.01);
        if (daCo) return; // có thể hiện UI đổi tên
        const cacDd = (this.tl.danh_dau || []).map(d => /^dd_(\d+)$/.exec(d.id || '')).filter(Boolean).map(m => Number(m[1]));
        const id = `dd_${(cacDd.length ? Math.max(...cacDd) : 0) + 1}`;
        this.ctx.sua('Thêm đánh dấu', [tao.them(this.tl, ['danh_dau'], { id, t, ten: 'Điểm' })]);
    }

    menuVungTrong(trId, t, x, y) {
        document.querySelectorAll('.menu').forEach((mm) => mm.remove());
        const html = `
            ${this._boNhoTam ? `<button data-l="dan">📋 Dán vào khoảng trống</button>` : ''}
            ${trId ? `<button data-l="khep">⇤ Khép khoảng trống track này</button>` : ''}
        `.trim();
        if (!html) return;
        const menu = document.createElement('div');
        menu.className = 'menu';
        menu.innerHTML = html;
        document.body.appendChild(menu);
        const r = menu.getBoundingClientRect();
        menu.style.left = `${Math.min(x, innerWidth - r.width - 8)}px`;
        menu.style.top = `${Math.min(y, innerHeight - r.height - 8)}px`;
        menu.addEventListener('click', (e) => {
            const l = e.target.closest('[data-l]');
            if (!l) return;
            menu.remove();
            if (l.dataset.l === 'dan') this.dan(t, trId);
            if (l.dataset.l === 'khep') {
                const ops = opsKhepKhoang(this.tl, trId, t);
                if (ops.length) this.ctx.sua('Khép khoảng trống', ops);
            }
        });
        setTimeout(() => document.addEventListener('click', () => menu.remove(), { once: true }), 0);
    }

    menuClip(cid, x, y) {
        document.querySelectorAll('.menu').forEach((mm) => mm.remove());
        const c = this.tl.clips.find(x => x.id === cid);
        const m = c ? this.ctx.media.find(x => x.id === c.media) : null;
        const tr = c ? this.tl.tracks.find(t => t.id === c.track) : null;
        
        const dangChon = this.ui.dang_chon || [];
        const mediaDict = Object.fromEntries(this.ctx.media.map((m) => [m.id, m]));
        const muc = mucMenuChoClip(this.tl, mediaDict, cid, dangChon, !!this._boNhoTam);
        
        const menu = document.createElement('div');
        menu.className = 'menu';
        menu.innerHTML = muc.map(m => {
            if (m.separator) return '<hr>';
            return `<button data-l="${esc(m.id)}"${m.v ? ` data-v="${m.v}"` : ''}>${esc(m.text)}</button>`;
        }).join('');
        document.body.appendChild(menu);
        const r = menu.getBoundingClientRect();
        menu.style.left = `${Math.min(x, innerWidth - r.width - 8)}px`;
        menu.style.top = `${Math.min(y, innerHeight - r.height - 8)}px`;
        menu.addEventListener('click', (e) => {
            const l = e.target.closest('[data-l]');
            if (!l) return;
            menu.remove();
            if (l.dataset.l === 'cat-dau') this.catTaiDauPhat();
            if (l.dataset.l === 'chep') this.saoChep();
            if (l.dataset.l === 'cat') { if (this.saoChep()) this.xoaDangChon(); }
            if (l.dataset.l === 'dan') this.dan();
            if (l.dataset.l === 'nhan-doi') this.nhanDoi();
            if (l.dataset.l === 'xoa') this.xoaDangChon();
            if (l.dataset.l === 'chia-deu') this.chiaDeu(cid);
            if (l.dataset.l === 'xoa-gon') this.xoaGonDangChon();
            if (l.dataset.l === 'tach-am') {
                import('./store.js').then(s => {
                    const lenh = s.opsTachAm(this.tl, cid);
                    if (lenh) this.ctx.sua('Tách âm thanh', lenh.ops);
                });
            }
            if (l.dataset.l === 'lien-ket') {
                const nhomId = idNhomMoi(this.tl);
                const ops = dangChon.map(id => tao.dat(this.tl, ['clips', { id }, 'lien_ket'], nhomId));
                this.ctx.sua('Liên kết clip', ops);
            }
            if (l.dataset.l === 'bo-lien-ket') {
                const ops = dangChon.map(id => tao.dat(this.tl, ['clips', { id }, 'lien_ket'], undefined));
                this.ctx.sua('Bỏ liên kết', ops);
            }
            if (l.dataset.l === 'tieng') {
                const c = this.tl.clips.find(x => x.id === cid);
                this.ctx.sua('Tiếng', [tao.dat(this.tl, ['clips', { id: cid }, 'tat_am'], !c.tat_am)]);
            }
            if (l.dataset.l === 'toc') this.ctx.sua('Tốc độ', [tao.dat(this.tl, ['clips', { id: cid }, 'toc_do'], Number(l.dataset.v))]);
        });
        setTimeout(() => document.addEventListener('click', () => menu.remove(), { once: true }), 0);
    }

    // ------------------------------------------------------------ vẽ
    _veCongCu() {
        const cc = this.el.querySelector('.tl-cong-cu');
        cc.querySelector('[data-l=hoan-tac]').disabled = !this.ctx.store.hoanTac.length || this.ctx.store.chiDoc;
        cc.querySelector('[data-l=lam-lai]').disabled = !this.ctx.store.lamLai.length || this.ctx.store.chiDoc;
        cc.querySelector('[data-l=xoa]').disabled = !(this.ui.dang_chon || []).length;
        cc.querySelector('[data-l=bat-dinh]').classList.toggle('bat', !!this.ui.bat_dinh);
        cc.querySelector('[data-l=lien-ket]').classList.toggle('bat', !!this.ui.lien_ket_am_thanh);
        if (document.activeElement !== this.zoom) this.zoom.value = this.ui.zoom_timeline;
    }

    /* Dải khung hình: ô đúng tỉ lệ khung video, mỗi ô lấy khung gần thời điểm của nó nhất. */
    _dai(m, c, rongPx) {
        const pid = encodeURIComponent(this.ctx.id);
        const n = Number(m.dai_hinh) || 0, dai = Number(m.thoi_luong) || 0;
        if (!n || !dai || !m.rong || !m.cao) return '';
        const fw = 2 * Math.round((CAO_SPRITE * m.rong / m.cao) / 2);   // scale=-2:54 → rộng chẵn
        const k = H_KHUNG / CAO_SPRITE;
        const oW = fw * k;
        const so = Math.min(300, Math.ceil(rongPx / oW));
        const toc = Number(c.toc_do) || 1;
        const url = `/api/du-an/${pid}/media/${m.id}/dai-hinh?v=${esc(m.nhap_luc)}`;
        let html = '';
        for (let i = 0; i < so; i += 1) {
            const tm = (Number(c.vao) || 0) + ((i + 0.5) * oW / this.px) * toc;
            const khung = Math.max(0, Math.min(n - 1, Math.floor((tm / dai) * n)));
            html += `<i style="left:${i * oW}px;width:${oW}px;background-image:url('${url}');`
                + `background-size:${n * oW}px ${H_KHUNG}px;background-position:${-khung * oW}px 0"></i>`;
        }
        return `<div class="dai-khung">${html}</div>`;
    }

    ve() {
        const tl = this.tl, px = this.px;
        const tong = thoiLuong(tl);
        const rongNhin = Math.max(200, this.cuon.clientWidth || 800);
        const rong = Math.max(rongNhin, (tong + 30) * px);
        this.noi.style.width = `${rong}px`;

        const buoc = BUOC_NHAN.find((b) => b * px >= 90) || BUOC_NHAN[BUOC_NHAN.length - 1];
        const nho = buoc / 5;
        let thuoc = '';
        const het = rong / px;
        for (let i = 0, t = 0; t <= het; i += 1, t = i * nho) {
            const lon = i % 5 === 0;
            thuoc += `<i class="${lon ? 'lon' : ''}" style="left:${t * px}px"></i>`;
            if (lon) thuoc += `<span style="left:${t * px}px">${nhanGio(t, buoc)}</span>`;
        }
        
        const danhDau = this.tl.danh_dau || [];
        for (const d of danhDau) {
            thuoc += `<div class="danh-dau" data-dd="${esc(d.id)}" title="${esc(d.ten)}" style="position:absolute;bottom:0;left:${d.t * px - 6}px;width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:8px solid #ffeb3b;cursor:pointer;z-index:5;"></div>`;
        }

        const media = Object.fromEntries(this.ctx.media.map((m) => [m.id, m]));
        const pid = encodeURIComponent(this.ctx.id);
        // Chuyển cảnh chỉ nằm trên track nền (track video dưới cùng) — vẽ ⧓ ngay điểm nối.
        const nen = (trackVideoTuDuoiLen(tl)[0] || {}).id;
        const ccHtml = (tl.chuyen_canh || []).map((cc) => {
            const truoc = tl.clips.find((c) => c.id === cc.truoc);
            if (!truoc) return '';
            return `<b class="cc-diem ${this.ui.chuyen_canh_chon === cc.id ? 'chon' : ''}" data-cc="${esc(cc.id)}"
                style="left:${ketThucClip(truoc) * px}px" title="Chuyển cảnh ${esc(cc.loai)} · ${Number(cc.dai).toFixed(2)}s">⧓</b>`;
        }).join('');
        const tracks = tl.tracks.map((tr) => {
            if (tr.loai === 'phu_de' || tr.loai === 'lop_phu') {
                return `<div class="tl-track ${tr.an ? 'an-track' : ''} ${tr.khoa ? 'khoa-track' : ''}" data-track="${esc(tr.id)}">${this._veNeo(tr)}</div>`;
            }
            const clips = tl.clips.filter((c) => c.track === tr.id).map((c) => {
                const m = media[c.media] || {};
                const bd = Number(c.bat_dau) || 0, kt = ketThucClip(c);
                const toc = Number(c.toc_do) || 1;
                const rongClip = Math.max(2, (kt - bd) * px);
                let nen = '', trong = '';
                const dai = Number(m.thoi_luong) || 0;
                if (tr.loai === 'video' && m.loai === 'video') trong = this._dai(m, c, rongClip);
                if (tr.loai === 'video' && m.loai === 'anh' && m.thumb) {
                    nen = `background-image:url('/api/du-an/${pid}/media/${m.id}/thumb?v=${esc(m.nhap_luc)}');background-size:auto ${H_KHUNG}px;background-repeat:repeat-x;background-position:0 bottom;`;
                } else if (tr.loai === 'audio' && m.song_am && dai) {
                    nen = `background-image:url('/api/du-an/${pid}/media/${m.id}/song-am?v=${esc(m.nhap_luc)}');`
                        + `background-size:${dai * px / toc}px 80%;background-position:${-(Number(c.vao) || 0) * px / toc}px center;background-repeat:no-repeat;`;
                }
                const nhan = nhanClip(c, m);
                const iconLk = c.lien_ket ? '<span style="font-size:10px;margin-right:4px">🔗</span>' : '';
                const cham = viTriKeyframes(c, px).map(x => `<i style="position:absolute;bottom:0;left:${x-4}px;color:#00ffff;font-size:8px;line-height:8px;pointer-events:none">◆</i>`).join('');
                return `<div class="clip ${LOP[tr.loai] || 'v'} ${(this.ui.dang_chon || []).includes(c.id) ? 'chon' : ''}"
                    data-id="${esc(c.id)}" style="left:${bd * px}px;width:${rongClip}px;${nen}"
                    title="${esc(nhan)} · ${fmtThoiGian(bd)} → ${fmtThoiGian(kt)}${c.media && !media[c.media] ? ' · MẤT MEDIA' : ''}">
                    ${trong}<span class="nhan-clip">${iconLk}${esc(nhan)}</span>${cham}<b class="mep trai"></b><b class="mep phai"></b></div>`;
            }).join('');
            return `<div class="tl-track ${tr.an ? 'an-track' : ''} ${tr.khoa ? 'khoa-track' : ''}" data-track="${esc(tr.id)}">${clips}${tr.id === nen ? ccHtml : ''}</div>`;
        }).join('');
        
        let vungXuat = '';
        if (tl.vung_vao != null || tl.vung_ra != null) {
            const v = tl.vung_vao || 0;
            const r = tl.vung_ra ?? tong;
            vungXuat = `<div class="vung-xuat" style="left:${v * px}px;width:${(r - v) * px}px" title="Vùng xuất (Nhấn [ và ] để đặt, Alt+[ để xoá)"></div>`;
        }
        
        this.noi.innerHTML = `<div class="thuoc" style="width:${rong}px">${thuoc}</div>${vungXuat}${tracks}
            <div class="dau-phat" data-khu="dp"></div>
            ${tl.clips.length ? '' : '<div class="tl-trong">Kéo media từ bảng Tệp phương tiện thả vào đây.</div>'}`;

        this.dau.innerHTML = tl.tracks.map((tr) => `<div class="tl-dau-track" data-track="${esc(tr.id)}">
            <b>${esc(tr.ten || tr.id)}</b>
            ${tr.loai === 'video' || tr.loai === 'audio' ? `<button class="nut-icon ${tr.tat_tieng ? 'bat' : ''}" data-bat="tat_tieng" title="${tr.tat_tieng ? 'Bật tiếng' : 'Tắt tiếng'}">${tr.tat_tieng ? '🔇' : '🔊'}</button>` : ''}
            ${tr.loai !== 'audio' ? `<button class="nut-icon ${tr.an ? 'bat' : ''}" data-bat="an" title="${tr.an ? 'Hiện' : 'Ẩn'}">${tr.an ? '🙈' : '👁'}</button>` : ''}
            <button class="nut-icon ${tr.khoa ? 'bat' : ''}" data-bat="khoa" title="${tr.khoa ? 'Mở khoá' : 'Khoá'}">${tr.khoa ? '🔒' : '🔓'}</button>
            <button class="nut-icon" data-hd="xoa-track" title="Xoá track">✕</button>
        </div>`).join('') + `<div class="tl-dau-track" style="justify-content:center;gap:4px">
            <button class="nut" data-hd="them-v" title="Thêm track Video">+ V</button>
            <button class="nut" data-hd="them-a" title="Thêm track Audio">+ A</button>
        </div>`;

        this._veDauPhat();
        this._veCongCu();
        $('gioTong').textContent = fmtThoiGian(tong, true, Number((this.ctx.du.thong_so || {}).fps) || 30);

        if (!this._daKhoiPhucCuon) {
            const c = this.ui.cuon_timeline || {};
            requestAnimationFrame(() => {
                this.cuon.scrollLeft = c.x || 0;
                this.cuon.scrollTop = c.y || 0;
                this._daKhoiPhucCuon = true;
            });
        }
    }

    /* Câu phụ đề / vùng che: vẽ MỖI LẦN HIỆN (một câu neo media có thể hiện ở 2 clip sau khi cắt). */
    _veNeo(tr) {
        const px = this.px;
        const chon = this.ui.dang_chon || [];
        return this.tl.clips.filter((c) => c.track === tr.id).map((c) => hienThiNeo(this.tl, c).map((k) => {
            const nhan = nhanClip(c, null);
            return `<div class="clip ${tr.loai === 'phu_de' ? 's' : 'o'} neo ${chon.includes(c.id) ? 'chon' : ''}" data-id="${esc(c.id)}"
                data-vid="${esc(k.clip || '')}" data-bd="${k.bd}" data-kt="${k.kt}"
                style="left:${k.bd * px}px;width:${Math.max(3, (k.kt - k.bd) * px)}px" title="${esc(nhan)}">
                <span class="nhan-clip">${esc(nhan)}</span><b class="mep trai"></b><b class="mep phai"></b></div>`;
        }).join('')).join('');
    }

    /* Kéo câu phụ đề / vùng che: dời hoặc tỉa theo giờ timeline, ghi lại về giờ media qua clip chứa nó. */
    _keoNeo(e, el) {
        const cid = el.dataset.id;
        const c = this.tl.clips.find((x) => x.id === cid);
        const tr = c && this.tl.tracks.find((t) => t.id === c.track);
        if (!(this.ui.dang_chon || []).includes(cid) || e.shiftKey || e.ctrlKey) this.chonClip(cid, e.shiftKey || e.ctrlKey);
        if (!c || (tr && tr.khoa) || this.ctx.store.chiDoc) return;
        const r = el.getBoundingClientRect();
        const kieu = e.clientX - r.left < MEP ? 'trai' : r.right - e.clientX < MEP ? 'phai' : 'doi';
        const bd0 = Number(el.dataset.bd), kt0 = Number(el.dataset.kt);
        const vid = el.dataset.vid || '';
        const vclip = vid && this.tl.clips.find((x) => x.id === vid);
        const san = vclip ? Number(vclip.bat_dau) : 0;
        const tran = vclip ? ketThucClip(vclip) : Infinity;
        const t0 = this._t(e.clientX);
        const dinh = diemDinh(this.tl, this.ui.dau_phat, [cid]);
        const ng = DINH_PX / this.px;
        this._keo = { cid, daDi: false, moi: null };
        el.setPointerCapture(e.pointerId);
        el.classList.add('dang-keo');
        const di = (ev) => {
            const dt = this._t(ev.clientX) - t0;
            if (!this._keo.daDi && Math.abs(dt * this.px) < 3) return;
            this._keo.daDi = true;
            const hut = (x) => (this.ui.bat_dinh && !ev.shiftKey ? hutDinh(x, dinh, ng) : x);
            let bd = bd0, kt = kt0;
            if (kieu === 'doi') {
                bd = Math.min(Math.max(hut(bd0 + dt), san), tran - (kt0 - bd0));
                kt = bd + (kt0 - bd0);
            } else if (kieu === 'trai') bd = Math.min(Math.max(hut(bd0 + dt), san), kt0 - 0.1);
            else kt = Math.max(Math.min(hut(kt0 + dt), tran), bd0 + 0.1);
            this._keo.moi = { bd, kt };
            el.style.left = `${bd * this.px}px`;
            el.style.width = `${(kt - bd) * this.px}px`;
        };
        const xong = () => {
            el.removeEventListener('pointermove', di);
            el.removeEventListener('pointerup', xong);
            el.removeEventListener('pointercancel', xong);
            const { moi, daDi } = this._keo;
            this._keo = null;
            if (!daDi || !moi) { this.ve(); return; }
            const ten = c.loai === 'che_phu_de' ? 'Chỉnh vùng che' : c.loai === 'chu' ? 'Chỉnh chữ' : c.loai === 'hinh' ? 'Chỉnh hình' : 'Chỉnh giờ phụ đề';
            if (!this.ctx.sua(ten, opsDatGio(this.tl, c, vid, moi.bd, moi.kt))) this.ve();
        };
        el.addEventListener('pointermove', di);
        el.addEventListener('pointerup', xong);
        el.addEventListener('pointercancel', xong);
    }

    _veChon() {
        const ds = this.ui.dang_chon || [];
        this.noi.querySelectorAll('.clip').forEach((c) => c.classList.toggle('chon', ds.includes(c.dataset.id)));
        this._veCongCu();
    }

    _veDauPhat() {
        const dp = this.noi.querySelector('[data-khu=dp]');
        if (dp) dp.style.left = `${this.ui.dau_phat * this.px}px`;
        $('gioHienTai').textContent = fmtThoiGian(this.ui.dau_phat, true, Number((this.ctx.du.thong_so || {}).fps) || 30);
    }
}

function nhanGio(t, buoc) {
    const m = Math.floor(t / 60), s = t - m * 60;
    if (buoc < 1) return `${m}:${s.toFixed(1).padStart(4, '0')}`;
    return `${m}:${String(Math.round(s)).padStart(2, '0')}`;
}
