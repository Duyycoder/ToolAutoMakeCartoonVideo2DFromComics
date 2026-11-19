/* Thao tác dựng nâng cao trên clip — hàm thuần sinh ops (không đụng DOM), test ở tests/js/thao_tac_clip.test.mjs:
 *  - opsKenBurns: phóng to / thu nhỏ / lia ngang dần bằng keyframe biến đổi
 *  - opsDongBang: chèn một ảnh tĩnh (khung hình tại đầu phát) vào giữa clip, đẩy mọi thứ phía sau lùi lại
 *  - opsNoiMuotAm: crossfade hai clip âm thanh liền nhau */
import { tao, apOp, opsTach, idClipMoi, idMoiNhieu, idNhomMoi, ketThucClip, clipMediaMoi, chongClip, opsThemTrack } from './store.js';

const tron = (x) => Math.round(x * 1000) / 1000;

export const KIEU_KEN_BURNS = {
    zoom_vao: 'Phóng to dần', zoom_ra: 'Thu nhỏ dần', lia_trai: 'Lia sang trái', lia_phai: 'Lia sang phải', bo: 'Bỏ chuyển động',
};
const DD_KB = ['bien_doi.ti_le', 'bien_doi.x'];

/* Ken Burns cho ảnh/video: hai keyframe ở đầu và cuối clip. Lia ngang cần phóng 1.2× để không lộ mép khung. */
export function opsKenBurns(tl, c, kieu) {
    const D = tron(ketThucClip(c) - Number(c.bat_dau || 0));
    const b = c.bien_doi || {}, s = Number(b.ti_le ?? 1), x = Number(b.x ?? 0.5);
    const cap = (a, z) => [{ t: 0, v: tron(a), em: 'tuyen_tinh' }, { t: D, v: tron(z), em: 'tuyen_tinh' }];
    const moi = {
        zoom_vao: { 'bien_doi.ti_le': cap(s, s * 1.25) },
        zoom_ra: { 'bien_doi.ti_le': cap(s * 1.25, s) },
        lia_trai: { 'bien_doi.ti_le': cap(s * 1.2, s * 1.2), 'bien_doi.x': cap(x + 0.08, x - 0.08) },
        lia_phai: { 'bien_doi.ti_le': cap(s * 1.2, s * 1.2), 'bien_doi.x': cap(x - 0.08, x + 0.08) },
        bo: {},
    }[kieu];
    if (!moi || D <= 0) return [];
    const kf = { ...(c.keyframes || {}) };
    DD_KB.forEach((d) => delete kf[d]);
    return [tao.dat(tl, ['clips', { id: c.id }, 'keyframes'], { ...kf, ...moi })];
}

/* Thuộc tính KHÔNG chép từ clip video sang ảnh đóng băng (giờ giấc, nguồn, tiếng, chuyển động). */
const BO_KHI_DONG_BANG = new Set(['id', 'track', 'media', 'bat_dau', 'ket_thuc', 'vao', 'ra', 'toc_do', 'toc_do_cong', 'keyframes',
    'lien_ket', 'tach_tu', 'dao_nguoc', 'nhom_neo', 'am_luong', 'am_vao', 'am_ra', 'tat_am', 'nhac_nen_giam', 'hieu_ung_am']);

/* Đóng băng khung hình: cắt clip `cid` tại t, chèn ảnh `mAnh` dài `dai` giây vào đó (giữ biến đổi, màu, hiệu ứng của clip).
   Mọi clip bắt đầu từ t trở đi trên các track không khoá lùi lại `dai` giây để hình–tiếng–chữ vẫn khớp; clip liên kết với
   clip bị cắt cũng cắt theo. Clip khác đang chạy ngang qua t (nhạc nền) giữ nguyên. Trả {ops, id} hoặc null. */
export function opsDongBang(tl, cid, t, mAnh, dai = 2) {
    const nhap = JSON.parse(JSON.stringify(tl));
    const goc = nhap.clips.find((x) => x.id === cid);
    if (!goc || goc.loai) return null;
    const bd = Number(goc.bat_dau || 0), kt = ketThucClip(goc);
    if (t < bd - 1e-6 || t > kt + 1e-6) return null;
    const ops = [];
    const lam = (op) => { apOp(nhap, op); ops.push(op); };
    const khoa = new Set(nhap.tracks.filter((x) => x.khoa).map((x) => x.id));
    let tChen = t <= bd + 0.02 ? bd : t >= kt - 0.02 ? kt : tron(t);
    if (tChen > bd && tChen < kt) {
        const nhom = {};
        const canCat = nhap.clips.filter((x) => !x.loai && !khoa.has(x.track) && (x.id === cid || (goc.lien_ket && x.lien_ket === goc.lien_ket))
            && tChen > Number(x.bat_dau || 0) + 0.02 && tChen < ketThucClip(x) - 0.02).map((x) => x.id);
        for (const id of canCat) {
            const o = opsTach(nhap, id, tChen, idClipMoi(nhap));
            if (!o) continue;
            const them = o.find((x) => x.op === 'them');
            const cu = nhap.clips.find((x) => x.id === id);
            if (them && cu.lien_ket) {                        // nửa sau thành nhóm liên kết mới, như khi cắt tay
                nhom[cu.lien_ket] = nhom[cu.lien_ket] || idNhomMoi(nhap);
                them.gia_tri.lien_ket = nhom[cu.lien_ket];
            }
            o.forEach(lam);
        }
    }
    for (const x of nhap.clips.map((y) => ({ ...y }))) {
        if (khoa.has(x.track) || x.bat_dau == null || Number(x.bat_dau) < tChen - 1e-6) continue;
        lam(tao.dat(nhap, ['clips', { id: x.id }, 'bat_dau'], tron(Number(x.bat_dau) + dai)));
        if (x.ket_thuc != null) lam(tao.dat(nhap, ['clips', { id: x.id }, 'ket_thuc'], tron(Number(x.ket_thuc) + dai)));
    }
    const id = idClipMoi(nhap);
    const anh = clipMediaMoi(id, goc.track, mAnh.id, tChen, dai);
    for (const [k, v] of Object.entries(goc)) if (!BO_KHI_DONG_BANG.has(k)) anh[k] = JSON.parse(JSON.stringify(v));
    lam(tao.them(nhap, ['clips'], anh));
    return { ops, id };
}

/* Hai clip có nối mượt được không: cùng một track âm thanh, clip sau bắt đầu ngay khi clip trước kết thúc. → [truoc, sau] | null */
export function capNoiMuot(tl, ids) {
    if (ids.length !== 2) return null;
    const [a, b] = ids.map((id) => (tl.clips || []).find((c) => c.id === id)).sort((x, y) => Number(x?.bat_dau || 0) - Number(y?.bat_dau || 0));
    if (!a || !b || a.loai || b.loai || a.track !== b.track) return null;
    const tr = (tl.tracks || []).find((x) => x.id === a.track);
    if (!tr || tr.loai !== 'audio' || Math.abs(Number(b.bat_dau || 0) - ketThucClip(a)) > 0.05) return null;
    return [a, b];
}

/* Crossfade hai clip âm thanh liền nhau trong `d` giây. Một track không chứa được hai clip chồng nhau nên clip sau chuyển
   sang track âm thanh khác (còn trống đoạn đó, không có thì thêm track) và bắt đầu SỚM hơn `d` giây — lấy thêm phần đầu
   trong file gốc nếu còn, không thì cả clip dời sớm lên. Clip trước fade ra, clip sau fade vào trong đoạn chồng. */
export function opsNoiMuotAm(tl, ids, d = 0.5) {
    const cap = capNoiMuot(tl, ids);
    if (!cap) return null;
    const [a, b] = cap;
    const dai = Math.min(d, (ketThucClip(a) - Number(a.bat_dau || 0)) / 2, (ketThucClip(b) - Number(b.bat_dau || 0)) / 2);
    if (dai < 0.05) return null;
    const nhap = JSON.parse(JSON.stringify(tl));
    const ops = [];
    const lam = (op) => { apOp(nhap, op); ops.push(op); };
    const p = (id, k) => ['clips', { id }, k];
    const bdMoi = tron(Number(b.bat_dau || 0) - dai), toc = Number(b.toc_do) || 1;
    let tr = nhap.tracks.find((x) => x.loai === 'audio' && x.id !== a.track && !x.khoa && x.vai !== 'long_tieng'
        && !chongClip(nhap, x.id, bdMoi, ketThucClip(b), [b.id]));
    if (!tr) {
        const moi = opsThemTrack(nhap, 'audio');
        moi.ops.forEach(lam);
        tr = { id: moi.id };
    }
    if (!b.toc_do_cong && Number(b.vao || 0) >= dai * toc - 1e-6) lam(tao.dat(nhap, p(b.id, 'vao'), tron(Number(b.vao || 0) - dai * toc)));
    lam(tao.dat(nhap, p(b.id, 'bat_dau'), bdMoi));
    lam(tao.dat(nhap, p(b.id, 'track'), tr.id));
    lam(tao.dat(nhap, p(b.id, 'am_vao'), tron(dai)));
    lam(tao.dat(nhap, p(a.id, 'am_ra'), tron(dai)));
    return { ops, track: tr.id, dai: tron(dai) };
}

/* Tách phụ đề / vùng che đang DÙNG CHUNG: một media có nhiều clip trùng đoạn nguồn (thêm lại, nhân đôi, dán) thì cùng
   một câu hiện ở mọi clip đó và sửa một chỗ là đổi hết. Ở đây mỗi clip trùng nhận nhóm neo riêng (`nhom_neo`) kèm BẢN SAO
   của các câu rơi vào nó (`tu_nhom`) → từng chỗ hiện sửa riêng được. Các mảnh của một clip đã cắt (không trùng đoạn
   nguồn) vẫn chung nhóm. Trả {ops, soCau} — soCau = số bản sao tạo ra (0 = không có gì dính nhau). */
export function opsTachNeo(tl) {
    const loai = Object.fromEntries((tl.tracks || []).map((t) => [t.id, t.loai]));
    const xo = new Map();                                   // media|nhóm → {video: [], audio: []}
    for (const c of tl.clips || []) {
        const l = loai[c.track];
        if (!c.media || (l !== 'video' && l !== 'audio')) continue;
        const k = `${c.media}|${c.nhom_neo || ''}`;
        if (!xo.has(k)) xo.set(k, { mid: c.media, nhom: c.nhom_neo || '', video: [], audio: [] });
        xo.get(k)[l].push(c);
    }
    const neo = (tl.clips || []).filter((c) => c.tu_media && c.t_vao != null && c.t_ra != null);
    let so = Math.max(0, ...(tl.clips || []).map((c) => Number((/^n_(\d+)$/.exec(c.nhom_neo || '') || [])[1] || 0)));
    const trung = (a, b, c, d) => Math.min(b, d) - Math.max(a, c) > 1e-3;
    const ops = [], sao = [];
    for (const x of xo.values()) {
        const cac = (x.video.length ? x.video : x.audio).slice().sort((a, b) => Number(a.bat_dau || 0) - Number(b.bat_dau || 0));
        const nhom = [];
        for (const c of cac) {
            const g = nhom.find((ds) => !ds.some((y) => trung(Number(y.vao || 0), Number(y.ra || 0), Number(c.vao || 0), Number(c.ra || 0))));
            if (g) g.push(c); else nhom.push([c]);
        }
        const cau = neo.filter((c) => c.tu_media === x.mid && (c.tu_nhom || '') === x.nhom);
        for (const ds of nhom.slice(1)) {
            const ban = cau.filter((c) => ds.some((y) => trung(Number(c.t_vao), Number(c.t_ra), Number(y.vao || 0), Number(y.ra || 0))));
            if (!ban.length) continue;                      // clip trùng nhưng không câu nào rơi vào → khỏi đổi nhóm
            so += 1;
            for (const y of ds) ops.push(tao.dat(tl, ['clips', { id: y.id }, 'nhom_neo'], `n_${so}`));
            for (const c of ban) sao.push({ ...JSON.parse(JSON.stringify(c)), tu_nhom: `n_${so}` });
        }
    }
    const ids = idMoiNhieu(tl, sao.length), dau = (tl.clips || []).length;
    sao.forEach((c, i) => ops.push({ op: 'them', path: ['clips'], vi_tri: dau + i, gia_tri: { ...c, id: ids[i] } }));
    return { ops, soCau: sao.length };
}
