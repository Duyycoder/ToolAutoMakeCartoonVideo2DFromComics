/* Ghi MP4 theo luồng cho xuất trên thiết bị: mã hoá khung (WebCodecs qua Mediabunny) + chép nguyên gói tiếng AAC
   (server dựng — tieng_server.js) → file MP4.
   Đích: OPFS (bộ nhớ riêng của trang, không chiếm RAM — file 4K dài vài GB vẫn được) khi trình duyệt cho ghi luồng
   (`createWritable`), không thì giữ trong RAM (BufferTarget) — đủ cho video ngắn.
   fastStart: false → moov ghi ở cuối, không phải giữ cả file để dời moov lên đầu. */
import { BufferTarget, EncodedAudioPacketSource, Mp4OutputFormat, Output, StreamTarget, VideoSample, VideoSampleSource }
    from '../thu_vien_ngoai/mediabunny-1.65.1.min.js';

const THU_MUC = 'xuat_thiet_bi';

async function dichOpfs(ten) {
    try {
        const tm = await (await navigator.storage.getDirectory()).getDirectoryHandle(THU_MUC, { create: true });
        const fh = await tm.getFileHandle(ten, { create: true });
        if (typeof fh.createWritable !== 'function') return null;     // Safari cũ: chỉ có SyncAccessHandle trong Worker
        return { tm, fh, ghi: await fh.createWritable() };
    } catch (e) { return null; }
}

/* Mở một bản xuất. tc = {codec: 'avc'|'hevc'|'av1', rong, cao, fps, bitrate, ten, phanCung?, tieng?: {cauHinh}}.
   Trả {them(khung, t), themGoiTieng(goi), xong() → {file, opfs}, huy()}. `khung` = OffscreenCanvas/VideoFrame/canvas. */
export async function moBanXuat(tc) {
    const opfs = await dichOpfs(tc.ten || `xuat_${Date.now()}.mp4`);
    const target = opfs ? new StreamTarget(opfs.ghi, { chunked: true }) : new BufferTarget();
    const output = new Output({ format: new Mp4OutputFormat({ fastStart: false }), target });
    const nguon = new VideoSampleSource({ codec: tc.codec || 'avc', bitrate: tc.bitrate, keyFrameInterval: 2,
        latencyMode: 'quality', hardwareAcceleration: tc.phanCung || 'no-preference' });   // no-preference: trình duyệt tự chọn phần cứng khi có
    output.addVideoTrack(nguon, { frameRate: tc.fps });
    let nguonTieng = null, metaTieng = null;
    if (tc.tieng && tc.tieng.cauHinh) {
        nguonTieng = new EncodedAudioPacketSource('aac');
        output.addAudioTrack(nguonTieng);
        metaTieng = { decoderConfig: tc.tieng.cauHinh };
    }
    await output.start();
    const dai = 1 / tc.fps;
    let daHuy = false;
    return {
        async them(khung, t) {
            if (daHuy) return;
            const s = khung instanceof VideoSample ? khung : new VideoSample(khung, { timestamp: t, duration: dai });
            await nguon.add(s);        // chờ khi hàng đợi bộ mã hoá đầy — tự giữ áp lực, không tràn RAM
            if (s !== khung) s.close();
        },
        async themGoiTieng(goi) {
            if (daHuy || !nguonTieng) return;
            await nguonTieng.add(goi, metaTieng || undefined);
            metaTieng = null;          // decoderConfig chỉ cần ở gói đầu
        },
        async xong() {
            await output.finalize();
            if (opfs) return { file: await opfs.fh.getFile(), opfs: true };
            return { file: new Blob([target.buffer], { type: 'video/mp4' }), opfs: false };
        },
        async huy() {
            daHuy = true;
            try { await output.cancel(); } catch (e) { /* đã dừng */ }
            if (opfs) { try { await opfs.tm.removeEntry(opfs.fh.name); } catch (e) { /* bỏ qua */ } }
        },
    };
}

/* Dọn bản xuất cũ trong OPFS (giữ `giu` tên đang dùng). */
export async function donOpfs(giu = '') {
    try {
        const tm = await (await navigator.storage.getDirectory()).getDirectoryHandle(THU_MUC, { create: true });
        for await (const [ten] of tm.entries()) if (ten !== giu) await tm.removeEntry(ten).catch(() => {});
    } catch (e) { /* trình duyệt không có OPFS */ }
}
