/* Xem trước — hai chế độ như các phần mềm dựng:
 *  - TIMELINE (mặc định): ghép các LỚP tại đầu phát — mỗi track video một thẻ <video>/<img>, track
 *    trên đè track dưới, có biến đổi (vị trí/tỉ lệ/xoay), cắt khung, độ mờ, bo góc; phụ đề và vùng
 *    che vẽ phủ lên. Space phát cả timeline: đồng hồ chính là video của lớp nền khi nó đang chạy,
 *    khoảng trống/ảnh thì theo đồng hồ thật; các lớp khác và track âm thanh bám theo.
 *    Chuyển cảnh: trong khoảng [điểm nối − dai/2, điểm nối + dai/2] một lớp phụ ngay trên lớp nền hiện
 *    clip còn lại với độ mờ tăng dần — mọi kiểu xfade đều xem trước như dissolve (gần đúng).
 *  - NGUỒN: bấm một media trong bảng Tệp phương tiện → xem riêng file đó (✕ để về timeline).
 * Xem trước là gần đúng (CSS); bản xuất ffmpeg (render.py) mới là bản chính xác. */
import { $, esc, toast, api } from './chung.js';
import {
    ketThucClip, thoiLuong, clipTai, thoiDiemMedia, neoTai, tao, trackVideoTuDuoiLen, hopLop, heSoFade,
    BIEN_DOI_MAC_DINH, giaTriTai, hopChuHinh, bienDoiSauKeo
} from './store.js';
import { cssFilter } from './hieu_ung.js';

const LECH_TOI_DA = 0.35;   // giây lệch giữa một lớp và đồng hồ thì tua lại

export class Preview {
    constructor(ctx) {
        this.ctx = ctx;
        this.tocDoPhat = 1;
        this.chieuPhat = 1;
        this._hLui = null;
        this.khung = $('previewKhung');
        this.man = $('previewMan');
        this.man.innerHTML = `
            <div class="lop-cac" data-khu="lop"></div>
            <video class="lop-nguon" preload="auto" playsinline></video>
            <img class="lop-nguon-anh" alt="">
            <div class="lop-che" data-khu="che"></div>
            <div class="lop-chu-hinh" data-khu="chu-hinh"></div>
            <div class="lop-phu-de" data-khu="phu-de"></div>
            <div class="lop-tay-nam" data-khu="tay-nam"></div>
            <div class="lop-ve-vung" data-khu="ve-vung"></div>
            <div class="goi-y" data-khu="goi-y"></div>
            <span class="preview-ten" data-khu="ten"></span>
            <button class="nut-icon nut-ve-tl" data-khu="ve-tl" title="Về xem timeline">✕</button>`;
        const q = (k) => this.man.querySelector(`[data-khu=${k}]`);
        this.cacLop = q('lop');
        this.vNguon = this.man.querySelector('.lop-nguon');
        this.imgNguon = this.man.querySelector('.lop-nguon-anh');
        this.goiY = q('goi-y');
        this.ten = q('ten');
        this.phuDe = q('phu-de');
        this.lopChe = q('che');
        this.lopChuHinh = q('chu-hinh');
        this.lopVe = q('ve-vung');
        this.tayNam = q('tay-nam');
        this.nutVe = q('ve-tl');
        this.lop = new Map();          // track id → {el: div, v: <video>, img: <img>, clip}
        this.amThanh = new Map();      // clip id → <audio>
        this.dangPhat = false;
        this.nguon = null;
        this._raf = 0;
        this._hDuPhong = 0;
        new ResizeObserver(() => { this._co(); this.veTai(this.ctx.ui.dau_phat); }).observe(this.khung);
        this.nutVe.addEventListener('click', () => this.veTimeline());
        this.vNguon.addEventListener('play', () => this._veNut());
        this.vNguon.addEventListener('pause', () => this._veNut());

        ctx.bus.on('bo_cuc', () => { this._co(); this.veTai(ctx.ui.dau_phat); });
        ctx.bus.on('chon', () => { if (!this.dangPhat) { this._veChe(ctx.ui.dau_phat); this._veTayNam(); } });
        ctx.bus.on('chon_nguon', (m) => this.xemNguon(m));
        ctx.bus.on('dau_phat', ({ tuThuoc } = {}) => {
            if (this.dangPhat && tuThuoc === 'phat') return;
            if (this.dangPhat) this.dung();
            if (this.nguon) this.veTimeline(false);
            this.veTai(ctx.ui.dau_phat);
        });
        ctx.bus.on('timeline', () => { if (!this.dangPhat && !this.nguon) this.veTai(ctx.ui.dau_phat); });
        ctx.bus.on('media', () => { if (!this.dangPhat && !this.nguon) this.veTai(ctx.ui.dau_phat); });
        this._ganKeoChe();
        this._ganTayNam();
        this._ganSuaChu();

        $('btnPhat').addEventListener('click', () => this.batTat());
        $('btnVeDau').addEventListener('click', () => ctx.timeline.datDauPhat(0));
        $('btnVeCuoi').addEventListener('click', () => ctx.timeline.datDauPhat(1e9));
        const fps = () => Number((ctx.du.thong_so || {}).fps) || 30;
        $('btnLuiKhung').addEventListener('click', () => ctx.timeline.datDauPhat(ctx.ui.dau_phat - 1 / fps()));
        $('btnToiKhung').addEventListener('click', () => ctx.timeline.datDauPhat(ctx.ui.dau_phat + 1 / fps()));
        $('btnXemChinhXac').addEventListener('click', () => this.xemChinhXac());
        const al = $('amLuong');
        al.value = ctx.ui.xem_truoc.am_luong;
        al.addEventListener('input', () => {
            ctx.ui.xem_truoc.am_luong = Number(al.value);
            if (this.nguon) this.vNguon.volume = this.master;
            ctx.luuUi();
        });
    }

    get tl() { return this.ctx.store.timeline; }
    get master() { return Number(this.ctx.ui.xem_truoc.am_luong ?? 1); }

    _co() {
        const ts = this.ctx.du.thong_so || {};
        const tiLe = (ts.rong && ts.cao) ? ts.rong / ts.cao : 16 / 9;
        const w = this.khung.clientWidth - 24, h = this.khung.clientHeight - 24;
        const rong = Math.max(40, Math.min(w, h * tiLe));
        this.man.style.width = `${Math.floor(rong)}px`;
        this.man.style.height = `${Math.floor(rong / tiLe)}px`;
    }

    _url(m) { return `/api/du-an/${encodeURIComponent(this.ctx.id)}/media/${m.id}/file?v=${esc(m.proxy || '')}`; }
    _media(id) { return this.ctx.media.find((m) => m.id === id); }

    // ------------------------------------------------------------------ NGUỒN
    xemNguon(m) {
        if (this.dangPhat) this.dung();
        this.nguon = m;
        this.man.classList.add('nguon');
        this._anAmThanh();
        for (const l of this.lop.values()) l.v.pause();
        this.imgNguon.style.display = 'none';
        this.vNguon.style.display = 'none';
        this.phuDe.style.display = 'none';
        this.lopChe.innerHTML = '';
        this.tayNam.innerHTML = '';
        this.ten.textContent = `Nguồn: ${m.ten}`;
        this.goiY.textContent = '';
        if (m.trang_thai !== 'san_sang' || m.mat_file) { this.goiY.textContent = `Media chưa sẵn sàng (${m.trang_thai})`; return; }
        if (m.loai === 'anh') {
            this.imgNguon.src = this._url(m);
            this.imgNguon.style.display = '';
        } else if (m.loai === 'video' || m.loai === 'audio') {
            if (this.vNguon.dataset.src !== this._url(m)) { this.vNguon.dataset.src = this._url(m); this.vNguon.src = this._url(m); }
            this.vNguon.style.display = m.loai === 'video' ? '' : 'none';
            if (m.loai === 'audio') this.goiY.textContent = '🎵 Âm thanh — Space để nghe';
            this.vNguon.currentTime = 0;
            this.vNguon.volume = this.master;
        } else {
            this.goiY.textContent = '💬 File phụ đề — kéo xuống timeline hoặc mở ở bảng Phụ đề.';
        }
        this._veNut();
    }

    async xemChinhXac() {
        if (this.dangPhat) this.dung();
        
        // Đoạn quanh đầu phát ±3s
        const t_vao = Math.max(0, this.ctx.ui.dau_phat - 3);
        const t_ra = this.ctx.ui.dau_phat + 3;
        
        $('btnXemChinhXac').disabled = true;
        try {
            toast('Đang gọi FFmpeg render 1 đoạn ngắn, vui lòng đợi...', 'info', 5000);
            const r = await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/xem-chinh-xac`, {
                method: 'POST',
                body: { phien: this.ctx.boLuu.phien, t_vao, t_ra }
            });
            
            // Theo dõi
            while (true) {
                const hds = await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/tac-vu`);
                const v = (hds.tac_vu || []).find(x => x.id === r.id);
                if (!v) break;
                if (v.trang_thai === 'loi' || v.trang_thai === 'bi_ngat') {
                    throw new Error(v.loi || 'Bị ngắt');
                }
                if (v.trang_thai === 'xong') {
                    this._hienVideoChinhXac(v.ket_qua.url || v.ket_qua.file);
                    break;
                }
                await new Promise(res => setTimeout(res, 500));
            }
        } catch(e) {
            toast('Lỗi xem chính xác: ' + e.message, 'error');
        } finally {
            $('btnXemChinhXac').disabled = false;
        }
    }
    
    _hienVideoChinhXac(url) {
        // Overlay
        let wrap = this.khung.querySelector('.xem-chinh-xac-wrap');
        if (!wrap) {
            wrap = document.createElement('div');
            wrap.className = 'xem-chinh-xac-wrap';
            wrap.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); display:flex; align-items:center; justify-content:center; z-index:100; flex-direction:column;';
            this.khung.appendChild(wrap);
            wrap.innerHTML = `
                <div style="background:#222; padding:10px; border-radius:5px; position:relative; box-shadow:0 0 15px rgba(0,0,0,0.5);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <b style="color:#eee">Bản xuất ffmpeg chính xác</b>
                        <button class="nut nut-nho nut-dong">✕ Đóng</button>
                    </div>
                    <video controls autoplay style="max-width:100%; max-height:calc(100vh - 200px); background:#000; border:1px solid #444; border-radius:3px;"></video>
                </div>
            `;
            wrap.querySelector('.nut-dong').addEventListener('click', () => wrap.style.display = 'none');
        }
        wrap.style.display = 'flex';
        const v = wrap.querySelector('video');
        v.src = url + (url.includes('?') ? '&' : '?') + 'v=' + Date.now();
        v.play().catch(() => {});
    }

    veTimeline(ve = true) {
        this.nguon = null;
        this.man.classList.remove('nguon');
        this.vNguon.pause();
        this.vNguon.style.display = 'none';
        this.imgNguon.style.display = 'none';
        this.ctx.chon.media = null;
        this.ctx.bus.emit('bo_chon_nguon');
        if (ve) this.veTai(this.ctx.ui.dau_phat);
    }

    // ------------------------------------------------------------------ LỚP
    /* Bảo đảm mỗi track video có một phần tử lớp, đúng thứ tự chồng (dưới trước). */
    _dongBoLop() {
        const ds = trackVideoTuDuoiLen(this.tl);
        const ids = new Set(ds.map((t) => t.id));
        for (const [id, l] of this.lop) if (!ids.has(id)) { l.v.pause(); l.el.remove(); this.lop.delete(id); }
        ds.forEach((t, i) => {
            let l = this.lop.get(t.id);
            if (!l) {
                const el = document.createElement('div');
                el.className = 'lop-video';
                el.innerHTML = '<video preload="auto" playsinline></video><img alt="">';
                l = { el, v: el.querySelector('video'), img: el.querySelector('img'), clip: null };
                l.v.addEventListener('loadedmetadata', () => { if (!this.dangPhat) this._veChe(this.ctx.ui.dau_phat); });
                this.lop.set(t.id, l);
            }
            l.el.style.zIndex = String(i + 1);
            if (this.cacLop.children[i] !== l.el) this.cacLop.insertBefore(l.el, this.cacLop.children[i] || null);
        });
        return ds;
    }

    /* Đặt vị trí/biến đổi của lớp theo clip (CSS gần đúng với render.py). */
    _datHop(l, c, m, t) {
        const W = this.man.clientWidth, H = this.man.clientHeight;
        const ts = this.ctx.du.thong_so || {};
        const W_xuat = ts.rong || 1920;
        const tiLe = W / W_xuat;
        
        const bd = c.bat_dau || 0;
        const tCucBo = t - bd;
        
        const ht = {
            ...c,
            bien_doi: {
                x: giaTriTai(c, 'bien_doi.x', tCucBo),
                y: giaTriTai(c, 'bien_doi.y', tCucBo),
                ti_le: giaTriTai(c, 'bien_doi.ti_le', tCucBo),
                xoay: giaTriTai(c, 'bien_doi.xoay', tCucBo)
            },
            hien_thi: {
                ...(c.hien_thi || {}),
                do_mo: giaTriTai(c, 'hien_thi.do_mo', tCucBo)
            }
        };
        
        const hop = hopLop(ht, m, W, H);
        const k = ht.cat_khung || {}, h = ht.hien_thi || {};
        const pc = (x) => `${Math.max(0, Math.min(100, Number(x || 0) * 100))}%`;
        const r = Number(h.bo_goc || 0) * H / 1080;
        Object.assign(l.el.style, {
            left: `${hop.cx - hop.w / 2}px`, top: `${hop.cy - hop.h / 2}px`, width: `${hop.w}px`, height: `${hop.h}px`,
            transform: hop.xoay ? `rotate(${hop.xoay}deg)` : '', opacity: String(h.do_mo ?? 1),
            clipPath: (k.trai || k.phai || k.tren || k.duoi || r) ? `inset(${pc(k.tren)} ${pc(k.phai)} ${pc(k.duoi)} ${pc(k.trai)} round ${r}px)` : '',
            display: '',
            filter: cssFilter(c.mau, c.hieu_ung, tiLe),
            mixBlendMode: h.hoa_tron && h.hoa_tron !== 'normal' ? h.hoa_tron : '',
        });
        l.hop = hop;
    }

    /* Hiện clip `c` trên lớp `l` tại thời điểm t; phat=true thì cho chạy và chỉ tua khi lệch nhiều. */
    _hienLop(l, tr, c, t, phat) {
        const m = c && this._media(c.media);
        l.clip = c;
        if (!c || !m || m.trang_thai !== 'san_sang' || m.mat_file) {
            l.v.pause();
            l.el.style.display = 'none';
            return;
        }
        this._datHop(l, c, m, t);
        const url = this._url(m);
        if (m.loai === 'anh') {
            l.v.pause();
            l.v.style.display = 'none';
            if (l.img.dataset.src !== url) { l.img.dataset.src = url; l.img.src = url; }
            l.img.style.display = '';
            return;
        }
        l.img.style.display = 'none';
        l.v.style.display = '';
        if (l.v.dataset.src !== url) { l.v.dataset.src = url; l.v.src = url; }
        l.v.muted = !!tr.tat_tieng || !!c.tat_am;
        const vol = Number(giaTriTai(c, 'am_luong', t - (c.bat_dau || 0)) ?? 1);
        l.v.volume = Math.min(1, vol * this.master * heSoFade(c, t));
        l.v.playbackRate = (Number(c.toc_do) || 1) * (this.tocDoPhat || 1);
        const tm = thoiDiemMedia(c, t);
        const tua = () => { if (Math.abs(l.v.currentTime - tm) > (phat ? LECH_TOI_DA : 0.02)) l.v.currentTime = tm; };
        if (l.v.readyState >= 1) tua(); else l.v.addEventListener('loadedmetadata', tua, { once: true });
        if (phat && l.v.paused) l.v.play().catch(() => {});
        if (!phat && !l.v.paused) l.v.pause();
    }

    /* Vẽ mọi lớp tại t (không phát). */
    veTai(t) {
        if (this.nguon) return;
        this.ten.textContent = '';
        this.goiY.textContent = '';
        for (const tr of this._dongBoLop()) {
            const l = this.lop.get(tr.id);
            this._hienLop(l, tr, tr.an ? null : clipTai(this.tl, tr.id, t), t, false);
        }
        this._veChuyenCanh(t, false);
        this._veLop(t);
        this._veTayNam();
        if (!this.tl.clips.length) this.goiY.textContent = 'Timeline trống — kéo media từ bảng Tệp phương tiện xuống.';
    }

    /* Lớp đang hiện media `mid` (lớp trên cùng) — vùng che/OCR tính theo khung của nó. */
    _lopCuaMedia(mid) {
        const ds = trackVideoTuDuoiLen(this.tl).reverse();
        for (const tr of ds) {
            const l = this.lop.get(tr.id);
            if (l && l.clip && l.clip.media === mid && l.el.style.display !== 'none') return l;
        }
        return null;
    }

    /* Khung nội dung (không xoay, trước cắt) của media trên màn xem trước. */
    _khungNoiDung(mid) {
        const l = mid ? this._lopCuaMedia(mid) : trackVideoTuDuoiLen(this.tl).reverse().map((t) => this.lop.get(t.id))
            .find((x) => x && x.clip && x.el.style.display !== 'none');
        if (l && l.hop) return { x: l.hop.cx - l.hop.w / 2, y: l.hop.cy - l.hop.h / 2, w: l.hop.w, h: l.hop.h, mid: l.clip.media };
        return { x: 0, y: 0, w: this.man.clientWidth, h: this.man.clientHeight, mid: null };
    }

    _veLop(t) {
        this._vePhuDe(t);
        this._veChe(t);
        this._veChuHinh(t);
    }

    _vePhuDe(t) {
        const dang = this.nguon ? [] : neoTai(this.tl, 'phu_de', t);
        const c = dang.length ? dang[dang.length - 1].c : null;
        const chu = c ? (c.text || '') : '';
        this.phuDe.style.display = chu ? '' : 'none';
        if (!chu) { this.phuDe.textContent = ''; return; }
        const k = ((this.tl.kieu_phu_de || {})[c.kieu || 'k_mac_dinh']) || {};
        const H = this.man.clientHeight, ty = H / 1080;
        const vien = Number(k.do_day_vien ?? 2) * ty;
        const mauVien = k.vien || '#000';
        const s = this.phuDe.style;
        s.fontFamily = k.font ? `"${k.font}", Arial, sans-serif` : 'Arial, sans-serif';
        s.fontSize = `${Math.max(8, Number(k.co || 48) * ty)}px`;
        s.color = k.mau || '#fff';
        s.bottom = `${(1 - Number(k.vi_tri_y ?? 0.9)) * 100}%`;
        s.textShadow = vien > 0
            ? [[-1, -1], [1, -1], [-1, 1], [1, 1], [0, 1], [0, -1], [1, 0], [-1, 0]]
                .map(([a, b]) => `${a * vien}px ${b * vien}px 0 ${mauVien}`).join(',')
            : 'none';
        const coNen = (k.nen || 'None') !== 'None';
        this.phuDe.innerHTML = coNen
            ? `<span style="background:${k.mau_nen || 'rgba(0,0,0,.6)'};padding:0 .3em;box-decoration-break:clone;-webkit-box-decoration-break:clone">${esc(chu)}</span>`
            : esc(chu);
    }

    _veChe(t) {
        const ds = this.nguon ? [] : neoTai(this.tl, 'che_phu_de', t);
        const chon = new Set(this.ctx.ui.dang_chon || []);
        this.lopChe.innerHTML = ds.map(({ c }) => {
            const kh = this._khungNoiDung(c.tu_media);
            const v = c.vung || { x: 0.1, y: 0.8, w: 0.8, h: 0.12 };
            const manh = Number(c.do_manh ?? 20);
            const kieu = c.kieu || 'blur';
            const mo = Math.max(2, kieu === 'mosaic' ? manh / 1.5 : manh / 3);
            const nen = kieu === 'mau' ? `background:${c.mau || '#000'};`
                : `backdrop-filter:blur(${mo}px);-webkit-backdrop-filter:blur(${mo}px);`;
            return `<div class="o-che ${chon.has(c.id) ? 'chon' : ''} ${kieu}" data-id="${esc(c.id)}"
                style="left:${kh.x + v.x * kh.w}px;top:${kh.y + v.y * kh.h}px;width:${v.w * kh.w}px;height:${v.h * kh.h}px;${nen}">
                ${chon.has(c.id) ? '<i class="nam" data-goc="se"></i>' : ''}</div>`;
        }).join('');
    }

    _veChuHinh(t) {
        if (this.nguon) { this.lopChuHinh.innerHTML = ''; return; }
        const ds = this.tl.clips.filter((c) => (c.loai === 'chu' || c.loai === 'hinh') && c.bat_dau <= t && t < c.ket_thuc);   // nửa mở như ffmpeg: ở điểm nối chỉ hiện clip sau
        const chon = new Set(this.ctx.ui.dang_chon || []);
        const W = this.man.clientWidth, H = this.man.clientHeight;
        
        this.lopChuHinh.innerHTML = ds.map((c) => {
            const bd = c.bien_doi || { x: 0.5, y: 0.5, ti_le: 1, xoay: 0 };
            const ht = c.hien_thi || {};
            const mo = ht.do_mo ?? c.do_mo ?? 1;
            const left = bd.x * W, top = bd.y * H;
            let noi = '';
            if (c.loai === 'chu') {
                const k = c.kieu || {};
                const co = (k.co || 48) * (H / 1080) * (bd.ti_le || 1);
                const shadow = k.vien_day ? `-1px -1px 0 ${k.vien_mau}, 1px -1px 0 ${k.vien_mau}, -1px 1px 0 ${k.vien_mau}, 1px 1px 0 ${k.vien_mau}` : 'none';
                noi = `<div class="chu-hinh-o ${chon.has(c.id) ? 'chon' : ''}" data-id="${esc(c.id)}" data-loai="chu" 
                    style="position:absolute;left:${left}px;top:${top}px;transform:translate(-50%,-50%) rotate(${bd.xoay || 0}deg);
                    font-family:'${esc(k.font || 'Arial')}',sans-serif;font-size:${co}px;color:${esc(k.mau || '#fff')};
                    text-shadow:${shadow};opacity:${mo};white-space:pre-wrap;text-align:center;width:max-content;max-width:${W}px;
                    cursor:pointer">${esc(c.noi_dung || '')}</div>`;
            } else if (c.loai === 'hinh') {
                const w = (bd.rong || 0.2) * W * (bd.ti_le || 1);
                const h = (bd.cao || 0.2) * H * (bd.ti_le || 1);
                const rx = w/2, ry = h/2;
                // Hình vẽ quanh tâm (0,0); viewBox dời gốc về giữa khung SVG — không thì rect x=-rx bị lệch nửa cỡ lên trái.
                // Cùng dáng với bản xuất (chu_hinh.py): sao 5 cánh bán kính trong 0.4, đa giác đều, mũi tên, tim.
                const diem = (n, trong) => Array.from({ length: n }, (_, i) => {
                    const a = -Math.PI / 2 + i * 2 * Math.PI / n, r = trong && i % 2 ? 0.4 : 1;
                    return `${(Math.cos(a) * rx * r).toFixed(1)},${(Math.sin(a) * ry * r).toFixed(1)}`;
                }).join(' ');
                let path;
                if (c.dang === 'chu_nhat') path = `<rect x="${-rx}" y="${-ry}" width="${w}" height="${h}" rx="${c.bo_goc || 0}" />`;
                else if (c.dang === 'sao') path = `<polygon points="${diem(10, true)}" />`;
                else if (c.dang === 'da_giac') path = `<polygon points="${diem(Math.max(3, c.so_canh || 5), false)}" />`;
                else if (c.dang === 'mui_ten') path = `<polygon points="${-rx},${-ry * 0.6} 0,${-ry * 0.6} 0,${-ry} ${rx},0 0,${ry} 0,${ry * 0.6} ${-rx},${ry * 0.6}" />`;
                else if (c.dang === 'tim') path = `<path d="M0 ${-ry * 0.4} C${rx} ${-ry * 1.4} ${rx * 1.2} 0 0 ${ry} C${-rx * 1.2} 0 ${-rx} ${-ry * 1.4} 0 ${-ry * 0.4}Z" />`;
                else path = `<ellipse cx="0" cy="0" rx="${rx}" ry="${ry}" />`;
                noi = `<svg class="chu-hinh-o ${chon.has(c.id) ? 'chon' : ''}" data-id="${esc(c.id)}" data-loai="hinh" viewBox="${-rx} ${-ry} ${w} ${h}"
                    style="position:absolute;left:${left}px;top:${top}px;transform:translate(-50%,-50%) rotate(${bd.xoay || 0}deg);
                    width:${w}px;height:${h}px;opacity:${mo};overflow:visible;cursor:pointer">
                    <g stroke="${esc(c.vien_mau || '#000')}" stroke-width="${c.vien_day || 0}" fill="${esc(c.mau || '#fff')}">${path}</g>
                </svg>`;
            }
            return noi;
        }).join('');
    }

    // ------------------------------------------------------- tay nắm biến đổi
    _clipChonHien() {
        const cid = this.ctx.chon.clip;
        if (!cid || this.dangPhat || this.nguon) return null;
        for (const [tid, l] of this.lop) {
            if (l.clip && l.clip.id === cid && l.el.style.display !== 'none') return { l, loai: 'media' };
        }
        const o = this.lopChuHinh.querySelector(`.chu-hinh-o[data-id="${cid}"]`);
        if (o && o.contentEditable !== 'true') {
            const c = (this.tl.clips || []).find(x => x.id === cid);
            if (c) return { c, el: o, loai: c.loai };
        }
        return null;
    }

    _veTayNam() {
        const x = this._clipChonHien();
        let h = null;
        if (x && x.loai === 'media' && x.l.hop) {
            h = x.l.hop;
        } else if (x && (x.loai === 'chu' || x.loai === 'hinh')) {
            const W = this.man.clientWidth, H = this.man.clientHeight;
            h = hopChuHinh(x.c, W, H, x.loai === 'chu' ? x.el.offsetWidth : 0, x.loai === 'chu' ? x.el.offsetHeight : 0);
            x.hop = h;
        }
        if (!h) { this.tayNam.innerHTML = ''; return; }
        this.tayNam.innerHTML = `<div class="khung-bien-doi" style="left:${h.cx - h.w / 2}px;top:${h.cy - h.h / 2}px;width:${h.w}px;height:${h.h}px;${h.xoay ? `transform:rotate(${h.xoay}deg)` : ''}">
            <i class="nam-goc" data-nam="tl"></i><i class="nam-goc" data-nam="tr"></i><i class="nam-goc" data-nam="bl"></i><i class="nam-goc" data-nam="br"></i>
            <i class="nam-xoay" data-nam="xoay" title="Kéo để xoay (Shift: bước 15°)"></i></div>`;
    }

    _ganTayNam() {
        this.tayNam.addEventListener('pointerdown', (e) => {
            const x = this._clipChonHien();
            const khung = e.target.closest('.khung-bien-doi');
            if (!x || !khung || this.ctx.store.chiDoc) return;
            e.preventDefault();
            const c = x.loai === 'media' ? x.l.clip : x.c;
            const tCucBo = this.ctx.ui.dau_phat - (c.bat_dau || 0);
            const val = (k, fb) => giaTriTai(c, k, tCucBo) ?? fb;
            const b0 = {
                x: val('bien_doi.x', (c.bien_doi || {}).x ?? BIEN_DOI_MAC_DINH.x),
                y: val('bien_doi.y', (c.bien_doi || {}).y ?? BIEN_DOI_MAC_DINH.y),
                ti_le: val('bien_doi.ti_le', (c.bien_doi || {}).ti_le ?? BIEN_DOI_MAC_DINH.ti_le),
                xoay: val('bien_doi.xoay', (c.bien_doi || {}).xoay ?? 0)
            };
            if (c.loai === 'hinh') {
                b0.rong = val('bien_doi.rong', (c.bien_doi || {}).rong ?? 0.2);
                b0.cao = val('bien_doi.cao', (c.bien_doi || {}).cao ?? 0.2);
            }
            const W = this.man.clientWidth, H = this.man.clientHeight;
            const r = this.man.getBoundingClientRect();
            const nam = e.target.dataset.nam || 'doi';
            const x0 = e.clientX, y0 = e.clientY;
            const tam = { x: r.left + b0.x * W, y: r.top + b0.y * H };
            const kc0 = Math.hypot(x0 - tam.x, y0 - tam.y) || 1;
            const goc0 = Math.atan2(y0 - tam.y, x0 - tam.x);
            let moi = null;
            khung.setPointerCapture(e.pointerId);
            const di = (ev) => {
                let dx, dy;
                if (nam === 'doi') { dx = ev.clientX - x0; dy = ev.clientY - y0; }
                else if (nam === 'xoay') { dx = (Math.atan2(ev.clientY - tam.y, ev.clientX - tam.x) - goc0) * 180 / Math.PI; dy = 0; }
                else if (x.loai === 'hinh') { dx = ev.clientX - x0; dy = ev.clientY - y0; }
                else { dx = Math.hypot(ev.clientX - tam.x, ev.clientY - tam.y) / kc0; dy = 0; }
                
                moi = bienDoiSauKeo(b0, x.loai, nam, dx, dy, W, H, ev.shiftKey);
                
                const tam2 = { ...c, bien_doi: moi };
                if (x.loai === 'media') {
                    this._datHop(x.l, tam2, this._media(c.media), this.ctx.ui.dau_phat);
                    this._veTayNam2(x.l.hop);
                } else {
                    const h = hopChuHinh(tam2, W, H, x.loai === 'chu' ? x.el.offsetWidth : 0, x.loai === 'chu' ? x.el.offsetHeight : 0);
                    Object.assign(x.el.style, {
                        left: `${h.cx}px`, top: `${h.cy}px`, transform: `translate(-50%,-50%) rotate(${h.xoay}deg)`
                    });
                    if (x.loai === 'chu') x.el.style.fontSize = `${(tam2.kieu?.co || 48) * H / 1080 * (tam2.bien_doi.ti_le || 1)}px`;
                    else if (x.loai === 'hinh') {
                        x.el.style.width = `${h.w}px`; x.el.style.height = `${h.h}px`;
                    }
                    this._veTayNam2(h);
                }
            };
            const xong = () => {
                khung.removeEventListener('pointermove', di);
                khung.removeEventListener('pointerup', xong);
                if (!moi) return;
                const r4 = (v) => Math.round(v * 10000) / 10000;
                const bd = { x: r4(moi.x), y: r4(moi.y), ti_le: r4(moi.ti_le), xoay: moi.xoay };
                const ten = nam === 'doi' ? 'Dời lớp' : nam === 'xoay' ? 'Xoay lớp' : 'Đổi cỡ lớp';
                
                const kf = c.keyframes || {};
                let ops = [];
                
                const processProp = (k, v) => {
                    const full = 'bien_doi.' + k;
                    const ds = kf[full] || [];
                    if (ds.length > 0 || ds.some(d => Math.abs(d.t - tCucBo) < 1e-4)) {
                        let moiDS = [...ds];
                        const idx = moiDS.findIndex(d => Math.abs(d.t - tCucBo) < 1e-4);
                        if (idx >= 0) moiDS[idx] = { ...moiDS[idx], v };
                        else moiDS.push({ t: tCucBo, v, em: 'tuyen_tinh' });
                        moiDS.sort((a,b) => a.t - b.t);
                        ops.push(tao.dat(this.tl, ['clips', { id: c.id }, 'keyframes', full], moiDS));
                    }
                };
                
                if (nam === 'doi') { processProp('x', bd.x); processProp('y', bd.y); }
                else if (nam === 'xoay') { processProp('xoay', bd.xoay); }
                else { processProp('ti_le', bd.ti_le); }
                
                ops.push(tao.dat(this.tl, ['clips', { id: c.id }, 'bien_doi'], { ...(c.bien_doi || {}), ...bd }));
                if (!this.ctx.sua(ten, ops)) this.veTai(this.ctx.ui.dau_phat);
            };
            khung.addEventListener('pointermove', di);
            khung.addEventListener('pointerup', xong);
        });
    }

    _veTayNam2(h) {
        const k = this.tayNam.querySelector('.khung-bien-doi');
        if (!k || !h) return;
        Object.assign(k.style, { left: `${h.cx - h.w / 2}px`, top: `${h.cy - h.h / 2}px`, width: `${h.w}px`, height: `${h.h}px`,
            transform: h.xoay ? `rotate(${h.xoay}deg)` : '' });
    }

    // ------------------------------------------------------- kéo khung vùng
    /* Kéo một khung chữ nhật trên video đang hiện → Promise vùng {x,y,w,h} (0–1 theo khung media), null nếu huỷ. */
    veVung(goiY = 'Kéo chuột quanh vùng chữ/phụ đề cần lấy', mid = null) {
        if (this.dangPhat) this.dung();
        return new Promise((resolve) => {
            const lop = this.lopVe;
            lop.classList.add('bat');
            lop.innerHTML = `<div class="ve-goi-y">${esc(goiY)} — Esc để huỷ</div><div class="ve-khung"></div>`;
            const khung = lop.querySelector('.ve-khung');
            let bd = null;
            const kh = this._khungNoiDung(mid);
            const toaDo = (e) => {
                const r = this.man.getBoundingClientRect();
                return {
                    x: Math.min(Math.max(e.clientX - r.left, kh.x), kh.x + kh.w),
                    y: Math.min(Math.max(e.clientY - r.top, kh.y), kh.y + kh.h),
                };
            };
            const phim = (e) => { if (e.key === 'Escape') { e.stopPropagation(); xong(null); } };
            function xong(vung) {
                lop.classList.remove('bat');
                lop.innerHTML = '';
                lop.onpointerdown = null;
                lop.onpointermove = null;
                lop.onpointerup = null;
                document.removeEventListener('keydown', phim, true);
                resolve(vung);
            }
            document.addEventListener('keydown', phim, true);
            lop.onpointerdown = (e) => { bd = toaDo(e); lop.setPointerCapture(e.pointerId); };
            lop.onpointermove = (e) => {
                if (!bd) return;
                const p = toaDo(e);
                Object.assign(khung.style, {
                    left: `${Math.min(bd.x, p.x)}px`, top: `${Math.min(bd.y, p.y)}px`,
                    width: `${Math.abs(p.x - bd.x)}px`, height: `${Math.abs(p.y - bd.y)}px`, display: 'block',
                });
            };
            lop.onpointerup = (e) => {
                if (!bd) return;
                const p = toaDo(e);
                const w = Math.abs(p.x - bd.x), h = Math.abs(p.y - bd.y);
                if (w < 8 || h < 8) { bd = null; khung.style.display = 'none'; return; }
                const r4 = (x) => Math.round(x * 10000) / 10000;
                xong({
                    x: r4((Math.min(bd.x, p.x) - kh.x) / kh.w), y: r4((Math.min(bd.y, p.y) - kh.y) / kh.h),
                    w: r4(w / kh.w), h: r4(h / kh.h),
                });
            };
        });
    }

    _ganSuaChu() {
        this.lopChuHinh.addEventListener('dblclick', (e) => {
            const o = e.target.closest('.chu-hinh-o[data-loai="chu"]');
            if (!o) return;
            o.contentEditable = 'true';
            o.focus();
            this.tayNam.innerHTML = '';
            const cu = o.innerText;
            const ketThuc = (luu) => {
                if (o.contentEditable !== 'true') return;
                o.contentEditable = 'false';
                o.removeEventListener('keydown', phim);
                if (luu) {
                    const moi = o.innerText;
                    if (moi !== cu) {
                        const c = this.tl.clips.find(x => x.id === o.dataset.id);
                        if (c) this.ctx.sua('Sửa nội dung chữ', [tao.dat(this.tl, ['clips', { id: c.id }, 'noi_dung'], moi)]);
                    }
                } else {
                    o.innerText = cu;
                }
                this._veTayNam();
            };
            const phim = (ev) => {
                if (ev.key === 'Escape') {
                    ev.preventDefault();
                    ketThuc(false);
                } else if (ev.key === 'Enter' && !ev.shiftKey) {
                    ev.preventDefault();
                    ketThuc(true);
                }
            };
            o.addEventListener('keydown', phim);
            o.onblur = () => ketThuc(true);
        });
        this.lopChuHinh.addEventListener('pointerdown', (e) => {
            const o = e.target.closest('.chu-hinh-o');
            if (o && o.dataset.id && o.contentEditable !== 'true') this.ctx.timeline.chonClip(o.dataset.id);
        });
    }

    /* Vùng che đang chọn: kéo thân để dời, kéo góc dưới-phải để đổi cỡ → một lệnh hoàn tác. */
    _ganKeoChe() {
        this.lopChe.addEventListener('pointerdown', (e) => {
            const o = e.target.closest('.o-che');
            if (!o || this.dangPhat || this.ctx.store.chiDoc) return;
            const c = this.tl.clips.find((x) => x.id === o.dataset.id);
            if (!c) return;
            if (!(this.ctx.ui.dang_chon || []).includes(c.id)) { this.ctx.timeline.chonClip(c.id); return; }
            e.preventDefault();
            const kh = this._khungNoiDung(c.tu_media);
            const v0 = { ...(c.vung || { x: 0.1, y: 0.8, w: 0.8, h: 0.12 }) };
            const doiCo = !!e.target.closest('[data-goc]');
            const x0 = e.clientX, y0 = e.clientY;
            let moi = null;
            o.setPointerCapture(e.pointerId);
            const k01 = (x) => Math.min(1, Math.max(0, x));
            const di = (ev) => {
                const dx = (ev.clientX - x0) / kh.w, dy = (ev.clientY - y0) / kh.h;
                moi = doiCo
                    ? { ...v0, w: Math.max(0.02, Math.min(1 - v0.x, v0.w + dx)), h: Math.max(0.02, Math.min(1 - v0.y, v0.h + dy)) }
                    : { ...v0, x: k01(Math.min(1 - v0.w, v0.x + dx)), y: k01(Math.min(1 - v0.h, v0.y + dy)) };
                Object.assign(o.style, {
                    left: `${kh.x + moi.x * kh.w}px`, top: `${kh.y + moi.y * kh.h}px`,
                    width: `${moi.w * kh.w}px`, height: `${moi.h * kh.h}px`,
                });
            };
            const xong = () => {
                o.removeEventListener('pointermove', di);
                o.removeEventListener('pointerup', xong);
                if (!moi) return;
                const r4 = (x) => Math.round(x * 10000) / 10000;
                this.ctx.sua(doiCo ? 'Đổi cỡ vùng che' : 'Dời vùng che', [tao.dat(this.tl, ['clips', { id: c.id }, 'vung'],
                    { x: r4(moi.x), y: r4(moi.y), w: r4(moi.w), h: r4(moi.h) })]);
            };
            o.addEventListener('pointermove', di);
            o.addEventListener('pointerup', xong);
        });
    }

    // ------------------------------------------------------------ âm thanh
    _dongBoAmThanh(t, phat) {
        const conSong = new Set();
        for (const tr of this.tl.tracks.filter((x) => x.loai === 'audio')) {
            const c = clipTai(this.tl, tr.id, t);
            if (!c || tr.tat_tieng) continue;
            const m = this._media(c.media);
            if (!m || m.trang_thai !== 'san_sang') continue;
            conSong.add(c.id);
            let a = this.amThanh.get(c.id);
            if (!a) {
                a = new Audio(this._url(m));
                a.preload = 'auto';
                this.amThanh.set(c.id, a);
            }
            a.volume = Math.min(1, Number(c.am_luong ?? 1) * this.master * heSoFade(c, t));
            a.playbackRate = (Number(c.toc_do) || 1) * (this.tocDoPhat || 1);
            const tm = thoiDiemMedia(c, t);
            if (a.readyState >= 1 && Math.abs(a.currentTime - tm) > LECH_TOI_DA) a.currentTime = tm;
            if (phat && a.paused) a.play().catch(() => {});
        }
        for (const [id, a] of this.amThanh) {
            if (!conSong.has(id)) { a.pause(); this.amThanh.delete(id); a.removeAttribute('src'); }
        }
    }

    _anAmThanh() {
        for (const a of this.amThanh.values()) { a.pause(); a.removeAttribute('src'); }
        this.amThanh.clear();
    }

    // ------------------------------------------------------------ phát
    phat() {
        const tong = thoiLuong(this.tl);
        if (!tong) return;
        if (this.ctx.ui.dau_phat >= tong - 0.05) this.ctx.timeline.datDauPhat(0, true);
        this.dangPhat = true;
        this.tayNam.innerHTML = '';
        this._neo = { t: this.ctx.ui.dau_phat, luc: performance.now() };
        const buoc = () => {
            if (!this.dangPhat) return;
            this._nhip();
            this._raf = requestAnimationFrame(buoc);
        };
        this._raf = requestAnimationFrame(buoc);
        // Cửa sổ bị thu nhỏ/che thì rAF dừng — nhịp dự phòng giữ cho timeline vẫn chạy đúng.
        this._hDuPhong = setInterval(() => this._nhip(), 120);
        this._nhip();
        this._veNut();
    }

    _nhip() {
        if (!this.dangPhat) return;
        const tong = thoiLuong(this.tl);
        const bayGio = performance.now();
        let t = this._neo.t + (bayGio - this._neo.luc) / 1000;
        // Đồng hồ chính: video của lớp NỀN khi nó đang chạy ổn định.
        const ds = this._dongBoLop();
        const nen = ds.length ? this.lop.get(ds[0].id) : null;
        const c = nen && nen.clip;
        if (c && !nen.v.paused && nen.v.readyState >= 3 && nen.v.style.display !== 'none') {
            const tv = Number(c.bat_dau) + (nen.v.currentTime - Number(c.vao || 0)) / (Number(c.toc_do) || 1);
            if (tv >= Number(c.bat_dau) - 0.05 && tv <= ketThucClip(c) + 0.05) {
                t = tv;
                this._neo = { t, luc: bayGio };
            }
        }
        if (t >= tong) {
            this.ctx.timeline.datDauPhat(tong, 'phat', true);
            this.dung();
            return;
        }
        this.ctx.timeline.datDauPhat(t, 'phat', true);
        for (const tr of ds) {
            const l = this.lop.get(tr.id);
            const moi = tr.an ? null : clipTai(this.tl, tr.id, t);
            if (moi !== l.clip || (moi && l.v.paused && l.v.style.display !== 'none')) {
                this._hienLop(l, tr, moi, t, true);
                if (l === nen) this._neo = { t, luc: bayGio };
            } else if (moi) {
                l.v.volume = Math.min(1, Number(moi.am_luong ?? 1) * this.master * heSoFade(moi, t));
                if (l !== nen && l.v.readyState >= 1 && Math.abs(l.v.currentTime - thoiDiemMedia(moi, t)) > LECH_TOI_DA) {
                    l.v.currentTime = thoiDiemMedia(moi, t);
                }
            }
        }
        this._veChuyenCanh(t, true);
        this._veLop(t);
        this._dongBoAmThanh(t, true);
    }

    /* Chuyển cảnh đang diễn ra tại t trên track nền → {khac: clip hiện ở lớp phụ, mo: độ mờ của nó}, không có thì null. */
    _chuyenCanhTai(t) {
        const nen = trackVideoTuDuoiLen(this.tl)[0];
        if (!nen || nen.an) return null;
        for (const cc of this.tl.chuyen_canh || []) {
            const truoc = this.tl.clips.find((c) => c.id === cc.truoc);
            const sau = this.tl.clips.find((c) => c.id === cc.sau);
            if (!truoc || !sau || truoc.track !== nen.id) continue;
            const noi = ketThucClip(truoc), dai = Number(cc.dai) || 0;
            if (dai <= 0 || t < noi - dai / 2 || t >= noi + dai / 2) continue;
            const p = (t - (noi - dai / 2)) / dai;   // 0 → 1 qua suốt chuyển cảnh
            // Nền đang hiện clip trước (t < điểm nối) thì phủ clip sau với độ mờ p, và ngược lại.
            return t < noi ? { khac: sau, mo: p } : { khac: truoc, mo: 1 - p };
        }
        return null;
    }

    /* Lớp phụ cho chuyển cảnh: nằm ngay trên lớp nền (cùng z-index, đứng sau trong DOM). */
    _veChuyenCanh(t, phat) {
        const cc = this._chuyenCanhTai(t);
        if (!this.lopCC) {
            if (!cc) return;
            const el = document.createElement('div');
            el.className = 'lop-video';
            el.innerHTML = '<video preload="auto" playsinline muted></video><img alt="">';
            this.lopCC = { el, v: el.querySelector('video'), img: el.querySelector('img'), clip: null };
        }
        const l = this.lopCC;
        const nen = this.lop.get((trackVideoTuDuoiLen(this.tl)[0] || {}).id);
        if (!cc || !nen) {
            l.clip = null;
            l.v.pause();
            l.el.style.display = 'none';
            return;
        }
        if (nen.el.nextSibling !== l.el) this.cacLop.insertBefore(l.el, nen.el.nextSibling);
        l.el.style.zIndex = nen.el.style.zIndex;
        const tr = this.tl.tracks.find((x) => x.id === cc.khac.track) || {};
        if (l.clip !== cc.khac || !phat) this._hienLop(l, tr, cc.khac, t, phat);
        else if (l.v.readyState >= 1 && Math.abs(l.v.currentTime - thoiDiemMedia(cc.khac, t)) > LECH_TOI_DA) l.v.currentTime = thoiDiemMedia(cc.khac, t);
        // Khi xuất, tiếng cắt thẳng ở điểm nối — lớp phụ không phát tiếng.
        l.v.muted = true;
        l.el.style.opacity = String(cc.mo * Number((cc.khac.hien_thi || {}).do_mo ?? 1));
    }

    batTat() {
        if (this.nguon) {
            if (this.vNguon.paused) this.vNguon.play().catch(() => {}); else this.vNguon.pause();
            return;
        }
        if (this.dangPhat || this.chieuPhat === -1) this.dung(); else this.phat();
    }

    phatToiL() {
        if (this.chieuPhat === -1) {
            this.dung();
        }
        if (!this.dangPhat) {
            this.tocDoPhat = 1;
            this.phat();
        } else {
            this.tocDoPhat = this.tocDoPhat >= 4 ? 1 : this.tocDoPhat * 2;
        }
    }

    phatLuiJ() {
        if (this.dangPhat) {
            this.dung();
        }
        if (this.chieuPhat !== -1) {
            this.chieuPhat = -1;
            this.tocDoPhat = 1;
            this._batPhatLui();
        } else {
            this.tocDoPhat = this.tocDoPhat >= 4 ? 1 : this.tocDoPhat * 2;
        }
    }

    _batPhatLui() {
        clearInterval(this._hLui);
        this._veNut();
        this._hLui = setInterval(() => {
            if (this.chieuPhat !== -1) {
                clearInterval(this._hLui);
                return;
            }
            let t = this.ctx.ui.dau_phat - 0.1 * this.tocDoPhat;
            if (t <= 0) {
                t = 0;
                this.dung();
            }
            this.ctx.timeline.datDauPhat(t, 'phat', true);
            this.veTai(t);
        }, 100);
    }

    dung() {
        const dang = this.dangPhat || this.chieuPhat === -1;
        this.dangPhat = false;
        this.chieuPhat = 1;
        this.tocDoPhat = 1;
        cancelAnimationFrame(this._raf);
        clearInterval(this._hDuPhong);
        clearInterval(this._hLui);
        for (const l of this.lop.values()) l.v.pause();
        if (this.lopCC) this.lopCC.v.pause();
        this._anAmThanh();
        if (dang) { this.ctx.luuUi(); this._veTayNam(); }
        this._veNut();
    }

    _veNut() {
        const dang = this.nguon ? !this.vNguon.paused : (this.dangPhat || this.chieuPhat === -1);
        $('btnPhat').textContent = dang ? '⏸' : '▶';
    }
}
