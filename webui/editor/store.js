/* Trạng thái timeline + hoàn tác/làm lại kiểu LỆNH (patch trước/sau).
 *
 * Mỗi thao tác sửa là một lệnh {ten, ops}. Một op là một trong:
 *   {op:'dat',  path, cu, moi}           gán giá trị (cu = giá trị trước, để đảo ngược)
 *   {op:'them', path, vi_tri, gia_tri}   chèn vào mảng tại path
 *   {op:'xoa',  path, vi_tri, gia_tri}   bỏ khỏi mảng tại path
 * `path` là mảng khoá; phần tử {id:'c_1'} = tìm trong mảng theo id (ổn định hơn chỉ số
 * khi các lệnh khác đã chèn/xoá). Lệnh JSON được nên ghi thẳng vào hoan_tac.json:
 * mở lại dự án vẫn Ctrl+Z được.
 *
 * Module KHÔNG đụng DOM — test bằng `node --test tests/js/`.
 */

export const GIOI_HAN_BO_NHO = 100;
export const GIOI_HAN_GHI = 50;

const sao = (v) => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));

function buoc(cha, khoa) {
    if (khoa && typeof khoa === 'object') {
        if (!Array.isArray(cha)) throw new Error(`Không tìm theo id trong thứ không phải mảng: ${JSON.stringify(khoa)}`);
        const i = cha.findIndex((x) => x && x.id === khoa.id);
        if (i < 0) throw new Error(`Không có phần tử id=${khoa.id}`);
        return i;
    }
    return khoa;
}

export function doc(goc, path) {
    let cur = goc;
    for (const k of path) {
        if (cur == null) return undefined;
        cur = cur[buoc(cur, k)];
    }
    return cur;
}

function chaVaKhoa(goc, path) {
    if (!path.length) throw new Error('path rỗng');
    const cha = doc(goc, path.slice(0, -1));
    if (cha == null) throw new Error(`Không có đường dẫn ${JSON.stringify(path.slice(0, -1))}`);
    return [cha, buoc(cha, path[path.length - 1])];
}

export function apOp(goc, op) {
    if (op.op === 'dat') {
        const [cha, k] = chaVaKhoa(goc, op.path);
        if (op.moi === undefined) delete cha[k];
        else cha[k] = sao(op.moi);
    } else if (op.op === 'them' || op.op === 'xoa') {
        const mang = doc(goc, op.path);
        if (!Array.isArray(mang)) throw new Error(`${JSON.stringify(op.path)} không phải mảng`);
        const i = Math.max(0, Math.min(op.vi_tri, mang.length));
        if (op.op === 'them') mang.splice(i, 0, sao(op.gia_tri));
        else mang.splice(i, 1);
    } else {
        throw new Error(`op lạ: ${op.op}`);
    }
}

export function daoOp(op) {
    if (op.op === 'dat') return { ...op, cu: op.moi, moi: op.cu };
    if (op.op === 'them') return { ...op, op: 'xoa' };
    if (op.op === 'xoa') return { ...op, op: 'them' };
    throw new Error(`op lạ: ${op.op}`);
}

/* Trình tạo op đọc giá trị hiện tại — người gọi không phải tự nhớ "cu". */
export const tao = {
    dat: (goc, path, moi) => ({ op: 'dat', path, cu: sao(doc(goc, path)), moi: sao(moi) }),
    them: (goc, path, giaTri, viTri) => {
        const mang = doc(goc, path) || [];
        return { op: 'them', path, vi_tri: viTri == null ? mang.length : viTri, gia_tri: sao(giaTri) };
    },
    xoaTheoId: (goc, path, id) => {
        const mang = doc(goc, path) || [];
        const i = mang.findIndex((x) => x && x.id === id);
        if (i < 0) throw new Error(`Không có id=${id}`);
        return { op: 'xoa', path, vi_tri: i, gia_tri: sao(mang[i]) };
    },
};

export class Store {
    /**
     * @param {object} timeline  timeline đọc từ server
     * @param {object|null} ngan {hoan_tac:[lệnh], lam_lai:[lệnh]} từ hoan_tac.json (null = trống)
     */
    constructor(timeline, ngan = null) {
        this.timeline = timeline;
        this.hoanTac = (ngan && Array.isArray(ngan.hoan_tac)) ? ngan.hoan_tac : [];
        this.lamLai = (ngan && Array.isArray(ngan.lam_lai)) ? ngan.lam_lai : [];
        this.chiDoc = false;
        this._nghe = new Set();
    }

    nghe(fn) { this._nghe.add(fn); return () => this._nghe.delete(fn); }

    _bao(loai, lenh) { this._nghe.forEach((fn) => fn(loai, lenh)); }

    /**
     * Áp một lệnh. `gop`: hai lệnh liên tiếp cùng khoá gộp trong 800 ms (vd kéo thanh
     * trượt) thành MỘT bước hoàn tác — giữ giá trị "cu" của lệnh đầu.
     */
    thucHien(ten, ops, { gop = null, bayGio = Date.now() } = {}) {
        if (this.chiDoc) throw new Error('Dự án đang mở chỉ xem — không sửa được.');
        if (!ops || !ops.length) return null;

        const nhap = JSON.parse(JSON.stringify(this.timeline));
        for (const op of ops) apOp(nhap, op);
        const ccMoi = chuyenCanhHopLe(nhap);
        if (JSON.stringify(nhap.chuyen_canh || []) !== JSON.stringify(ccMoi)) {
            ops.push(tao.dat(nhap, ['chuyen_canh'], ccMoi));
        }

        const daAp = [];
        try {
            for (const op of ops) { apOp(this.timeline, op); daAp.push(op); }
        } catch (e) {
            // Áp dở thì trả lại nguyên trạng — timeline không bao giờ nằm ở trạng thái nửa vời.
            for (const op of daAp.reverse()) apOp(this.timeline, daoOp(op));
            throw e;
        }
        const cuoi = this.hoanTac[this.hoanTac.length - 1];
        let lenh;
        if (gop && cuoi && cuoi.gop === gop && bayGio - cuoi.luc < 800 && coTheGop(cuoi.ops, ops)) {
            cuoi.ops = cuoi.ops.map((op, i) => ({ ...op, moi: sao(ops[i].moi) }));
            cuoi.luc = bayGio;
            lenh = cuoi;
        } else {
            lenh = { ten, ops, luc: bayGio, ...(gop ? { gop } : {}) };
            this.hoanTac.push(lenh);
            if (this.hoanTac.length > GIOI_HAN_BO_NHO) this.hoanTac.splice(0, this.hoanTac.length - GIOI_HAN_BO_NHO);
        }
        this.lamLai = [];
        this._bao('sua', lenh);
        return lenh;
    }

    hoanTacMot() {
        if (this.chiDoc) return null;
        const lenh = this.hoanTac.pop();
        if (!lenh) return null;
        for (const op of lenh.ops.slice().reverse()) apOp(this.timeline, daoOp(op));
        this.lamLai.push(lenh);
        this._bao('hoan_tac', lenh);
        return lenh;
    }

    lamLaiMot() {
        if (this.chiDoc) return null;
        const lenh = this.lamLai.pop();
        if (!lenh) return null;
        for (const op of lenh.ops) apOp(this.timeline, op);
        this.hoanTac.push(lenh);
        this._bao('lam_lai', lenh);
        return lenh;
    }

    /* Ngăn hoàn tác để ghi xuống đĩa (50 bước cuối). */
    ngan() {
        return {
            hoan_tac: this.hoanTac.slice(-GIOI_HAN_GHI).map(({ gop, ...l }) => l),
            lam_lai: this.lamLai.slice(-GIOI_HAN_GHI).map(({ gop, ...l }) => l),
        };
    }

    /* Thay cả timeline (khôi phục phiên bản) như MỘT lệnh hoàn tác được. */
    thayToanBo(ten, moi) {
        const ops = [];
        const khoa = new Set([...Object.keys(this.timeline), ...Object.keys(moi)]);
        khoa.delete('phien_ban');
        for (const k of khoa) {
            if (JSON.stringify(this.timeline[k]) !== JSON.stringify(moi[k])) ops.push(tao.dat(this.timeline, [k], moi[k]));
        }
        return this.thucHien(ten, ops);
    }
}

function coTheGop(a, b) {
    return a.length === b.length && a.every((op, i) => op.op === 'dat' && b[i].op === 'dat'
        && JSON.stringify(op.path) === JSON.stringify(b[i].path));
}

/* --------------------------------------------------------------- tiện ích timeline */
export function clipChuMacDinh(id, track, bd, dai, laTieuDe) {
    return {
        id, track, loai: 'chu', bat_dau: bd, ket_thuc: bd + dai,
        noi_dung: laTieuDe ? 'Tiêu đề' : 'Chữ mới',
        kieu: laTieuDe 
            ? { font: 'Arial', co: 100, mau: '#ffffff', vien_mau: '#000000', vien_day: 2, bong: 0 }
            : { font: 'Arial', co: 48, mau: '#ffffff', vien_mau: '#000000', vien_day: 0, bong: 0 },
        bien_doi: { x: 0.5, y: 0.5, ti_le: 1.0, xoay: 0 },
        hien_thi: { do_mo: 1.0 },
        hieu_ung_vao: 'khong', hieu_ung_ra: 'khong'
    };
}

export function clipHinhMacDinh(id, track, bd, dai, dang) {
    return {
        id, track, loai: 'hinh', bat_dau: bd, ket_thuc: bd + dai,
        dang: dang || 'chu_nhat', mau: '#ffffff', do_mo: 1.0,
        vien_mau: '#000000', vien_day: 0, so_canh: dang === 'da_giac' ? 5 : undefined,
        bien_doi: { x: 0.5, y: 0.5, rong: 0.2, cao: 0.2, xoay: 0 },
        hieu_ung_vao: 'khong', hieu_ung_ra: 'khong'
    };
}

export function nhanClip(c, m) {
    if (c.loai === 'che_phu_de') return `▦ Che (${c.kieu || 'blur'})`;
    if (c.loai === 'chu') return (c.noi_dung || '').replace(/\n/g, ' ');
    if (c.loai === 'hinh') return `⬠ Hình (${c.dang || 'chu_nhat'})`;
    return c.text || (m && m.ten) || c.loai || c.id;
}

export function ketThucClip(c) {
    if (c.ket_thuc != null) return Number(c.ket_thuc);
    const toc = Number(c.toc_do) || 1;
    return Number(c.bat_dau || 0) + (Number(c.ra || 0) - Number(c.vao || 0)) / toc;
}

export function thoiLuong(tl) {
    // Phụ đề/vùng che NEO theo media luôn nằm trong clip media đó → không tự kéo dài timeline.
    return (tl.clips || []).reduce((m, c) => (laNeo(c) ? m : Math.max(m, ketThucClip(c))), 0);
}

/* ------------------------------------------- phụ đề / vùng che neo theo media gốc
 * Bản JS của orchestrator/editor/quy_doi.py — chạy chung ca test tests/js/ca_quy_doi.json. */
export const laNeo = (c) => !!c.tu_media && c.t_vao != null && c.t_ra != null;

/* Bảng media → clip chứa nó (cùng luật với clipChuaMedia), dựng MỘT lần cho cả lượt vẽ.
   Gọi clipChuaMedia cho từng câu phụ đề là quét toàn bộ clip mỗi câu: dự án 1925 câu ≈ 3,7 triệu lượt mỗi lần vẽ
   → timeline đứng ~0,5 s mỗi lần zoom/kéo, preview giật khi phát. */
export function bangClipChuaMedia(tl) {
    const loai = Object.fromEntries((tl.tracks || []).map((t) => [t.id, t.loai]));
    const theoMedia = new Map();
    for (const c of tl.clips || []) {
        if (!c.media) continue;
        const l = loai[c.track];
        if (l !== 'video' && l !== 'audio') continue;
        if (!theoMedia.has(c.media)) theoMedia.set(c.media, { video: [], audio: [] });
        theoMedia.get(c.media)[l].push(c);
    }
    const bang = new Map();
    for (const [mid, x] of theoMedia) bang.set(mid, x.video.length ? x.video : x.audio);
    return bang;
}

export function clipChuaMedia(tl, mid) {
    const loai = Object.fromEntries((tl.tracks || []).map((t) => [t.id, t.loai]));
    const cac = (tl.clips || []).filter((c) => c.media === mid);
    const video = cac.filter((c) => loai[c.track] === 'video');
    return video.length ? video : cac.filter((c) => loai[c.track] === 'audio');
}

const tron6 = (x) => Math.round(x * 1e6) / 1e6;

export function hienThiNeo(tl, c, bang = null) {
    if (!laNeo(c)) {
        if (c.bat_dau == null) return [];
        return [{ bd: Number(c.bat_dau), kt: ketThucClip(c), clip: null }];
    }
    const tv = Number(c.t_vao), tr = Number(c.t_ra);
    const out = [];
    for (const v of (bang ? (bang.get(c.tu_media) || []) : clipChuaMedia(tl, c.tu_media))) {
        const vao = Number(v.vao || 0), ra = Number(v.ra || 0);
        const lo = Math.max(tv, vao), hi = Math.min(tr, ra);
        if (hi - lo <= 1e-6) continue;
        const toc = Number(v.toc_do) || 1, bd0 = Number(v.bat_dau || 0);
        out.push({ bd: tron6(bd0 + (lo - vao) / toc), kt: tron6(bd0 + (hi - vao) / toc), clip: v.id });
    }
    return out.sort((a, b) => a.bd - b.bd);
}

/* Các clip phụ đề/che (theo track) đang hiện tại thời điểm t, kèm khoảng hiện và clip media chứa nó. */
export function neoTai(tl, loai, t) {
    const an = new Set((tl.tracks || []).filter((x) => x.an).map((x) => x.id));
    const out = [];
    const bang = bangClipChuaMedia(tl);
    for (const c of tl.clips || []) {
        if (c.loai !== loai || an.has(c.track)) continue;
        for (const k of hienThiNeo(tl, c, bang)) {
            if (t >= k.bd - 1e-6 && t < k.kt - 1e-6) out.push({ c, ...k });
        }
    }
    return out;
}

/* ------------------------------------------------------------ lớp video (GĐ 2)
 * Track video nằm TRÊN trong danh sách thì hiện ĐÈ lên (như Premiere/CapCut); track video
 * cuối cùng là nền (ghép bằng concat khi xuất). Bản Python tương ứng: render.hop_lop. */
export const BIEN_DOI_MAC_DINH = { x: 0.5, y: 0.5, ti_le: 1, xoay: 0 };

/* Track video từ DƯỚI lên TRÊN (nền trước). */
export function trackVideoTuDuoiLen(tl) {
    return (tl.tracks || []).filter((t) => t.loai === 'video').reverse();
}

export function laLopMacDinh(c) {
    const b = c.bien_doi || {}, k = c.cat_khung || {}, h = c.hien_thi || {};
    return (b.x ?? 0.5) === 0.5 && (b.y ?? 0.5) === 0.5 && (b.ti_le ?? 1) === 1 && !(b.xoay || 0)
        && !(k.trai || k.phai || k.tren || k.duoi) && (h.do_mo ?? 1) === 1 && !(h.bo_goc || 0);
}

/* Hộp của lớp trong khung W×H: media vừa khung (contain) × tỉ lệ, tâm ở (x·W, y·H), rồi xoay.
 * Trả thêm phần hiện sau khi cắt khung (tính theo phần trăm của hộp). */
export function hopLop(c, m, W, H) {
    const b = { ...BIEN_DOI_MAC_DINH, ...(c.bien_doi || {}) };
    const mw = Number(m && m.rong) || W, mh = Number(m && m.cao) || H;
    const k = Math.min(W / mw, H / mh) * Number(b.ti_le || 1);
    const w = mw * k, h = mh * k;
    return { cx: Number(b.x) * W, cy: Number(b.y) * H, w, h, xoay: Number(b.xoay || 0) };
}

/* Id track mới theo tiền tố: V → V2, V3…; A → A2…; S → S2…; O → O2… */
export function idTrackMoi(tl, tienTo) {
    const so = (tl.tracks || []).map((t) => new RegExp(`^${tienTo}(\\d+)$`).exec(t.id)).filter(Boolean).map((x) => Number(x[1]));
    return `${tienTo}${(so.length ? Math.max(...so) : 0) + 1}`;
}

const TIEN_TO = { video: 'V', audio: 'A', phu_de: 'S', lop_phu: 'O' };

/* Ops thêm track: video mới nằm TRÊN cùng các track video (hiện đè lên), loại khác nối sau cùng loại. */
export function opsThemTrack(tl, loai) {
    const id = idTrackMoi(tl, TIEN_TO[loai] || 'T');
    const tr = { id, loai, ten: id, an: false, khoa: false, tat_tieng: false };
    const ds = tl.tracks || [];
    let viTri;
    if (loai === 'video') viTri = ds.findIndex((t) => t.loai === 'video');
    else {
        const cuoi = ds.map((t, i) => [t, i]).filter(([t]) => t.loai === loai).pop();
        viTri = cuoi ? cuoi[1] + 1 : ds.length;
    }
    if (viTri < 0) viTri = 0;
    return { id, ops: [{ op: 'them', path: ['tracks'], vi_tri: viTri, gia_tri: tr }] };
}

export function idNhomMoi(tl) {
    const cacNh = (tl.clips || []).map(c => /^lk_(\d+)$/.exec(c.lien_ket || '')).filter(Boolean).map(m => Number(m[1]));
    return `lk_${(cacNh.length ? Math.max(...cacNh) : 0) + 1}`;
}

/* Ops tách âm thanh của clip video ra track âm thanh (track trống đoạn đó, không có thì tạo mới). */
export function opsTachAm(tl, cid) {
    const c = (tl.clips || []).find((x) => x.id === cid);
    if (!c) return null;
    const bd = Number(c.bat_dau || 0), kt = ketThucClip(c);
    const nhap = JSON.parse(JSON.stringify(tl));
    const ops = [];
    let tr = (nhap.tracks || []).find((t) => t.loai === 'audio' && !t.vai && !t.khoa && !chongClip(nhap, t.id, bd, kt));
    if (!tr) {
        const moi = opsThemTrack(nhap, 'audio');
        ops.push(...moi.ops);
        moi.ops.forEach((o) => nhap.tracks.splice(o.vi_tri, 0, o.gia_tri));
        tr = nhap.tracks.find((t) => t.id === moi.id);
    }
    const nhomId = idNhomMoi(nhap);
    const id = idClipMoi(nhap);
    ops.push({ op: 'them', path: ['clips'], vi_tri: nhap.clips.length, gia_tri: {
        id, track: tr.id, media: c.media, bat_dau: c.bat_dau, vao: c.vao, ra: c.ra, toc_do: c.toc_do || 1,
        am_luong: c.am_luong ?? 1, am_vao: c.am_vao || 0, am_ra: c.am_ra || 0, tach_tu: c.id, lien_ket: nhomId,
    } });
    ops.push(tao.dat(tl, ['clips', { id: cid }, 'tat_am'], true));
    ops.push(tao.dat(tl, ['clips', { id: cid }, 'lien_ket'], nhomId));
    return { id, track: tr.id, ops };
}

export function moRongNhom(tl, ids) {
    const mo = new Set(ids);
    const cacNhom = new Set(ids.map(id => tl.clips.find(c => c.id === id)?.lien_ket).filter(Boolean));
    if (cacNhom.size > 0) {
        tl.clips.forEach(c => {
            if (c.lien_ket && cacNhom.has(c.lien_ket)) mo.add(c.id);
        });
    }
    return Array.from(mo);
}

/* Hệ số âm lượng tại thời điểm t (fade vào/ra tính bằng giây trên timeline). */
export function heSoFade(c, t) {
    const bd = Number(c.bat_dau || 0), kt = ketThucClip(c);
    let g = 1;
    if (Number(c.am_vao) > 0) g = Math.min(g, (t - bd) / Number(c.am_vao));
    if (Number(c.am_ra) > 0) g = Math.min(g, (kt - t) / Number(c.am_ra));
    return Math.max(0, Math.min(1, g));
}

/* Kiểu chữ phụ đề mặc định — khớp luu_tru.kieu_phu_de_mac_dinh() bên Python. */
export const kieuPhuDeMacDinh = () => ({ font: '', co: 48, mau: '#ffffff', vien: '#000000', do_day_vien: 2, nen: 'None', mau_nen: '#000000', vi_tri_y: 0.9 });

/* Tạo n id clip mới liên tiếp (c_N…). */
export function idMoiNhieu(tl, n) {
    const dau = Number(idClipMoi(tl).slice(2));
    return Array.from({ length: n }, (_, i) => `c_${dau + i}`);
}

/* Ops thêm một loạt câu phụ đề NEO theo media `mid` (giờ trong media gốc) vào track `trackId`. */
export function opsThemCau(tl, trackId, mid, cau) {
    const ids = idMoiNhieu(tl, cau.length);
    const mang = tl.clips || [];
    return cau.map((x, i) => ({
        op: 'them', path: ['clips'], vi_tri: mang.length + i,
        gia_tri: {
            id: ids[i], track: trackId, loai: 'phu_de',
            ...(mid ? { tu_media: mid, t_vao: x.t_vao, t_ra: x.t_ra } : { bat_dau: x.t_vao, ket_thuc: x.t_ra }),
            text: x.text, text_goc: x.text_goc ?? x.text, kieu: 'k_mac_dinh',
        },
    }));
}

/* Ops xoá nhiều clip theo id (xoá từ cuối lên để chỉ số không dời). */
export function opsXoaNhieu(tl, ids) {
    const bo = new Set(ids);
    return (tl.clips || []).map((c, i) => [c, i]).filter(([c]) => bo.has(c.id)).reverse()
        .map(([c, i]) => ({ op: 'xoa', path: ['clips'], vi_tri: i, gia_tri: JSON.parse(JSON.stringify(c)) }));
}

/* Câu phụ đề neo vào media `mid`, theo giờ trong media. */
export function cauCuaMedia(tl, mid) {
    return (tl.clips || []).filter((c) => c.loai === 'phu_de' && c.tu_media === mid)
        .sort((a, b) => a.t_vao - b.t_vao);
}

/* Danh sách câu hiển thị (giờ TIMELINE) — mỗi lần hiện là một dòng, dùng cho bảng Phụ đề và xuất .srt. */
export function dongPhuDe(tl) {
    const out = [];
    const bang = bangClipChuaMedia(tl);
    for (const c of tl.clips || []) {
        if (c.loai !== 'phu_de') continue;
        const hien = hienThiNeo(tl, c, bang);
        if (!hien.length) out.push({ c, bd: null, kt: null, clip: null });
        for (const k of hien) out.push({ c, ...k });
    }
    return out.sort((a, b) => (a.bd ?? 1e12) - (b.bd ?? 1e12) || (a.c.t_vao ?? 0) - (b.c.t_vao ?? 0));
}

function srtGio(t) {
    let ms = Math.round(Math.max(0, t) * 1000);
    const h = Math.floor(ms / 3600000); ms -= h * 3600000;
    const m = Math.floor(ms / 60000); ms -= m * 60000;
    const s = Math.floor(ms / 1000); ms -= s * 1000;
    const p = (n, k = 2) => String(n).padStart(k, '0');
    return `${p(h)}:${p(m)}:${p(s)},${p(ms, 3)}`;
}

export function srtTuTimeline(tl) {
    return dongPhuDe(tl).filter((d) => d.bd != null && (d.c.text || '').trim())
        .map((d, i) => `${i + 1}\n${srtGio(d.bd)} --> ${srtGio(d.kt)}\n${d.c.text.trim()}\n`).join('\n');
}

/* Ops dời/tỉa một câu (hoặc vùng che) theo GIỜ TIMELINE mới, qua clip media `vid` đang chứa nó. */
export function opsDatGio(tl, c, vid, bdMoi, ktMoi) {
    const p = (k) => ['clips', { id: c.id }, k];
    if (laNeo(c) && vid) {
        const tv = Math.round(veMedia(tl, vid, bdMoi) * 1000) / 1000;
        const tr = Math.round(veMedia(tl, vid, ktMoi) * 1000) / 1000;
        return [tao.dat(tl, p('t_vao'), tv), tao.dat(tl, p('t_ra'), tr)];
    }
    return [tao.dat(tl, p('bat_dau'), Math.round(bdMoi * 1000) / 1000), tao.dat(tl, p('ket_thuc'), Math.round(ktMoi * 1000) / 1000)];
}

/* Đổi thời điểm trên timeline về giây trong media gốc, qua clip media `vid` (dùng khi sửa giờ phụ đề). */
export function veMedia(tl, vid, t) {
    const v = (tl.clips || []).find((x) => x.id === vid);
    if (!v) return t;
    return Number(v.vao || 0) + (t - Number(v.bat_dau || 0)) * (Number(v.toc_do) || 1);
}

export function idClipMoi(tl) {
    const so = (tl.clips || []).map((c) => /^c_(\d+)$/.exec(c.id || '')).filter(Boolean).map((m) => Number(m[1]));
    return `c_${(so.length ? Math.max(...so) : 0) + 1}`;
}

/* Clip của track đang nằm dưới thời điểm t (null nếu khoảng trống). */
export function clipTai(tl, trackId, t) {
    return (tl.clips || []).find((c) => c.track === trackId
        && t >= Number(c.bat_dau || 0) - 1e-6 && t < ketThucClip(c) - 1e-6) || null;
}

/* Vị trí trong media gốc ứng với thời điểm t trên timeline. */
export function thoiDiemMedia(c, t) {
    return Number(c.vao || 0) + (t - Number(c.bat_dau || 0)) * (Number(c.toc_do) || 1);
}

/* Bắt dính: t gần điểm nào trong `diem` dưới `nguong` giây thì hút vào điểm đó. */
export function hutDinh(t, diem, nguong) {
    let tot = t, kc = nguong;
    for (const d of diem) {
        if (Math.abs(d - t) <= kc) { kc = Math.abs(d - t); tot = d; }
    }
    return tot;
}

/* Các điểm bắt dính: 0, đầu phát, hai mép mọi clip (trừ clip đang kéo). */
export function diemDinh(tl, dauPhat, boQua = []) {
    const d = [0, dauPhat];
    for (const c of tl.clips || []) {
        if (boQua.includes(c.id)) continue;
        d.push(Number(c.bat_dau || 0), ketThucClip(c));
    }
    for (const m of tl.danh_dau || []) d.push(Number(m.t));
    return d;
}

/* Có chồng clip khác trên track không (bỏ qua các id trong `boQua`). */
export function chongClip(tl, trackId, bd, kt, boQua = []) {
    return (tl.clips || []).some((c) => c.track === trackId && !boQua.includes(c.id)
        && bd < ketThucClip(c) - 1e-6 && kt > Number(c.bat_dau || 0) + 1e-6);
}

/* Giới hạn tỉa: không chồng clip bên cạnh, không vượt media gốc (ảnh thì kéo dài thoải mái). */
export function gioiHanTia(tl, c, daiMedia, laAnh) {
    const toc = Number(c.toc_do) || 1;
    const bd = Number(c.bat_dau || 0), kt = ketThucClip(c);
    const cung = (tl.clips || []).filter((x) => x.track === c.track && x.id !== c.id);
    const truoc = cung.map(ketThucClip).filter((e) => e <= bd + 1e-6);
    const sau = cung.map((x) => Number(x.bat_dau || 0)).filter((s) => s >= kt - 1e-6);
    const khongMedia = (c.ket_thuc != null);
    const sanTrai = Math.max(truoc.length ? Math.max(...truoc) : 0,
        (laAnh || khongMedia) ? 0 : bd - Number(c.vao || 0) / toc);
    const tranPhai = Math.min(sau.length ? Math.min(...sau) : Infinity,
        (laAnh || !daiMedia || khongMedia) ? Infinity : kt + (daiMedia - Number(c.ra || 0)) / toc);
    return { sanTrai: Math.max(0, sanTrai), tranPhai };
}

/* Ops cắt clip tại t: clip cũ kết thúc ở t, clip mới (idMoi) bắt đầu ở t. null nếu t không nằm trong clip. */
export function tachKeyframes(c, tCucBo) {
    if (!c.keyframes) return { kfTruoc: undefined, kfSau: undefined };
    const kfTruoc = {};
    const kfSau = {};
    for (const d of Object.keys(c.keyframes)) {
        if (!c.keyframes[d] || !c.keyframes[d].length) continue;
        const diem = c.keyframes[d].sort((a, b) => a.t - b.t);
        const vCucBo = giaTriTai(c, d, tCucBo);
        
        const truoc = diem.filter(k => k.t < tCucBo - 1e-6).map(k => ({...k}));
        const prev = diem.filter(k => k.t <= tCucBo).pop();
        truoc.push({ t: tCucBo, v: vCucBo, em: prev ? prev.em : 'tuyen_tinh' });
        kfTruoc[d] = truoc;
        
        const sau = diem.filter(k => k.t > tCucBo + 1e-6).map(k => ({...k, t: Math.round((k.t - tCucBo)*1000)/1000}));
        const prevSau = diem.filter(k => k.t <= tCucBo).pop();
        sau.unshift({ t: 0, v: vCucBo, em: prevSau ? prevSau.em : 'tuyen_tinh' });
        kfSau[d] = sau;
    }
    return { kfTruoc, kfSau };
}

/* Ops cắt clip tại t: clip cũ kết thúc ở t, clip mới (idMoi) bắt đầu ở t. null nếu t không nằm trong clip. */
export function opsTach(tl, cid, t, idMoi) {
    const c = (tl.clips || []).find((x) => x.id === cid);
    if (!c) return null;
    const bd = Number(c.bat_dau || 0), kt = ketThucClip(c);
    if (t <= bd + 0.02 || t >= kt - 0.02) return null;
    
    const moi = { ...JSON.parse(JSON.stringify(c)), id: idMoi, bat_dau: Math.round(t * 1000) / 1000 };
    const i = tl.clips.indexOf(c);
    
    const { kfTruoc, kfSau } = tachKeyframes(c, t - bd);
    if (kfSau) moi.keyframes = kfSau;
    
    const ops = [];
    if (kfTruoc) ops.push(tao.dat(tl, ['clips', { id: cid }, 'keyframes'], kfTruoc));
    
    if (c.ket_thuc != null) {
        moi.ket_thuc = c.ket_thuc;
        ops.push(tao.dat(tl, ['clips', { id: cid }, 'ket_thuc'], moi.bat_dau));
        ops.push({ op: 'them', path: ['clips'], vi_tri: i + 1, gia_tri: moi });
        return ops;
    }
    
    const giua = Math.round(thoiDiemMedia(c, t) * 1000) / 1000;
    moi.vao = giua;
    ops.push(tao.dat(tl, ['clips', { id: cid }, 'ra'], giua));
    ops.push({ op: 'them', path: ['clips'], vi_tri: i + 1, gia_tri: moi });
    return ops;
}

/* Chỗ đặt clip dài `dai` giây trên track, gần `t` nhất mà không chồng clip khác (dời về sau). */
export function choTrong(tl, trackId, t, dai) {
    const cac = (tl.clips || []).filter((c) => c.track === trackId)
        .map((c) => [Number(c.bat_dau || 0), ketThucClip(c)]).sort((a, b) => a[0] - b[0]);
    let bd = Math.max(0, t);
    for (let lap = 0; lap <= cac.length; lap += 1) {
        const chong = cac.find(([a, b]) => bd < b - 1e-6 && bd + dai > a + 1e-6);
        if (!chong) return Math.round(bd * 1000) / 1000;
        bd = chong[1];
    }
    return Math.round(bd * 1000) / 1000;
}

/* Xoá gợn (ripple delete): xoá các clip ids, dồn clip SAU nó trên cùng track lùi lại đúng khoảng trống. */
export function opsXoaGon(tl, ids) {
    const ops = [...opsXoaNhieu(tl, ids)];
    const bo = new Set(ids);
    const nhap = JSON.parse(JSON.stringify(tl));
    const tracks = new Set((tl.clips || []).filter((c) => bo.has(c.id)).map((c) => c.track));
    
    for (const track of tracks) {
        const xoa = (tl.clips || []).filter((c) => c.track === track && bo.has(c.id)).sort((a, b) => b.bat_dau - a.bat_dau);
        for (const c of xoa) {
            const bd = Number(c.bat_dau || 0);
            const khoang = ketThucClip(c) - bd;
            for (const khac of nhap.clips) {
                if (khac.track === track && !bo.has(khac.id) && Number(khac.bat_dau || 0) >= bd - 1e-6) {
                    khac.bat_dau = Math.round((Number(khac.bat_dau) - khoang) * 1000) / 1000;
                }
            }
        }
    }
    for (const c of nhap.clips) {
        if (!bo.has(c.id)) {
            const cu = (tl.clips || []).find((x) => x.id === c.id);
            if (cu && cu.bat_dau !== c.bat_dau) ops.push(tao.dat(tl, ['clips', { id: c.id }, 'bat_dau'], c.bat_dau));
        }
    }
    return ops;
}

/* Chèn gợn (ripple insert): tạo khoảng trống dài `dai` giây tại `t` trên `trackId`, đẩy các clip SAU `t` về sau. */
export function opsChenGon(tl, trackId, t, dai) {
    const ops = [];
    for (const c of tl.clips || []) {
        if (c.track === trackId && Number(c.bat_dau || 0) >= t - 1e-6) {
            ops.push(tao.dat(tl, ['clips', { id: c.id }, 'bat_dau'], Math.round((Number(c.bat_dau || 0) + dai) * 1000) / 1000));
        }
    }
    return ops;
}

/* Khép khoảng trống trên trackId. Nếu chiKhoangTai khác null, chỉ khép khoảng trống dưới thời điểm đó. */
export function opsKhepKhoang(tl, trackId, chiKhoangTai = null) {
    const ops = [];
    const cac = (tl.clips || []).filter((c) => c.track === trackId).sort((a, b) => Number(a.bat_dau || 0) - Number(b.bat_dau || 0));
    if (!cac.length) return ops;

    if (chiKhoangTai != null) {
        let gapStart = 0, gapEnd = Infinity, found = false, i = 0;
        for (; i < cac.length; i += 1) {
            const bd = Number(cac[i].bat_dau || 0);
            if (chiKhoangTai >= gapStart && chiKhoangTai < bd) { gapEnd = bd; found = true; break; }
            gapStart = ketThucClip(cac[i]);
        }
        if (found && gapEnd - gapStart > 1e-6) {
            const khoang = gapEnd - gapStart;
            for (let j = i; j < cac.length; j += 1) {
                ops.push(tao.dat(tl, ['clips', { id: cac[j].id }, 'bat_dau'], Math.round((Number(cac[j].bat_dau) - khoang) * 1000) / 1000));
            }
        }
    } else {
        let hienTai = 0;
        for (const c of cac) {
            const bd = Number(c.bat_dau || 0);
            if (bd > hienTai + 1e-6) ops.push(tao.dat(tl, ['clips', { id: c.id }, 'bat_dau'], Math.round(hienTai * 1000) / 1000));
            hienTai += ketThucClip(c) - bd;
        }
    }
    return ops;
}

export function opsChiaDeu(tl, cid, n) {
    const c = (tl.clips || []).find((x) => x.id === cid);
    if (!c) return null;
    const dai = ketThucClip(c) - (c.bat_dau || 0);
    const buoc = dai / n;
    if (buoc < 0.1) return null;

    const ops = [];
    const nhap = JSON.parse(JSON.stringify(tl));
    let idHienTai = cid;

    for (let i = 1; i < n; i++) {
        const diemCat = Number(c.bat_dau || 0) + i * buoc;
        const idMoi = idClipMoi(nhap);
        const o = opsTach(nhap, idHienTai, diemCat, idMoi);
        if (!o) break;
        
        o.forEach((op) => {
            ops.push(op);
            if (op.op === 'dat') {
                const prop = op.path[op.path.length - 1];
                nhap.clips.find((x) => x.id === idHienTai)[prop] = op.moi;
            } else {
                nhap.clips.splice(op.vi_tri, 0, op.gia_tri);
            }
        });
        idHienTai = idMoi;
    }
    return ops.length ? ops : null;
}

/* Tỉa tới đầu phát t: bỏ phần 'truoc' (Q) hoặc 'sau' (W). gon: dồn gợn hay không (false = Alt+Q/W). */
export function opsTiaToiDauPhat(tl, ids, t, phia, gon) {
    const ops = [];
    const bo = new Set(ids);
    const nhap = JSON.parse(JSON.stringify(tl));
    const tracks = new Set(nhap.clips.map((c) => c.track));

    for (const track of tracks) {
        const xet = nhap.clips.filter((c) => c.track === track).sort((a, b) => a.bat_dau - b.bat_dau);
        for (let i = xet.length - 1; i >= 0; i -= 1) {
            const c = xet[i];
            if (!bo.has(c.id)) continue;

            const bd = Number(c.bat_dau || 0), kt = ketThucClip(c);
            if (t <= bd + 1e-6 || t >= kt - 1e-6) continue;

            const khongMedia = c.ket_thuc != null;
            const giua = Math.round(thoiDiemMedia(c, t) * 1000) / 1000;
            const { kfTruoc, kfSau } = tachKeyframes(c, t - bd);
            
            if (phia === 'truoc') {
                const khoang = t - bd;
                if (kfSau) ops.push(tao.dat(tl, ['clips', { id: c.id }, 'keyframes'], kfSau));
                
                if (!gon) {
                    ops.push(tao.dat(tl, ['clips', { id: c.id }, 'bat_dau'], Math.round(t * 1000) / 1000));
                    if (!khongMedia) ops.push(tao.dat(tl, ['clips', { id: c.id }, 'vao'], giua));
                } else {
                    if (khongMedia) {
                        ops.push(tao.dat(tl, ['clips', { id: c.id }, 'ket_thuc'], Math.round((kt - khoang) * 1000) / 1000));
                    } else {
                        ops.push(tao.dat(tl, ['clips', { id: c.id }, 'vao'], giua));
                    }
                    for (const khac of nhap.clips) {
                        if (khac.track === track && Number(khac.bat_dau || 0) >= bd + 1e-6 && khac.id !== c.id) {
                            khac.bat_dau = Math.round((Number(khac.bat_dau) - khoang) * 1000) / 1000;
                            ops.push(tao.dat(tl, ['clips', { id: khac.id }, 'bat_dau'], khac.bat_dau));
                            if (khac.ket_thuc != null) {
                                khac.ket_thuc = Math.round((Number(khac.ket_thuc) - khoang) * 1000) / 1000;
                                ops.push(tao.dat(tl, ['clips', { id: khac.id }, 'ket_thuc'], khac.ket_thuc));
                            }
                        }
                    }
                }
            } else {
                const khoang = kt - t;
                if (kfTruoc) ops.push(tao.dat(tl, ['clips', { id: c.id }, 'keyframes'], kfTruoc));
                
                if (khongMedia) {
                    ops.push(tao.dat(tl, ['clips', { id: c.id }, 'ket_thuc'], Math.round(t * 1000) / 1000));
                } else {
                    ops.push(tao.dat(tl, ['clips', { id: c.id }, 'ra'], giua));
                }
                if (gon) {
                    for (const khac of nhap.clips) {
                        if (khac.track === track && Number(khac.bat_dau || 0) >= kt - 1e-6 && khac.id !== c.id) {
                            khac.bat_dau = Math.round((Number(khac.bat_dau) - khoang) * 1000) / 1000;
                            ops.push(tao.dat(tl, ['clips', { id: khac.id }, 'bat_dau'], khac.bat_dau));
                            if (khac.ket_thuc != null) {
                                khac.ket_thuc = Math.round((Number(khac.ket_thuc) - khoang) * 1000) / 1000;
                                ops.push(tao.dat(tl, ['clips', { id: khac.id }, 'ket_thuc'], khac.ket_thuc));
                            }
                        }
                    }
                }
            }
        }
    }
    return ops;
}


/* ------------------------------------------------------------ chuyển cảnh (GĐ 3) */
export function chuyenCanhHopLe(tl) {
    const hopLe = [];
    const ccList = tl.chuyen_canh || [];
    if (!ccList.length) return hopLe;
    
    const vTracks = (tl.tracks || []).filter(t => t.loai === 'video');
    const chinh = vTracks.length ? vTracks[vTracks.length - 1].id : null;
    if (!chinh) return hopLe;
    
    const clipsV1 = (tl.clips || []).filter(c => c.track === chinh).sort((a, b) => Number(a.bat_dau || 0) - Number(b.bat_dau || 0));
    
    for (let i = 0; i < clipsV1.length - 1; i++) {
        const truoc = clipsV1[i];
        const sau = clipsV1[i+1];
        const toc = Number(truoc.toc_do) || 1;
        const ket_thuc_truoc = Number(truoc.bat_dau || 0) + (Number(truoc.ra || 0) - Number(truoc.vao || 0)) / toc;
        const bat_dau_sau = Number(sau.bat_dau || 0);
        
        // Giải thích: Chỉ giữ chuyển cảnh giữa 2 clip kề nhau (sai số 1 khung hình ~ 0.05s). 
        // Nếu clip bị di chuyển hoặc xoá, khoảng cách > 0.05s -> chuyển cảnh tự bị loại bỏ, thoả mãn yêu cầu "xoá clip thì xoá luôn chuyển cảnh".
        if (Math.abs(ket_thuc_truoc - bat_dau_sau) <= 0.05) {
            const cc = ccList.find(x => x.truoc === truoc.id && x.sau === sau.id);
            if (cc) {
                // Giải thích: Thời lượng chuyển cảnh tối đa bằng nửa thời lượng của clip ngắn nhất trong 2 clip, tránh lấn sang điểm nối khác.
                const dai_truoc = (Number(truoc.ra || 0) - Number(truoc.vao || 0)) / toc;
                const toc_sau = Number(sau.toc_do) || 1;
                const dai_sau = (Number(sau.ra || 0) - Number(sau.vao || 0)) / toc_sau;
                const max_dai = Math.min(dai_truoc / 2, dai_sau / 2);
                hopLe.push({ ...cc, dai: Math.min(Number(cc.dai || 0.5), max_dai) });
            }
        }
    }
    return hopLe;
}

export function opsThemChuyenCanh(tl, cidTruoc, cidSau, loai, dai) {
    const nhap = JSON.parse(JSON.stringify(tl));
    nhap.chuyen_canh = nhap.chuyen_canh || [];
    const i = nhap.chuyen_canh.findIndex(x => x.truoc === cidTruoc && x.sau === cidSau);
    let idMoi = '';
    if (i >= 0) {
        idMoi = nhap.chuyen_canh[i].id;
        nhap.chuyen_canh.splice(i, 1);
    } else {
        const so = nhap.chuyen_canh.map(c => /^cc_(\d+)$/.exec(c.id || '')).filter(Boolean).map(m => Number(m[1]));
        idMoi = `cc_${(so.length ? Math.max(...so) : 0) + 1}`;
    }
    nhap.chuyen_canh.push({ id: idMoi, truoc: cidTruoc, sau: cidSau, loai: loai || 'fade', dai: dai || 0.5 });
    return [tao.dat(tl, ['chuyen_canh'], chuyenCanhHopLe(nhap))];
}

export function opsXoaChuyenCanh(tl, cidTruoc, cidSau) {
    const nhap = JSON.parse(JSON.stringify(tl));
    nhap.chuyen_canh = (nhap.chuyen_canh || []).filter(x => !(x.truoc === cidTruoc && x.sau === cidSau));
    return [tao.dat(tl, ['chuyen_canh'], chuyenCanhHopLe(nhap))];
}

/* ------------------------------------------------------------ keyframe (GĐ 3d) */
export function giaTriTai(c, duongDan, tCucBo) {
    const tinh = doc(c, duongDan.split('.'));
    if (!c.keyframes || !Array.isArray(c.keyframes[duongDan]) || c.keyframes[duongDan].length === 0) {
        return tinh;
    }
    const diem = c.keyframes[duongDan].sort((a, b) => a.t - b.t);
    if (tCucBo <= diem[0].t) return diem[0].v;
    if (tCucBo >= diem[diem.length - 1].t) return diem[diem.length - 1].v;
    
    for (let i = 0; i < diem.length - 1; i++) {
        const d1 = diem[i];
        const d2 = diem[i + 1];
        if (tCucBo >= d1.t && tCucBo < d2.t) {
            const tl = (tCucBo - d1.t) / (d2.t - d1.t);
            const em = d1.em || 'tuyen_tinh';
            if (em === 'giu') return d1.v;
            let f = tl;
            if (em === 'vao_ra') f = tl * tl * (3 - 2 * tl);
            return d1.v + (d2.v - d1.v) * f;
        }
    }
    return tinh;
}

export function viTriKeyframes(c, px) {
    if (!c.keyframes) return [];
    const setT = new Set();
    for (const k in c.keyframes) {
        if (!c.keyframes[k]) continue;
        for (const kf of c.keyframes[k]) setT.add(kf.t);
    }
    const dai = ketThucClip(c) - (c.bat_dau || 0);
    return Array.from(setT).filter(t => t >= 0 && t <= dai + 1e-6).map(t => t * px);
}

export function cacMucMenuClip(tl, mediaDict, cid, dangChonTuDanhSach, coBoNhoTam) {
    const dangChon = dangChonTuDanhSach || [];
    const c = tl.clips.find(x => x.id === cid);
    const m = c ? mediaDict[c.media] : null;
    const tr = c ? tl.tracks.find(t => t.id === c.track) : null;
    
    const muc = [];
    muc.push({ id: 'cat-dau', text: '✂ Cắt tại đầu phát (S)' });
    muc.push({ id: 'chep', text: '📋 Sao chép (Ctrl+C)' });
    muc.push({ id: 'cat', text: '✂ Cắt (Ctrl+X)' });
    if (coBoNhoTam) muc.push({ id: 'dan', text: '📋 Dán (Ctrl+V)' });
    muc.push({ id: 'nhan-doi', text: '👯 Nhân đôi (Ctrl+D)' });
    muc.push({ separator: true });
    muc.push({ id: 'xoa', text: '✕ Xoá (Delete)' });
    muc.push({ id: 'xoa-gon', text: '✕ Xoá gợn (Shift+Delete)' });
    
    if (c && tr && tr.loai === 'video' && m && m.co_am_thanh) {
        muc.push({ separator: true });
        muc.push({ id: 'tach-am', text: 'Tách âm thanh' });
    }
    
    if (dangChon.length === 2) {
        const c1 = tl.clips.find(x => x.id === dangChon[0]);
        const c2 = tl.clips.find(x => x.id === dangChon[1]);
        const t1 = c1 ? tl.tracks.find(t => t.id === c1.track) : null;
        const t2 = c2 ? tl.tracks.find(t => t.id === c2.track) : null;
        if (t1 && t2 && ((t1.loai === 'video' && t2.loai === 'audio') || (t1.loai === 'audio' && t2.loai === 'video'))) {
            muc.push({ separator: true });
            muc.push({ id: 'lien-ket', text: '🔗 Liên kết' });
        }
    }
    if (dangChon.some(id => { const cl = tl.clips.find(x => x.id === id); return cl && cl.lien_ket; })) {
        muc.push({ separator: true });
        muc.push({ id: 'bo-lien-ket', text: '🔗 Bỏ liên kết' });
    }
    
    if (c && (c.loai === 'audio' || (!c.loai && m && m.loai !== 'anh'))) {
        muc.push({ separator: true });
        muc.push({ id: 'tieng', text: c.tat_am ? '🔊 Bật tiếng' : '🔇 Tắt tiếng' });
    }
    
    if (c && !c.loai && m && m.loai !== 'anh') {
        muc.push({ separator: true });
        muc.push({ id: 'toc', v: 0.5, text: 'Tốc độ 0.5×' });
        muc.push({ id: 'toc', v: 1, text: 'Tốc độ 1×' });
        muc.push({ id: 'toc', v: 1.5, text: 'Tốc độ 1.5×' });
        muc.push({ id: 'toc', v: 2, text: 'Tốc độ 2×' });
    }
    
    if (c && (c.loai === 'audio' || (!c.loai && m && m.loai !== 'anh')) && tr && ['video', 'audio'].includes(tr.loai) && (c.ra > c.vao)) {
        muc.push({ separator: true });
        muc.push({ id: 'chia-deu', text: '➗ Chia đều thành N đoạn…' });
    }
    
    return muc;
}

export function mucMenuChoClip(tl, mediaDict, cid, dangChonTuDanhSach, coBoNhoTam) {
    return cacMucMenuClip(tl, mediaDict, cid, dangChonTuDanhSach, coBoNhoTam);
}

export function opsNhanDoi(tl, chon) {
    const ops = [];
    const nhap = JSON.parse(JSON.stringify(tl));
    const idsMoi = [];
    const lienKetCuMoi = {};
    
    const theoTrack = {};
    for (const id of chon) {
        const c = nhap.clips.find(x => x.id === id);
        if (!theoTrack[c.track]) theoTrack[c.track] = [];
        theoTrack[c.track].push(c);
    }
    
    for (const tr in theoTrack) {
        const clips = theoTrack[tr].sort((a, b) => Number(b.bat_dau || 0) - Number(a.bat_dau || 0));
        for (const c of clips) {
            const kt = ketThucClip(c);
            const dai = kt - Number(c.bat_dau || 0);
            
            const opsChen = opsChenGon(nhap, tr, kt, dai);
            for (const o of opsChen) {
                const cBiDay = nhap.clips.find(x => x.id === o.path[1].id);
                if (cBiDay) cBiDay.bat_dau = o.moi;
                ops.push(o);
            }
            
            const idMoi = idClipMoi(nhap);
            const m = JSON.parse(JSON.stringify(c));
            m.id = idMoi;
            m.bat_dau = kt;
            
            if (m.lien_ket) {
                if (!lienKetCuMoi[m.lien_ket]) lienKetCuMoi[m.lien_ket] = idNhomMoi(nhap);
                m.lien_ket = lienKetCuMoi[m.lien_ket];
            }
            
            ops.push(tao.them(tl, ['clips'], m));
            nhap.clips.push(m);
            idsMoi.push(idMoi);
        }
    }
    return { ops, idsMoi };
}

export function hopChuHinh(c, W, H, doRongChu = 0, doCaoChu = 0) {
    const b = c.bien_doi || {};
    const tl = Number(b.ti_le || 1);
    let w, h;
    if (c.loai === 'hinh') {
        w = Number(b.rong || 0.2) * W * tl;
        h = Number(b.cao || 0.2) * H * tl;
    } else {
        w = doRongChu;
        h = doCaoChu;
    }
    return {
        cx: Number(b.x ?? 0.5) * W,
        cy: Number(b.y ?? 0.5) * H,
        w: w,
        h: h,
        xoay: Number(b.xoay || 0)
    };
}

export function bienDoiSauKeo(b0, loai, nam, dx, dy, W, H, shift) {
    const moi = { ...b0 };
    if (nam === 'doi') {
        moi.x = (b0.x ?? 0.5) + dx / W;
        moi.y = (b0.y ?? 0.5) + dy / H;
        if (!shift) {
            if (Math.abs(moi.x - 0.5) < 0.012) moi.x = 0.5;
            if (Math.abs(moi.y - 0.5) < 0.012) moi.y = 0.5;
        }
    } else if (nam === 'xoay') {
        let d = dx + Number(b0.xoay || 0);
        d = ((d + 540) % 360) - 180;
        moi.xoay = shift ? Math.round(d / 15) * 15 : Math.round(d * 10) / 10;
    } else {
        if (loai === 'hinh') {
            const rad = -Number(b0.xoay || 0) * Math.PI / 180;
            const udx = dx * Math.cos(rad) - dy * Math.sin(rad);
            const udy = dx * Math.sin(rad) + dy * Math.cos(rad);
            
            let dw = udx, dh = udy;
            if (nam === 'tl') { dw = -udx; dh = -udy; }
            else if (nam === 'tr') { dw = udx; dh = -udy; }
            else if (nam === 'bl') { dw = -udx; dh = udy; }
            else if (nam === 'br') { dw = udx; dh = udy; }
            
            let r_moi = Number(b0.rong || 0.2) + (dw * 2) / W / Number(b0.ti_le || 1);
            let c_moi = Number(b0.cao || 0.2) + (dh * 2) / H / Number(b0.ti_le || 1);
            r_moi = Math.max(0.01, r_moi);
            c_moi = Math.max(0.01, c_moi);
            
            if (!shift) {
                const r0 = Number(b0.rong || 0.2);
                const c0 = Number(b0.cao || 0.2);
                const scale = Math.max(r_moi / r0, c_moi / c0);
                r_moi = r0 * scale;
                c_moi = c0 * scale;
            }
            moi.rong = r_moi;
            moi.cao = c_moi;
        } else {
            moi.ti_le = Math.max(loai === 'chu' ? 0.1 : 0.05, Math.min(8, Number(b0.ti_le || 1) * dx));
            if (!shift && Math.abs(moi.ti_le - 1) < 0.03) moi.ti_le = 1;
        }
    }
    return moi;
}

export function opsNhacNen(tl, mid, daiBai, tongDai) {
    if (daiBai <= 0 || tongDai <= 0) return [];
    const ops = [];
    let batDau = 0;
    let indexClip = (tl.clips || []).length;
    const clipSo = (tl.clips || []).map((c) => /^c_(\d+)$/.exec(c.id || '')).filter(Boolean).map((m) => Number(m[1]));
    let soHienTai = (clipSo.length ? Math.max(...clipSo) : 0);

    while (batDau < tongDai) {
        soHienTai++;
        const id = "c_" + soHienTai;
        let ra = daiBai;
        if (batDau + daiBai > tongDai) {
            ra = tongDai - batDau;
        }
        
        ops.push({
            op: 'them',
            path: ['clips'],
            vi_tri: indexClip,
            gia_tri: {
                id,
                track: '',
                media: mid,
                bat_dau: batDau,
                vao: 0,
                ra,
                toc_do: 1,
                am_luong: 0.25,
                am_vao: batDau === 0 ? 1 : 0,                       // chỉ fade vào ở đoạn đầu
                am_ra: batDau + ra >= tongDai - 1e-6 ? 2 : 0        // chỉ fade ra ở đoạn cuối (fade mọi đoạn lặp = chìm/nổi ở chỗ nối)
            }
        });
        
        batDau += ra;
        indexClip++;
    }
    return ops;
}
