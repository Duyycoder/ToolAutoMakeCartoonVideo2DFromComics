/* Xuất trên thiết bị: phần nào máy tự ghép, phần nào server nướng sẵn (orchestrator/editor/nuong.py). Hàm thuần — test Node.
   - Chữ / hình vẽ / phụ đề → lớp chữ server vẽ bằng libass (ảnh trong suốt, máy chồng lên) — khớp bản server.
   - Chỉnh màu nâng cao, chuyển cảnh máy chưa vẽ khớp, nguồn máy không giải mã được → ĐOẠN NƯỚNG: server dựng sẵn
     những khung đó (đủ mọi track), máy chép vào.
   - Còn lại máy ghép (che phụ đề, chỉnh màu cơ bản, hiệu ứng, biến đổi, chuyển cảnh khớp) — vài thứ gần giống → cảnh báo.
   Tiếng luôn do server dựng nên mọi hiệu ứng âm thanh đều giữ nguyên.
   Khung đánh số trên lưới fps xuất: khung n ở giây n / fps, thuộc khoảng [bd, kt) khi bd ≤ n/fps < kt. */
import { coNangCao } from '../mau_nang_cao.js';
import { hienThiNeo, ketThucClip } from '../store.js';
import { KIEU_CHINH_XAC } from './chuyen_canh_tb.js';

export const NGUONG_GOI_Y_SERVER = 0.5;     // nướng > 50 % thời lượng → gợi ý xuất bằng server

const khungTu = (t, fps) => Math.ceil(t * fps - 1e-6);

/* Gộp các khoảng khung chồng/chạm nhau, cắt vào [n0, n1). */
export function gopKhuc(ds, n0, n1) {
    const s = ds.map(([a, b]) => [Math.max(n0, a), Math.min(n1, b)]).filter(([a, b]) => a < b).sort((x, y) => x[0] - y[0]);
    const ra = [];
    for (const [a, b] of s) {
        if (ra.length && a <= ra[ra.length - 1][1]) ra[ra.length - 1][1] = Math.max(ra[ra.length - 1][1], b);
        else ra.push([a, b]);
    }
    return ra;
}

/* tl, media, khung [n0, n1), fps, khongGiaiMa: Set id media máy không giải mã được (biết sau khi mở nguồn).
   → {chan, canhBao, lopChu: bool, doan: [[a, b]] khung server nướng, lyDoNuong: [..], tiLeNuong: 0..1} */
export function phanLoai(tl, media, n0, n1, fps, khongGiaiMa = new Set()) {
    const canhBao = new Set(), lyDo = new Set(), khuc = [];
    const mdict = Object.fromEntries((media || []).map((m) => [m.id, m]));
    const tracks = Object.fromEntries((tl.tracks || []).map((t) => [t.id, t]));
    const t0 = n0 / fps, t1 = n1 / fps;
    const giao = (bd, kt) => kt > t0 && bd < t1;
    let lopChu = false;
    for (const c of tl.clips || []) {
        const tr = tracks[c.track];
        if (!tr || tr.an) continue;
        if (tr.loai === 'phu_de' || c.loai === 'phu_de') {
            if (hienThiNeo(tl, c).some((k) => giao(k.bd, k.kt)) && String(c.text || '').trim()) lopChu = true;
            continue;
        }
        const bd = Number(c.bat_dau) || 0, kt = ketThucClip(c);
        if (c.loai === 'chu' || c.loai === 'hinh') { if (giao(bd, kt)) lopChu = true; continue; }
        if (c.loai === 'che_phu_de') {
            if (c.kieu && c.kieu !== 'mau') canhBao.add('vùng che làm mờ/khảm vẽ bằng trình duyệt — gần giống bản Server');
            continue;
        }
        if (tr.loai !== 'video' || !c.media || !giao(bd, kt)) continue;
        const m = mdict[c.media];
        const can = [khungTu(bd, fps), khungTu(kt, fps)];
        if (coNangCao(c.mau)) { khuc.push(can); lyDo.add('chỉnh màu nâng cao'); }
        if (c.lat_ngang || c.lat_doc) { khuc.push(can); lyDo.add('lật hình'); }
        if (c.nen_mo) { khuc.push(can); lyDo.add('nền mờ'); }
        if (c.khoa_mau && c.khoa_mau.bat) { khuc.push(can); lyDo.add('phông xanh'); }
        if (c.mat_na && c.mat_na.bat) { khuc.push(can); lyDo.add('mặt nạ'); }
        if (khongGiaiMa.has(c.media)) { khuc.push(can); lyDo.add(`video máy không đọc được (${m ? m.ten : c.media})`); }
        if (m && m.hdr) canhBao.add('video HDR được chuyển sang SDR — màu có thể khác bản Server một chút');
        if ((c.hieu_ung || []).some((h) => h.bat !== false)) canhBao.add('hiệu ứng hình dùng bộ lọc của trình duyệt — có thể lệch nhẹ');
    }
    const clip = Object.fromEntries((tl.clips || []).map((c) => [c.id, c]));
    for (const cc of tl.chuyen_canh || []) {
        if (KIEU_CHINH_XAC.has(cc.loai) || !clip[cc.sau]) continue;
        const cat = Number(clip[cc.sau].bat_dau) || 0, d = Number(cc.dai) || 0;
        khuc.push([khungTu(cat - d / 2, fps), khungTu(cat + d / 2, fps)]);
        lyDo.add(`chuyển cảnh ${cc.loai}`);
    }
    const doan = gopKhuc(khuc, n0, n1);
    const nuong = doan.reduce((s, [a, b]) => s + b - a, 0);
    return { chan: [], canhBao: [...canhBao], lopChu, doan, lyDoNuong: [...lyDo], tiLeNuong: n1 > n0 ? nuong / (n1 - n0) : 0 };
}
