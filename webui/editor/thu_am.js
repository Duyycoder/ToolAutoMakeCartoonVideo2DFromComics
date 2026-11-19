/* Thu âm lồng tiếng (voice-over) ngay trên timeline: bấm 🎙 → thu từ micro và phát timeline từ đầu phát; bấm lần nữa →
   dừng, lưu thành file WAV trong dự án và đặt clip vào track âm thanh còn trống đúng chỗ bắt đầu thu.
   Ghi WAV (PCM 16-bit mono) thay vì webm của MediaRecorder: webm thu trực tiếp không có thời lượng trong file, Safari lại
   ra mp4 — WAV thì máy nào cũng như nhau và ffmpeg đọc chính xác từng mẫu. */
import { toast } from './chung.js';
import { taiLenFile } from './tai_len.js';

/* Float32 [-1, 1] → Blob WAV PCM 16-bit mono. */
export function wavTuMau(mau, tanSo) {
    const dv = new DataView(new ArrayBuffer(44 + mau.length * 2));
    const chu = (vt, s) => [...s].forEach((ch, i) => dv.setUint8(vt + i, ch.charCodeAt(0)));
    chu(0, 'RIFF'); dv.setUint32(4, 36 + mau.length * 2, true); chu(8, 'WAVEfmt ');
    dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true);
    dv.setUint32(24, tanSo, true); dv.setUint32(28, tanSo * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true);
    chu(36, 'data'); dv.setUint32(40, mau.length * 2, true);
    for (let i = 0; i < mau.length; i += 1) {
        const x = Math.max(-1, Math.min(1, mau[i]));
        dv.setInt16(44 + i * 2, x < 0 ? x * 0x8000 : x * 0x7fff, true);
    }
    return new Blob([dv], { type: 'audio/wav' });
}

export class ThuAm {
    constructor(ctx, nut) {
        this.ctx = ctx;
        this.nut = nut;
        this.dang = null;          // {luong, may, manh, t0}
    }

    batTat() { return this.dang ? this.dung() : this.batDau(); }

    async batDau() {
        if (this.ctx.store.chiDoc) { toast('Cửa sổ này chỉ xem.', 'warn'); return; }
        if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
            toast('Trình duyệt không cho thu âm ở đây (cần mở bằng https hoặc localhost).', 'warn');
            return;
        }
        let luong;
        try {
            luong = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
        } catch (e) { toast('Không dùng được micro — hãy cho phép trang truy cập micro.', 'error'); return; }
        const may = new MediaRecorder(luong);
        const manh = [];
        may.addEventListener('dataavailable', (e) => { if (e.data.size) manh.push(e.data); });
        this.dang = { luong, may, manh, t0: Math.round((this.ctx.ui.dau_phat || 0) * 1000) / 1000 };
        may.start(500);
        this.nut.classList.add('dang-thu');
        this.nut.title = 'Dừng thu âm';
        if (!this.ctx.preview.dangPhat) this.ctx.preview.batTat();     // vừa xem vừa đọc; nên đeo tai nghe để tiếng video không lọt vào micro
        toast('Đang thu âm… bấm 🎙 lần nữa để dừng.', 'info', 3000);
    }

    async dung() {
        const { luong, may, manh, t0 } = this.dang;
        this.dang = null;
        this.nut.classList.remove('dang-thu');
        this.nut.title = 'Thu âm lồng tiếng tại đầu phát';
        if (this.ctx.preview.dangPhat) this.ctx.preview.dung();
        await new Promise((xong) => { may.addEventListener('stop', xong, { once: true }); may.stop(); });
        luong.getTracks().forEach((x) => x.stop());
        if (!manh.length) { toast('Chưa thu được gì.', 'warn'); return; }
        try {
            const am = new (window.AudioContext || window.webkitAudioContext)();
            const buf = await am.decodeAudioData(await new Blob(manh, { type: may.mimeType }).arrayBuffer());
            am.close();
            const mau = buf.getChannelData(0);
            if (mau.length < buf.sampleRate * 0.3) { toast('Đoạn thu quá ngắn.', 'warn'); return; }
            const gio = new Date().toTimeString().slice(0, 8).replace(/:/g, '-');
            const file = new File([wavTuMau(mau, buf.sampleRate)], `Thu âm ${gio}.wav`, { type: 'audio/wav' });
            toast('Đang lưu đoạn thu âm…', 'info', 2500);
            const hua = taiLenFile(this.ctx.id, this.ctx.boLuu.phien, file).then((ds) => ({ media: ds }));
            this.ctx.timeline._nhapRoiDat(hua, (m) => this.ctx.timeline.themLopTaiDauPhat(m, t0));
        } catch (e) { toast(`Không lưu được đoạn thu âm: ${e.message}`, 'error'); }
    }
}
