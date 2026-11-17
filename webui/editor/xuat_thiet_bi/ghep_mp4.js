/* Ghép MP4 cuối cho xuất trên thiết bị: CHÉP gói hình đã mã hoá (các khúc trong khuc_opfs.js) + gói tiếng AAC server dựng
   (tieng_server.js) — không mã hoá lại, vài giây là xong.
   Đích: OPFS (bộ nhớ riêng của trang, không chiếm RAM — file 4K dài vài GB vẫn được) khi trình duyệt cho ghi luồng
   (`createWritable`), không thì giữ trong RAM (BufferTarget) — đủ cho video ngắn.
   fastStart: false → moov ghi ở cuối, không phải giữ cả file để dời moov lên đầu. */
import { BufferTarget, EncodedAudioPacketSource, EncodedPacket, EncodedVideoPacketSource, Mp4OutputFormat, Output, StreamTarget }
    from '../thu_vien_ngoai/mediabunny-1.65.1.min.js';
import { cauHinhGiaiMa } from './ma_hoa_khuc.js';

const THU_MUC = 'xuat_thiet_bi';

async function dichOpfs(ten) {
    try {
        const tm = await (await navigator.storage.getDirectory()).getDirectoryHandle(THU_MUC, { create: true });
        const fh = await tm.getFileHandle(ten, { create: true });
        if (typeof fh.createWritable !== 'function') return null;     // Safari cũ: chỉ có SyncAccessHandle trong Worker
        return { tm, fh, ghi: await fh.createWritable() };
    } catch (e) { return null; }
}

/* {ten, codec: 'avc'|'hevc'|'av1', fps, cauHinh (decoderConfig đã lưu), goiHinh: AsyncIterable<{data, ts, dur, key}> (µs),
    tieng: {cauHinh, goi: AsyncIterator<EncodedPacket>} | null, baoTienDo(0..1)} → {file, opfs} */
export async function ghepFile({ ten, codec, fps, cauHinh, goiHinh, tieng, tongGoi, baoTienDo = () => {} }) {
    const opfs = await dichOpfs(ten);
    const target = opfs ? new StreamTarget(opfs.ghi, { chunked: true }) : new BufferTarget();
    const output = new Output({ format: new Mp4OutputFormat({ fastStart: false }), target });
    const hinh = new EncodedVideoPacketSource(codec);
    output.addVideoTrack(hinh, { frameRate: fps });
    let am = null;
    if (tieng && tieng.cauHinh) {
        am = new EncodedAudioPacketSource('aac');
        output.addAudioTrack(am);
    }
    try {
        await output.start();
        let metaHinh = { decoderConfig: cauHinhGiaiMa(cauHinh) }, metaAm = am ? { decoderConfig: tieng.cauHinh } : null;
        let goiAm = am ? await tieng.goi.next() : { done: true };
        let n = 0;
        for await (const g of goiHinh) {
            const t = g.ts / 1e6;
            // Gói tiếng đi trước hình ~0,5 s (xen kẽ cho muxer, không dồn RAM).
            while (!goiAm.done && goiAm.value.timestamp <= t + 0.5) {
                await am.add(goiAm.value, metaAm || undefined);
                metaAm = null;
                goiAm = await tieng.goi.next();
            }
            await hinh.add(new EncodedPacket(g.data, g.key ? 'key' : 'delta', t, g.dur / 1e6), metaHinh || undefined);
            metaHinh = null;
            if (++n % 30 === 0) baoTienDo(tongGoi ? n / tongGoi : 0);
        }
        while (!goiAm.done) {
            await am.add(goiAm.value, metaAm || undefined);
            metaAm = null;
            goiAm = await tieng.goi.next();
        }
        await output.finalize();
    } catch (e) {
        try { await output.cancel(); } catch (x) { /* đã dừng */ }
        if (opfs) await opfs.tm.removeEntry(opfs.fh.name).catch(() => {});
        throw e;
    }
    if (opfs) return { file: await opfs.fh.getFile(), opfs: true };
    return { file: new Blob([target.buffer], { type: 'video/mp4' }), opfs: false };
}

/* Dọn bản xuất cũ trong OPFS (giữ `giu` tên đang dùng). */
export async function donOpfs(giu = '') {
    try {
        const tm = await (await navigator.storage.getDirectory()).getDirectoryHandle(THU_MUC, { create: true });
        for await (const [ten] of tm.entries()) if (ten !== giu) await tm.removeEntry(ten).catch(() => {});
    } catch (e) { /* trình duyệt không có OPFS */ }
}
