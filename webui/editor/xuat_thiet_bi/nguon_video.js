/* Nguồn video cho xuất trên thiết bị: đọc file GỐC từ server bằng Range request (không tải cả file vào RAM),
   demux MP4/MOV + giải mã WebCodecs qua Mediabunny, lấy khung theo thời điểm như `fps=` của ffmpeg
   (khung cuối cùng có thời điểm bắt đầu ≤ t — đúng cả video VFR của điện thoại).
   Dùng: const n = await NguonVideo.mo(url); for await (const s of n.khungTai([0, 1/30, …])) {…; s.close()} ; n.dong(). */
import { ALL_FORMATS, Input, UrlSource, VideoSampleSink } from '../thu_vien_ngoai/mediabunny-1.65.1.min.js';

export class NguonVideo {
    static async mo(url) {
        const n = new NguonVideo();
        n.input = new Input({ source: new UrlSource(url), formats: ALL_FORMATS });
        n.track = await n.input.getPrimaryVideoTrack();
        if (!n.track) throw new Error('File không có hình.');
        n.giaiMaDuoc = await n.track.canDecode();
        n.codec = await n.track.getCodecParameterString();
        n.rong = n.track.displayWidth;
        n.cao = n.track.displayHeight;
        n.xoay = n.track.rotation || 0;
        n.thoiLuong = await n.input.computeDuration();
        if (n.giaiMaDuoc) n.sink = new VideoSampleSink(n.track);
        return n;
    }

    /* Khung tại MỘT thời điểm (giây) — VideoSample; nhớ .close() sau khi dùng. */
    async khung(t) {
        if (!this.sink) throw new Error(`Máy này không giải mã được ${this.codec} — cần server chuyển mã.`);
        return this.sink.getSample(t);
    }

    /* Nhiều thời điểm tăng dần (lúc xuất) — Mediabunny giải mã trước vài khung, nhanh hơn gọi khung() lẻ. */
    khungTai(ds) {
        if (!this.sink) throw new Error(`Máy này không giải mã được ${this.codec} — cần server chuyển mã.`);
        return this.sink.samplesAtTimestamps(ds);
    }

    dong() {
        try { this.input && this.input.dispose(); } catch (e) { /* đã đóng */ }
    }
}
