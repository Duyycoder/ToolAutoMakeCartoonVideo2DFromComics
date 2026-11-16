/* Xuất trên thiết bị — nối các khối: kiểm làm được không (phan_loai) → server dựng tiếng (song song) → mở nguồn gốc →
   ghép từng khung (ghep_khung) → mã hoá bằng phần cứng máy + chép gói tiếng xen kẽ (ghep_mp4) → file MP4.
   Kích thước/fps quy đổi như render.kich_thuoc_xuat (đổi cạnh NGẮN về 720/1080/1440/2160, giữ tỉ lệ). */
import { thoiLuong } from '../store.js';
import { BoGhepKhung } from './ghep_khung.js';
import { moBanXuat, donOpfs } from './ghep_mp4.js';
import { layTiengServer } from './tieng_server.js';
import { phanLoai } from './phan_loai.js';

const CANH_NGAN = { '720p': 720, '1080p': 1080, '1440p': 1440, '4k': 2160 };
const chan = (x) => { x = Math.round(x); return Math.max(2, x - (x % 2)); };

export function kichThuocXuat(ts, luaChon) {
    const rong = Number(ts.rong) || 1920, cao = Number(ts.cao) || 1080, dich = CANH_NGAN[(luaChon || '').toLowerCase()];
    if (!dich) return [chan(rong), chan(cao)];
    const k = dich / Math.min(rong, cao);
    return [chan(rong * k), chan(cao * k)];
}

/* Bitrate theo chất lượng (crf của hộp Xuất) — bit/pixel/khung, gần với x264 crf tương ứng. */
function bitrate(W, H, fps, crf) {
    const bpp = { 16: 0.2, 19: 0.13, 22: 0.09, 26: 0.06 }[Number(crf)] || 0.13;
    return Math.round(W * H * Math.min(fps, 60) * bpp);
}

/* ctx: context editor (store, du, media, id, boLuu). tc: tuỳ chọn hộp Xuất. baoTienDo(phan_tram, chu). daHuy(): bool.
   Trả {file: File|Blob, ten, giay, khung}. */
export async function xuatTrenThietBi(ctx, tc, baoTienDo = () => {}, daHuy = () => false) {
    if (typeof VideoEncoder !== 'function' || typeof OffscreenCanvas !== 'function') {
        throw new Error('Trình duyệt này chưa có WebCodecs — cần Chrome/Edge mới, hoặc Safari iOS 17+. Hãy xuất bằng Server.');
    }
    const tl = ctx.store.timeline, ts = ctx.du.thong_so || {};
    const [W, H] = kichThuocXuat(ts, tc.do_phan_giai);
    const fps = Number(tc.fps) || Number(ts.fps) || 30;
    const t0 = tc.vung_vao != null ? Number(tc.vung_vao) : 0;
    const t1 = tc.vung_ra != null ? Number(tc.vung_ra) : thoiLuong(tl);
    if (!(t1 > t0)) throw new Error('Timeline trống.');
    const pl = phanLoai(tl, ctx.media, t0, t1);
    if (pl.chan.length) throw new Error(`Thiết bị chưa ghép được: ${pl.chan.join('; ')} — hãy chọn Máy xuất "Server".`);

    await ctx.boLuu.flush();            // server dựng tiếng từ timeline TRÊN ĐĨA
    const bat = performance.now();
    let tieng = null, loiTieng = null, xongTieng = false, tiengTD = 'Đang xin server dựng tiếng…';
    const hTieng = layTiengServer(ctx.id, ctx.boLuu.phien, { ...tc, fps }, (p, chu) => { tiengTD = `${chu} ${p}%`; }, daHuy)
        .then((x) => { tieng = x; }, (e) => { loiTieng = e; }).finally(() => { xongTieng = true; });

    const bo = new BoGhepKhung({ du: ctx.du, tl, media: ctx.media, pid: ctx.id, W, H, fps, t0, t1 });
    let ban = null;
    try {
        await bo.mo((i, n, ten) => baoTienDo(2, `Mở nguồn ${i + 1}/${n}: ${ten}`));
        while (!xongTieng) {
            if (daHuy()) throw new Error('Đã huỷ');
            baoTienDo(4, tiengTD);
            await new Promise((r) => setTimeout(r, 300));
        }
        await hTieng;
        if (loiTieng) throw loiTieng;
        const ten = `${(tc.ten || 'video').replace(/[\\/:*?"<>|]+/g, ' ')}.mp4`;
        await donOpfs(ten);
        ban = await moBanXuat({ codec: tc.codec_tb || 'avc', rong: W, cao: H, fps, bitrate: bitrate(W, H, fps, tc.crf), ten,
            tieng: tieng ? { cauHinh: tieng.cauHinh } : null });
        const tong = Math.round((t1 - t0) * fps);
        let goi = tieng ? await tieng.goi.next() : { done: true };
        for (let k = 0; k < tong; k++) {
            if (daHuy()) throw new Error('Đã huỷ');
            const tGiay = k / fps;
            // Gói tiếng đi trước hình ~0,5 s (xen kẽ cho muxer, không dồn RAM).
            while (!goi.done && goi.value.timestamp <= tGiay + 0.5) { await ban.themGoiTieng(goi.value); goi = await tieng.goi.next(); }
            await ban.them(await bo.veKhung(t0 + tGiay), tGiay);
            if (k % Math.max(1, Math.round(fps / 2)) === 0) {
                const da = (performance.now() - bat) / 1000, conLai = k ? da / k * (tong - k) : 0;
                baoTienDo(5 + Math.round(k / tong * 93), `Đang xuất trên máy ${k}/${tong} khung · còn ~${Math.ceil(conLai)} s`);
            }
        }
        while (!goi.done) { await ban.themGoiTieng(goi.value); goi = await tieng.goi.next(); }
        baoTienDo(99, 'Hoàn tất file…');
        const { file } = await ban.xong();
        ban = null;
        return { file, ten, giay: Math.round((performance.now() - bat) / 100) / 10, khung: tong, W, H, fps };
    } catch (e) {
        if (ban) await ban.huy();
        throw e;
    } finally {
        bo.dong();
        if (tieng) tieng.dong();
    }
}
