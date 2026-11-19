/* Thao tác dựng nâng cao trên clip — hàm thuần sinh ops (không đụng DOM), test ở tests/js/thao_tac_clip.test.mjs:
 *  - opsKenBurns: phóng to / thu nhỏ / lia ngang dần bằng keyframe biến đổi
 *  - opsDongBang: chèn một ảnh tĩnh (khung hình tại đầu phát) vào giữa clip, đẩy mọi thứ phía sau lùi lại
 *  - opsNoiMuotAm: crossfade hai clip âm thanh liền nhau */
import { tao, apOp, opsTach, opsXoaGon, veTimeline, idClipMoi, idMoiNhieu, idNhomMoi, ketThucClip, clipMediaMoi, chongClip, opsThemTrack } from './store.js';

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

/* Đánh dấu theo nhịp nhạc: `nhip` = giây trong MEDIA (server đo). Thay các dấu nhịp cũ nằm trong khoảng của clip bằng dấu mới
   (dấu người dùng tự đặt giữ nguyên). Đầu phát và clip bắt dính vào các dấu này → cắt cảnh đúng nhịp. */
export function opsDanhDauNhip(tl, cid, nhip) {
    const c = (tl.clips || []).find((x) => x.id === cid);
    if (!c) return [];
    const bd = Number(c.bat_dau || 0), kt = ketThucClip(c);
    const cu = (tl.danh_dau || []).filter((d) => !(d.nhip && d.t >= bd - 1e-6 && d.t <= kt + 1e-6));
    let so = Math.max(0, ...(tl.danh_dau || []).map((d) => Number((/^dd_(\d+)$/.exec(d.id || '') || [])[1] || 0)));
    const moi = nhip.filter((s) => s >= Number(c.vao || 0) - 1e-6 && s <= Number(c.ra || 0) + 1e-6)
        .map((s) => ({ id: `dd_${so += 1}`, t: tron(bd + veTimeline(c, s)), ten: '♪', nhip: true }));
    return [tao.dat(tl, ['danh_dau'], [...cu, ...moi].sort((a, b) => a.t - b.t))];
}

/* Xoá mọi dấu nhịp (giữ dấu tự đặt). */
export const opsXoaDauNhip = (tl) => [tao.dat(tl, ['danh_dau'], (tl.danh_dau || []).filter((d) => !d.nhip))];

/* Tự cắt khoảng lặng (jump cut): `khoang` = [[a, b], …] giây trong MEDIA (server đo bằng silencedetect). Mỗi khoảng lặng
   nằm trong clip được cắt ra và xoá gợn (phần sau dồn lên), chừa lại `dem` giây lặng ở mỗi đầu cho đỡ cụt tiếng.
   Clip liên kết trùng giờ với clip này (tiếng đã tách) cắt y hệt để hình–tiếng vẫn khớp. Trả {ops, so, giam} | null. */
export function opsCatKhoangLang(tl, cid, khoang, dem = 0.12) {
    const goc = (tl.clips || []).find((x) => x.id === cid);
    if (!goc || goc.loai) return null;
    const bd = Number(goc.bat_dau || 0), kt = ketThucClip(goc);
    // Khoảng lặng → giờ timeline, xét từ CUỐI lên để các lần xoá gợn không làm lệch khoảng chưa xử lý.
    const doan = khoang.map(([a, b]) => [bd + veTimeline(goc, Math.max(Number(goc.vao || 0), a + dem)), bd + veTimeline(goc, Math.min(Number(goc.ra || 0), b - dem))])
        .map(([a, b]) => [tron(Math.max(bd, a)), tron(Math.min(kt, b))]).filter(([a, b]) => b - a > 0.1).sort((x, y) => y[0] - x[0]);
    if (!doan.length) return null;
    const cung = (tl.clips || []).filter((x) => !x.loai && (x.id === cid || (goc.lien_ket && x.lien_ket === goc.lien_ket
        && Math.abs(Number(x.bat_dau || 0) - bd) < 1e-3 && Math.abs(ketThucClip(x) - kt) < 1e-3))).map((x) => x.id);
    const nhap = JSON.parse(JSON.stringify(tl));
    const ops = [];
    const lam = (o) => { if (o) o.forEach((op) => { apOp(nhap, op); ops.push(op); }); return o; };
    for (const [a, b] of doan) {
        for (const id of cung) {
            if (b < kt - 0.02) lam(opsTach(nhap, id, b, idClipMoi(nhap)));          // phần sau khoảng lặng thành clip riêng
            let giua = id;                                                         // khoảng lặng bắt đầu ngay đầu clip → xoá chính nó
            if (a > bd + 0.02) { giua = idClipMoi(nhap); if (!lam(opsTach(nhap, id, a, giua))) continue; }
            lam(opsXoaGon(nhap, [giua]));
        }
    }
    return { ops, so: doan.length, giam: tron(doan.reduce((s, [a, b]) => s + b - a, 0)) };
}

/* Hiệu ứng vào/ra cho clip video/ảnh (kiểu CapCut): sinh keyframe độ mờ / tỉ lệ / vị trí trong `dai` giây đầu và cuối clip.
   Tên hiệu ứng lưu ở clip.hu_vao / hu_ra / hu_dai để bảng thuộc tính hiện lại; keyframe cũ của 4 thuộc tính này bị thay. */
export const HU_VAO = { '': 'Không', mo_dan: 'Mờ dần', phong_to: 'Phóng to dần', thu_nho: 'Thu nhỏ dần', truot_trai: 'Trượt vào từ trái',
    truot_phai: 'Trượt vào từ phải', truot_len: 'Trượt lên', truot_xuong: 'Trượt xuống' };
export const HU_RA = { '': 'Không', mo_dan: 'Mờ dần', phong_to: 'Phóng to dần', thu_nho: 'Thu nhỏ dần', truot_trai: 'Trượt ra bên trái',
    truot_phai: 'Trượt ra bên phải', truot_len: 'Trượt lên', truot_xuong: 'Trượt xuống' };
const DD_HU = { mo: 'hien_thi.do_mo', s: 'bien_doi.ti_le', x: 'bien_doi.x', y: 'bien_doi.y' };

export function opsHieuUngClip(tl, c, vao, ra, dai = 0.5) {
    const D = tron(ketThucClip(c) - Number(c.bat_dau || 0));
    if (D <= 0) return [];
    const d = tron(Math.min(dai, D / 2));
    const b = c.bien_doi || {};
    const goc = { mo: Number((c.hien_thi || {}).do_mo ?? 1), s: Number(b.ti_le ?? 1), x: Number(b.x ?? 0.5), y: Number(b.y ?? 0.5) };
    // Giá trị ở mép ngoài (lúc bắt đầu vào / lúc ra hết) của từng hiệu ứng.
    const mep = (ten, laVao) => ({
        mo_dan: { mo: 0 },
        phong_to: { s: goc.s * (laVao ? 0.6 : 1.4), mo: 0 },
        thu_nho: { s: goc.s * (laVao ? 1.4 : 0.6), mo: 0 },
        truot_trai: { x: goc.x - 0.6 }, truot_phai: { x: goc.x + 0.6 },
        truot_len: { y: goc.y + (laVao ? 0.6 : -0.6) }, truot_xuong: { y: goc.y + (laVao ? -0.6 : 0.6) },
    }[ten] || {});
    const mv = mep(vao, true), mr = mep(ra, false);
    const kf = { ...(c.keyframes || {}) };
    for (const [k, dd] of Object.entries(DD_HU)) {
        delete kf[dd];
        if (!(k in mv) && !(k in mr)) continue;
        const diem = k in mv ? [{ t: 0, v: tron(mv[k]), em: 'ra' }, { t: d, v: goc[k], em: 'tuyen_tinh' }] : [{ t: 0, v: goc[k], em: 'tuyen_tinh' }];
        if (k in mr) {
            if (diem[diem.length - 1].t < D - d - 1e-6) diem.push({ t: tron(D - d), v: goc[k], em: 'vao' });
            else diem[diem.length - 1].em = 'vao';
            diem.push({ t: D, v: tron(mr[k]), em: 'tuyen_tinh' });
        }
        kf[dd] = diem;
    }
    const p = (k) => ['clips', { id: c.id }, k];
    return [tao.dat(tl, p('keyframes'), kf), tao.dat(tl, p('hu_vao'), vao || undefined), tao.dat(tl, p('hu_ra'), ra || undefined),
        tao.dat(tl, p('hu_dai'), vao || ra ? dai : undefined)];
}

/* ------------------------------------------------------------ Slip / Roll (Alt + kéo trên timeline)
   Slip: giữ nguyên chỗ và độ dài clip trên timeline, chỉ trượt ĐOẠN NGUỒN bên trong (kéo phải = lấy phần sớm hơn).
   Roll: dời điểm nối giữa hai clip liền nhau — clip này dài ra bao nhiêu thì clip kia ngắn lại bấy nhiêu, tổng không đổi.
   Cả hai không áp cho clip có đồ thị tốc độ. `media` = {id: media} để biết độ dài nguồn / ảnh tĩnh. */
const laAnh = (media, c) => (media[c.media] || {}).loai === 'anh';
const daiNguon = (media, c) => Number((media[c.media] || {}).thoi_luong) || Infinity;
const thuong = (c) => c && !c.loai && !c.toc_do_cong && c.ket_thuc == null;

export function opsSlip(tl, c, dt, media) {
    if (!thuong(c) || laAnh(media, c)) return [];
    const toc = Number(c.toc_do) || 1, vao = Number(c.vao || 0), L = Number(c.ra || 0) - vao;
    const moi = tron(Math.min(Math.max(0, vao - dt * toc), Math.max(0, daiNguon(media, c) - L)));
    if (Math.abs(moi - vao) < 1e-4) return [];
    const p = (k) => ['clips', { id: c.id }, k];
    return [tao.dat(tl, p('vao'), moi), tao.dat(tl, p('ra'), tron(moi + L))];
}

/* Clip nằm sát mép `phia` ('trai' | 'phai') của c trên cùng track. */
export function clipKe(tl, c, phia) {
    const moc = phia === 'phai' ? ketThucClip(c) : Number(c.bat_dau || 0);
    return (tl.clips || []).find((x) => x.id !== c.id && x.track === c.track && !x.loai
        && Math.abs((phia === 'phai' ? Number(x.bat_dau || 0) : ketThucClip(x)) - moc) < 0.02) || null;
}

/* → {ops, d} (d = độ dời thật của điểm nối sau khi chặn theo nguồn còn lại và độ dài tối thiểu) | null nếu không roll được. */
export function opsRoll(tl, c, phia, dt, media, minDai = 0.04) {
    const ke = clipKe(tl, c, phia);
    const [a, b] = phia === 'phai' ? [c, ke] : [ke, c];              // a bên trái điểm nối, b bên phải
    if (!thuong(a) || !thuong(b)) return null;
    const ta = Number(a.toc_do) || 1, tb = Number(b.toc_do) || 1;
    const da = ketThucClip(a) - Number(a.bat_dau || 0), db = ketThucClip(b) - Number(b.bat_dau || 0);
    const lo = Math.max(-(da - minDai), laAnh(media, b) ? -Infinity : -Number(b.vao || 0) / tb);
    const hi = Math.min(db - minDai, laAnh(media, a) ? Infinity : (daiNguon(media, a) - Number(a.ra || 0)) / ta);
    const d = tron(Math.min(Math.max(dt, lo), hi));
    if (Math.abs(d) < 1e-4) return { ops: [], d: 0 };
    const p = (x, k) => ['clips', { id: x.id }, k];
    const ops = [tao.dat(tl, p(a, 'ra'), tron(Number(a.ra || 0) + d * ta)), tao.dat(tl, p(b, 'bat_dau'), tron(Number(b.bat_dau || 0) + d))];
    ops.push(laAnh(media, b) ? tao.dat(tl, p(b, 'ra'), tron(Number(b.ra || 0) - d * tb)) : tao.dat(tl, p(b, 'vao'), tron(Number(b.vao || 0) + d * tb)));
    return { ops, d };
}

/* Gộp clip (compound): các clip media `ids` được thay bằng MỘT clip dùng media `mMoi` (server đã dựng sẵn từ chính chúng),
   đặt tại thời điểm của clip sớm nhất. Chọn dòng: dòng của một clip vừa gộp mà còn trống đúng khoảng đó (ưu tiên dòng video
   dưới cùng), không có thì thêm dòng mới. Chuyển cảnh dính tới clip bị gộp được gỡ. Trả {ops, id} | null. */
export function opsGopClip(tl, ids, mMoi) {
    const chon = new Set(ids);
    const loai = Object.fromEntries((tl.tracks || []).map((t) => [t.id, t.loai]));
    const cac = (tl.clips || []).filter((c) => chon.has(c.id) && !c.loai && c.media && (loai[c.track] === 'video' || loai[c.track] === 'audio'));
    const D = Number(mMoi.thoi_luong) || 0;
    if (!cac.length || !D) return null;
    const t0 = tron(Math.min(...cac.map((c) => Number(c.bat_dau || 0))));
    const nhap = JSON.parse(JSON.stringify(tl));
    const ops = [];
    const lam = (op) => { apOp(nhap, op); ops.push(op); };
    const bo = new Set(cac.map((c) => c.id));
    const cc = (nhap.chuyen_canh || []).filter((x) => !bo.has(x.truoc) && !bo.has(x.sau));
    if (cc.length !== (nhap.chuyen_canh || []).length) lam(tao.dat(nhap, ['chuyen_canh'], cc));
    nhap.clips.map((c, i) => [c, i]).filter(([c]) => bo.has(c.id)).reverse()
        .forEach(([c, i]) => lam({ op: 'xoa', path: ['clips'], vi_tri: i, gia_tri: JSON.parse(JSON.stringify(c)) }));
    const canLoai = mMoi.loai === 'audio' ? 'audio' : 'video';
    const thuTu = (nhap.tracks || []).filter((t) => t.loai === canLoai && !t.khoa && cac.some((c) => c.track === t.id));
    if (canLoai === 'video') thuTu.reverse();                                  // dòng video dưới cùng trước
    let tr = thuTu.find((t) => !chongClip(nhap, t.id, t0, t0 + D));
    if (!tr) {
        const moi = opsThemTrack(nhap, canLoai);
        moi.ops.forEach(lam);
        tr = { id: moi.id };
    }
    const id = idClipMoi(nhap);
    lam(tao.them(nhap, ['clips'], clipMediaMoi(id, tr.id, mMoi.id, t0, D)));
    return { ops, id };
}
