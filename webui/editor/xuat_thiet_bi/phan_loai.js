/* Xuất trên thiết bị làm được tới đâu: liệt kê thứ trong đoạn xuất mà bộ ghép trên máy CHƯA vẽ được (→ phải xuất bằng Server)
   và thứ vẫn xuất được nhưng có thể lệch nhẹ so với bản Server (cảnh báo). Hàm thuần — test được bằng Node.
   Tiếng luôn do server dựng nên mọi hiệu ứng âm thanh đều được giữ nguyên. */
import { coNangCao } from '../mau_nang_cao.js';
import { KIEU_CHINH_XAC } from './chuyen_canh_tb.js';

const giao = (c, t0, t1) => {
    const bd = Number(c.bat_dau) || 0;
    const kt = c.ket_thuc != null ? Number(c.ket_thuc)
        : bd + ((Number(c.ra) || 0) - (Number(c.vao) || 0)) / (Number(c.toc_do) || 1);
    return kt > t0 && bd < t1;
};

/* → {chan: [lý do chặn], canhBao: [lưu ý]} */
export function phanLoai(tl, media, t0 = 0, t1 = Infinity) {
    const chan = new Set(), canhBao = new Set();
    const mdict = Object.fromEntries((media || []).map((m) => [m.id, m]));
    const tracks = Object.fromEntries((tl.tracks || []).map((t) => [t.id, t]));
    for (const c of tl.clips || []) {
        const tr = tracks[c.track];
        if (!tr || tr.an || !giao(c, t0, t1)) continue;
        if (tr.loai === 'phu_de') chan.add('phụ đề (track phụ đề)');
        else if (c.loai === 'chu' || c.loai === 'hinh') chan.add('chữ / hình vẽ');
        else if (c.loai === 'che_phu_de') chan.add('vùng che phụ đề');
        else if (tr.loai === 'video') {
            const m = mdict[c.media];
            if (coNangCao(c.mau)) chan.add('chỉnh màu nâng cao (preset, LUT, đường cong, HSL, Màu Pro, làm nét/khử nhiễu)');
            if (m && m.hdr) canhBao.add('video HDR được chuyển sang SDR — màu có thể khác bản Server một chút');
            if ((c.hieu_ung || []).some((h) => h.bat !== false)) canhBao.add('hiệu ứng hình dùng bộ lọc của trình duyệt — có thể lệch nhẹ');
        }
    }
    const gan = (tl.chuyen_canh || []).filter((cc) => !KIEU_CHINH_XAC.has(cc.loai)).map((cc) => cc.loai);
    if (gan.length) canhBao.add(`chuyển cảnh kiểu ${[...new Set(gan)].join(', ')} vẽ gần giống (không y hệt bản Server)`);
    return { chan: [...chan], canhBao: [...canhBao] };
}
