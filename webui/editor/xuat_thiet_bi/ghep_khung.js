/* Ghép khung trên thiết bị: vẽ khung tại thời điểm t của timeline lên OffscreenCanvas kích thước xuất — CÙNG công thức
   với màn xem trước (store.js hopLop/giaTriTai/thoiDiemMedia, hieu_ung.js cssFilter): track video dưới → trên,
   vị trí/tỉ lệ/xoay + keyframe, cắt khung, bo góc, độ mờ, chỉnh màu cơ bản + hiệu ứng (CSS filter của canvas).
   Chuyển cảnh (track nền): như render.tinh_xfade — nằm GIỮA điểm cắt, clip trước kéo dài thêm dai/2, clip sau bắt đầu sớm dai/2
   (lấy tiếp media gốc, hết media thì giữ khung cuối/đầu); trộn bằng chuyen_canh_tb.js.
   Nguồn đọc file GỐC (?goc=1) — video điện thoại quay dọc được Mediabunny tự xoay theo thẻ khi vẽ.
   Mỗi clip giải mã TUẦN TỰ đúng các thời điểm khung cần (samplesAtTimestamps), mỗi khung kéo đúng một lần.
   Khung đánh số trên lưới fps xuất (n = t × fps, [n0, n1)). Khung server đã nướng (goi_nuong.js) → chép nguyên khung đó;
   vùng che phụ đề vẽ trên khung nguồn (che_tb.js); cuối cùng chồng lớp chữ/phụ đề libass server vẽ. */
import { giaTriTai, hopLop, ketThucClip, thoiDiemMedia, trackVideoTuDuoiLen } from '../store.js';
import { cssFilter } from '../hieu_ung.js';
import { NguonVideo } from './nguon_video.js';
import { veChuyenCanh } from './chuyen_canh_tb.js';
import { BoChe, cheCuaMedia } from './che_tb.js';

const trongCuaSo = (w, t) => t >= w.lo - 1e-6 && t < w.hi - 1e-6;

export class BoGhepKhung {
    /* du: {thong_so}, tl: timeline, media: [..], pid, W, H, fps, [n0, n1): khung xuất trên lưới fps */
    constructor({ du, tl, media, pid, W, H, fps, n0, n1 }) {
        Object.assign(this, { du, tl, pid, W, H, fps, n0, n1, t0: n0 / fps, t1: n1 / fps });
        this.nuong = null;           // KetQuaNuong — gắn sau khi server nướng xong
        this.nBatDau = n0;           // xuất tiếp: khung đầu tiên sẽ vẽ (các khúc trước đã có trong OPFS)
        this.khongGiaiMa = new Set();
        this.boChe = new BoChe();
        this.che = new Map();        // media id → vùng che
        this.media = Object.fromEntries(media.map((m) => [m.id, m]));
        const taoCv = () => { const cv = new OffscreenCanvas(W, H); return { cv, c: cv.getContext('2d', { alpha: false }) }; };
        ({ cv: this.cv, c: this.c } = taoCv());
        this.tamA = taoCv();
        this.tamB = taoCv();
        this.nguon = new Map();      // media id → NguonVideo | ImageBitmap
        this.luong = new Map();      // clip id → {it, mau, con}
        this.mauNen = (du.thong_so || {}).mau_nen || '#000000';
        this.tracks = trackVideoTuDuoiLen(tl).filter((t) => !t.an);
        this.cuaSo = this._tinhCuaSo();
    }

    /* Cửa sổ thời gian mỗi clip video cần khung: [lo, hi) — clip track nền có chuyển cảnh được nới dai/2 mỗi phía. */
    _tinhCuaSo() {
        const ra = new Map();
        const nen = this.tracks[0] && this.tracks[0].id;
        const ccMap = new Map((this.tl.chuyen_canh || []).map((cc) => [`${cc.truoc}|${cc.sau}`, cc]));
        for (const tr of this.tracks) {
            const ds = this.tl.clips.filter((c) => c.track === tr.id && c.media).sort((a, b) => a.bat_dau - b.bat_dau);
            ds.forEach((c, i) => {
                const bd = Number(c.bat_dau) || 0, kt = ketThucClip(c);
                let truoc = null, sau = null;
                if (tr.id === nen) {
                    const p = ds[i - 1], n = ds[i + 1];
                    if (p && Math.abs(ketThucClip(p) - bd) <= 0.05) truoc = ccMap.get(`${p.id}|${c.id}`) || null;
                    if (n && Math.abs(kt - Number(n.bat_dau)) <= 0.05) sau = ccMap.get(`${c.id}|${n.id}`) || null;
                }
                ra.set(c.id, { c, tr: tr.id, lo: bd - (truoc ? truoc.dai / 2 : 0), hi: kt + (sau ? sau.dai / 2 : 0), truoc, sau });
            });
        }
        return ra;
    }

    _url(mid) { return `/api/du-an/${encodeURIComponent(this.pid)}/media/${encodeURIComponent(mid)}/file?goc=1`; }

    /* Mở mọi media hình được dùng trong đoạn xuất. baoTienDo(i, n, ten). */
    async mo(baoTienDo = () => {}) {
        const can = new Set();
        for (const w of this.cuaSo.values()) if (w.hi > this.t0 && w.lo < this.t1) can.add(w.c.media);
        let i = 0;
        for (const mid of can) {
            const m = this.media[mid];
            baoTienDo(i++, can.size, m ? m.ten : mid);
            if (!m || (m.loai !== 'video' && m.loai !== 'anh')) continue;
            if (m.loai === 'anh') {
                this.nguon.set(mid, await createImageBitmap(await (await fetch(this._url(mid))).blob()));
            } else {
                const n = await NguonVideo.mo(this._url(mid));
                if (!n.giaiMaDuoc) { this.khongGiaiMa.add(mid); n.dong(); continue; }   // server nướng các khung dùng nó
                this.nguon.set(mid, n);
            }
        }
    }

    _layLuong(w, n) {
        let l = this.luong.get(w.c.id);
        if (l) return l;
        // Đúng các khung xuất mà veKhung sẽ hỏi clip này (cùng điều kiện trongCuaSo) → mỗi khung kéo đúng một lần.
        const ds = [];
        for (let k = Math.max(this.nBatDau, Math.floor(w.lo * this.fps) - 1); k < this.n1; k++) {
            const t = k / this.fps;
            if (t >= w.hi) break;
            if (trongCuaSo(w, t) && !(this.nuong && this.nuong.laNuong(k))) {
                ds.push(Math.max(0, Math.min(n.thoiLuong - 1e-3, thoiDiemMedia(w.c, t))));
            }
        }
        l = { it: n.khungTai(ds)[Symbol.asyncIterator](), mau: null, con: ds.length };
        this.luong.set(w.c.id, l);
        return l;
    }

    async _khung(w) {
        const m = this.media[w.c.media], n = this.nguon.get(w.c.media);
        if (!m || !n) return null;
        if (m.loai === 'anh') return n;
        const l = this._layLuong(w, n);
        if (l.con > 0) {
            const r = await l.it.next();
            l.con--;
            if (!r.done && r.value) { if (l.mau) l.mau.close(); l.mau = r.value; }
        }
        return l.mau;
    }

    _ve(ctx, c, nguon, t) {
        const m = this.media[c.media];
        const tCuc = t - (Number(c.bat_dau) || 0);
        const bd = {};
        for (const k of ['x', 'y', 'ti_le', 'xoay']) {
            const v = giaTriTai(c, `bien_doi.${k}`, tCuc);
            if (v != null && !Number.isNaN(Number(v))) bd[k] = Number(v);   // thiếu → hopLop lấy mặc định
        }
        const hop = hopLop({ ...c, bien_doi: bd }, m, this.W, this.H);
        const k = c.cat_khung || {}, h = c.hien_thi || {};
        const doMo = Number(giaTriTai(c, 'hien_thi.do_mo', tCuc) ?? h.do_mo ?? 1);
        ctx.save();
        ctx.globalAlpha = Math.max(0, Math.min(1, Number.isNaN(doMo) ? 1 : doMo));
        if (h.hoa_tron && h.hoa_tron !== 'normal') ctx.globalCompositeOperation = h.hoa_tron;
        ctx.translate(hop.cx, hop.cy);
        if (hop.xoay) ctx.rotate(hop.xoay * Math.PI / 180);
        const x0 = -hop.w / 2, y0 = -hop.h / 2;
        // Cắt khung + bo góc như clip-path: inset(%) round r của màn xem trước.
        const pc = (v) => Math.max(0, Math.min(1, Number(v || 0)));
        const tr = pc(k.trai) * hop.w, ph = pc(k.phai) * hop.w, tp = pc(k.tren) * hop.h, du = pc(k.duoi) * hop.h;
        const r = Number(h.bo_goc || 0) * this.H / 1080;
        if (tr || ph || tp || du || r) {
            ctx.beginPath();
            ctx.roundRect(x0 + tr, y0 + tp, hop.w - tr - ph, hop.h - tp - du, r);
            ctx.clip();
        }
        if (m && m.loai === 'video') {
            if (!this.che.has(c.media)) this.che.set(c.media, cheCuaMedia(this.tl, c.media));
            const da = this.boChe.ap(nguon, hop.w, hop.h, this.che.get(c.media), thoiDiemMedia(c, t), m.rong || nguon.displayWidth);
            if (da) nguon = da;
        }
        ctx.filter = cssFilter(c.mau, c.hieu_ung, 1);
        if (nguon.draw) nguon.draw(ctx, x0, y0, hop.w, hop.h);
        else ctx.drawImage(nguon, x0, y0, hop.w, hop.h);
        ctx.restore();
    }

    _nen(ctx) {
        this._chuan(ctx);
        ctx.fillStyle = this.mauNen;
        ctx.fillRect(0, 0, this.W, this.H);
    }

    /* Khung n (lưới fps, gọi tăng dần) — trả OffscreenCanvas (vẽ lại tại chỗ: dùng xong mới gọi lần sau). */
    async veKhung(n) {
        await this._veHinh(n);
        const anh = this.nuong && await this.nuong.anhChu(n);
        if (anh) {
            this._chuan(this.c);
            this.c.drawImage(anh, 0, 0, this.W, this.H);
        }
        return this.cv;
    }

    _chuan(ctx) {
        ctx.globalAlpha = 1;
        ctx.globalCompositeOperation = 'source-over';
        ctx.filter = 'none';
    }

    async _veHinh(n) {
        const t = n / this.fps;
        this._nen(this.c);
        if (this.nuong && this.nuong.laNuong(n)) {
            const kh = await this.nuong.khungNuong();
            if (kh) kh.draw(this.c, 0, 0, this.W, this.H);
            return;
        }
        for (const tr of this.tracks) {
            const ds = [...this.cuaSo.values()].filter((w) => w.tr === tr.id && trongCuaSo(w, t))
                .sort((a, b) => a.c.bat_dau - b.c.bat_dau);
            if (ds.length >= 2 && ds[0].sau) {
                // Chuyển cảnh: A, B vẽ riêng trên nền rồi trộn (xfade trộn hai khung track nền đầy đủ).
                const [a, b] = ds, cc = a.sau, cat = Number(b.c.bat_dau);
                const [ka, kb] = [await this._khung(a), await this._khung(b)];
                this._nen(this.tamA.c); if (ka) this._ve(this.tamA.c, a.c, ka, t);
                this._nen(this.tamB.c); if (kb) this._ve(this.tamB.c, b.c, kb, t);
                veChuyenCanh(this.c, this.tamA.cv, this.tamB.cv, cc.loai, (t - (cat - cc.dai / 2)) / cc.dai, this.W, this.H);
                continue;
            }
            for (const w of ds) {
                const kh = await this._khung(w);
                if (kh) this._ve(this.c, w.c, kh, t);
            }
        }
    }

    dong() {
        for (const l of this.luong.values()) { if (l.mau) l.mau.close(); if (l.it.return) l.it.return(); }
        for (const n of this.nguon.values()) { if (n.dong) n.dong(); else if (n.close) n.close(); }
        this.luong.clear();
        this.nguon.clear();
        if (this.nuong) this.nuong.dong();
    }
}
