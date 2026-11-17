/* Xuất trên thiết bị — nối các khối: server dựng tiếng (song song) → mở nguồn gốc → phân loại (phan_loai) → server nướng
   phần máy không làm (lớp chữ libass + đoạn nướng, goi_nuong) → ghép từng khung (ghep_khung) → mã hoá bằng phần cứng máy
   theo khúc 10 s, khúc xong ghi ngay vào OPFS (ma_hoa_khuc + khuc_opfs: bị dừng thì lần sau xuất TIẾP) → chép gói hình +
   gói tiếng thành MP4 (ghep_mp4).
   Kích thước/fps quy đổi như render.kich_thuoc_xuat (đổi cạnh NGẮN về 720/1080/1440/2160, giữ tỉ lệ). Khung đánh số trên
   lưới fps (n = t × fps) giống bản server — vùng xuất [ ] làm tròn về khung gần nhất. */
import { thoiLuong } from '../store.js';
import { BoGhepKhung } from './ghep_khung.js';
import { ghepFile, donOpfs } from './ghep_mp4.js';
import { layTiengServer } from './tieng_server.js';
import { phanLoai } from './phan_loai.js';
import { KetQuaNuong } from './goi_nuong.js';
import { BoMaHoa } from './ma_hoa_khuc.js';
import { Phien, bamKhoa } from './khuc_opfs.js';

const CANH_NGAN = { '720p': 720, '1080p': 1080, '1440p': 1440, '4k': 2160 };
const chan = (x) => { x = Math.round(x); return Math.max(2, x - (x % 2)); };
export const GIAY_KHUC = 10;
const LAM_LAI_DUOI = 0.1;            // xong < 10 % thì xuất tiếp không đáng — làm lại từ đầu

export function kichThuocXuat(ts, luaChon) {
    const rong = Number(ts.rong) || 1920, cao = Number(ts.cao) || 1080, dich = CANH_NGAN[(luaChon || '').toLowerCase()];
    if (!dich) return [chan(rong), chan(cao)];
    const k = dich / Math.min(rong, cao);
    return [chan(rong * k), chan(cao * k)];
}

/* Bitrate (bit/s) theo chất lượng (crf của hộp Xuất) — bit/pixel/khung gần với x264 crf tương ứng; fps cao tốn thêm ít
   hơn tỉ lệ (khung liền nhau giống nhau hơn): ×√(fps/60) trên 60 fps. 4K60 "Rất cao" ≈ 100 Mbps, 1080p30 "Cao" ≈ 8 Mbps. */
export function bitrateXuat(W, H, fps, crf) {
    const bpp = { 16: 0.2, 19: 0.13, 22: 0.09, 26: 0.06 }[Number(crf)] || 0.13;
    const hs = fps <= 60 ? fps : 60 * Math.sqrt(fps / 60);
    return Math.round(W * H * hs * bpp);
}

async function kiemDungLuong(byte) {
    try {
        const e = await navigator.storage.estimate();
        if (e.quota && e.quota - e.usage < byte) {
            throw new Error(`Bộ nhớ trình duyệt còn ${(Math.max(0, e.quota - e.usage) / 1e9).toFixed(1)} GB, bản xuất cần ~${(byte / 1e9).toFixed(1)} GB — giảm chất lượng/độ phân giải hoặc xuất bằng Server.`);
        }
    } catch (e) { if (e.message.startsWith('Bộ nhớ')) throw e; }
}

const fmtMoc = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

/* ctx: context editor (store, du, media, id, boLuu). tc: tuỳ chọn hộp Xuất (lam_lai: bỏ phiên dở). baoTienDo(phan_tram, chu).
   daHuy(): bool. Trả {file: File|Blob, ten, giay, khung, W, H, fps, nuong, lopChu, tiep_tu}. */
export async function xuatTrenThietBi(ctx, tc, baoTienDo = () => {}, daHuy = () => false) {
    try {
        return await xuatMotLuot(ctx, tc, baoTienDo, daHuy);
    } catch (e) {
        if (!e.khac_cau_hinh) throw e;
        // Bộ mã hoá lần này ra SPS/PPS khác lần bị dừng → không nối được khúc cũ; làm lại từ đầu (một lần).
        baoTienDo(1, 'Máy mã hoá khác lần trước — làm lại từ đầu');
        return xuatMotLuot(ctx, { ...tc, lam_lai: true }, baoTienDo, daHuy);
    }
}

async function xuatMotLuot(ctx, tc, baoTienDo, daHuy) {
    if (typeof VideoEncoder !== 'function' || typeof OffscreenCanvas !== 'function') {
        throw new Error('Trình duyệt này chưa có WebCodecs — cần Chrome/Edge mới, hoặc Safari iOS 17+. Hãy xuất bằng Server.');
    }
    const tl = ctx.store.timeline, ts = ctx.du.thong_so || {};
    const [W, H] = kichThuocXuat(ts, tc.do_phan_giai);
    const fps = Number(tc.fps) || Number(ts.fps) || 30;
    const codec = tc.codec_tb || 'avc';
    const n0 = Math.round((tc.vung_vao != null ? Number(tc.vung_vao) : 0) * fps);
    const n1 = Math.round((tc.vung_ra != null ? Number(tc.vung_ra) : thoiLuong(tl)) * fps);
    if (!(n1 > n0)) throw new Error('Timeline trống.');
    const br = bitrateXuat(W, H, fps, tc.crf);
    const tong = n1 - n0, K = Math.round(GIAY_KHUC * fps), soKhuc = Math.ceil(tong / K);

    await ctx.boLuu.flush();            // server dựng tiếng/nướng từ timeline TRÊN ĐĨA
    const khoa = await bamKhoa({ pid: ctx.id, tl, ts, media: ctx.media.map((m) => [m.id, m.file, m.kich_thuoc, m.thoi_luong]),
        W, H, fps, n0, n1, br, codec });
    const ph = await Phien.mo(ctx.id, khoa, { tong_khuc: soKhuc, giay: tong / fps }, !!tc.lam_lai);
    if (ph.tt.so_khuc && ph.tt.so_khuc < soKhuc && ph.tt.so_khuc * K < tong * LAM_LAI_DUOI) await ph.lamLai();
    const s = Math.min(ph.tt.so_khuc, soKhuc);
    if (ph.lyDo) baoTienDo(1, `Làm lại từ đầu: ${ph.lyDo}`);
    await kiemDungLuong(br / 8 * (tong - s * K) / fps * 2.2);   // khúc + file cuối

    const bat = performance.now();
    const td = { tieng: 'Đang xin server dựng tiếng…', nuong: '' };
    const tiepTu = s ? `xuất tiếp từ ${fmtMoc(s * GIAY_KHUC)} · ` : '';
    const baoServer = () => baoTienDo(4, tiepTu + [td.tieng, td.nuong].filter(Boolean).join(' · '));
    let tieng = null;
    const hTieng = layTiengServer(ctx.id, ctx.boLuu.phien, { ...tc, fps }, (p, chu) => { td.tieng = `${chu} ${p}%`; baoServer(); }, daHuy)
        .then((x) => { tieng = x; td.tieng = 'Tiếng xong'; return x; });
    hTieng.catch(() => {});

    const bo = new BoGhepKhung({ du: ctx.du, tl, media: ctx.media, pid: ctx.id, W, H, fps, n0, n1 });
    let mh = null, pl = { tiLeNuong: 0, lopChu: false };
    try {
        if (s < soKhuc) {
            await bo.mo((i, n, ten) => baoTienDo(2, `${tiepTu}Mở nguồn ${i + 1}/${n}: ${ten}`));
            pl = phanLoai(tl, ctx.media, n0, n1, fps, bo.khongGiaiMa);
            let hNuong = Promise.resolve(null);
            if (pl.lopChu || pl.doan.length) {
                td.nuong = 'Xin server dựng chữ/phần máy không làm được…';
                hNuong = KetQuaNuong.tao(ctx.id, ctx.boLuu.phien, { do_phan_giai: tc.do_phan_giai, fps }, n0, n1, pl.lopChu, pl.doan,
                    (p, chu) => { td.nuong = `${chu} ${p}%`; baoServer(); }, daHuy);
            }
            baoServer();
            // Gắn ngay khi xong (kể cả khi tiếng lỗi) để bo.dong() dọn file nướng trên server.
            await Promise.all([hTieng, hNuong.then((x) => { bo.nuong = x; })]);
            if (daHuy()) throw new Error('Đã huỷ');
            bo.nBatDau = n0 + s * K;
            if (bo.nuong) bo.nuong.datBatDau(n0 + s * K);
            mh = await BoMaHoa.tao({ codec, W, H, fps, bitrate: br }, s ? ph.tt.cau_hinh : null);
            const batGhep = performance.now();
            let dinh = 0, mocK = s * K, mocT = batGhep;
            const moiKey = Math.max(1, Math.round(2 * fps));
            for (let i = s; i < soKhuc; i++) {
                const ghi = await ph.ghiKhuc(i);
                mh.ghi = ghi;
                const a = i * K, b = Math.min(tong, a + K);
                for (let k = a; k < b; k++) {
                    if (daHuy()) throw new Error('Đã huỷ');
                    await mh.them(await bo.veKhung(n0 + k), k, (k - a) % moiKey === 0);
                    if (k % Math.max(1, Math.round(fps / 2)) === 0 && k > s * K) {
                        const bay = performance.now(), lam = k - s * K;
                        const da = (bay - batGhep) / 1000, conLai = da / lam * (tong - k);
                        // Tốc độ 2 s gần nhất; tụt dưới nửa tốc độ cao nhất → máy nóng / bị hạ xung.
                        let cham = '';
                        if (bay - mocT > 2000) {
                            const v = (k - mocK) / ((bay - mocT) / 1000);
                            dinh = Math.max(dinh, v);
                            if (dinh && v < dinh / 2) cham = ' · máy đang chậm lại (nóng máy?)';
                            mocK = k; mocT = bay;
                        }
                        baoTienDo(5 + Math.round(k / tong * 90), `${tiepTu}Đang xuất trên máy ${k}/${tong} khung · ${(lam / da).toFixed(1)} khung/s · còn ~${Math.ceil(conLai)} s${cham}`);
                    }
                }
                await mh.flush();
                await ghi.dong();
                await ph.xongKhuc(i, mh.cauHinh);
            }
            mh.dong();
            mh = null;
        } else {
            baoServer();
            await hTieng;
        }
        const ten = `${(tc.ten || 'video').replace(/[\\/:*?"<>|]+/g, ' ')}.mp4`;
        await donOpfs(ten);
        const { file } = await ghepFile({ ten, codec, fps, cauHinh: ph.tt.cau_hinh, goiHinh: ph.goi(), tieng, tongGoi: tong,
            baoTienDo: (x) => baoTienDo(95 + Math.round(x * 4), 'Ghép file MP4…') });
        await ph.xoa();
        return { file, ten, giay: Math.round((performance.now() - bat) / 100) / 10, khung: tong, W, H, fps,
            nuong: pl.tiLeNuong, lopChu: pl.lopChu, tiep_tu: s * GIAY_KHUC };
    } catch (e) {
        if (daHuy()) await ph.xoa();              // huỷ = bỏ hẳn; lỗi/bị dừng = giữ khúc đã xong để xuất tiếp
        throw e;
    } finally {
        if (mh) mh.dong();
        bo.dong();
        hTieng.then((x) => x && x.dong(), () => {});
    }
}
