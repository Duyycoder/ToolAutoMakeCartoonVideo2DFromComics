/* Mã hoá hình cho xuất trên thiết bị bằng VideoEncoder của trình duyệt (phần cứng máy khi có), gói ra ghi thẳng vào khúc
   (khuc_opfs.js). Một bộ mã hoá cho cả lượt → mọi khúc cùng SPS/PPS, nối liền được; xuất tiếp thì bộ mới phải ra
   decoderConfig y hệt lần trước (khác → làm lại từ đầu, xem vong_xuat.js). */

/* Chuỗi codec đúng level cho khung W×H ở fps (level quá thấp → trình duyệt từ chối 4K60/120). */
export function chuoiCodec(codec, W, H, fps) {
    const mb = Math.ceil(W / 16) * Math.ceil(H / 16) * fps, mau = W * H * fps;
    if (codec === 'hevc') {
        const lv = mau <= 133693440 ? 123 : mau <= 267386880 ? 150 : mau <= 534773760 ? 153 : mau <= 1069547520 ? 156 : 183;
        return `hvc1.1.6.L${lv}.B0`;
    }
    if (codec === 'av1') {
        const lv = mau <= 133693440 ? '08' : mau <= 267386880 ? '12' : mau <= 534773760 ? '13' : '14';
        return `av01.0.${lv}M.08`;
    }
    const lv = mb <= 245760 ? '2A' : mb <= 983040 ? '33' : mb <= 2073600 ? '34' : mb <= 4177920 ? '3C' : '3D';
    return `avc1.6400${lv}`;
}

const hex = (buf) => (buf ? [...new Uint8Array(buf instanceof ArrayBuffer ? buf : buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength))]
    .map((x) => x.toString(16).padStart(2, '0')).join('') : '');

export class BoMaHoa {
    /* {codec, W, H, fps, bitrate}. cauHinhCu: decoderConfig đã lưu (xuất tiếp) — bộ mới ra khác thì báo loi.khac_cau_hinh. */
    static async tao({ codec, W, H, fps, bitrate }, cauHinhCu = null) {
        const cfg = { codec: chuoiCodec(codec, W, H, fps), width: W, height: H, framerate: fps, bitrate,
            hardwareAcceleration: 'no-preference', latencyMode: 'quality' };
        if (codec === 'avc') cfg.avc = { format: 'avc' };
        if (codec === 'hevc') cfg.hevc = { format: 'hevc' };
        const ho = await VideoEncoder.isConfigSupported(cfg).catch(() => ({ supported: false }));
        if (!ho.supported) throw new Error(`Máy không mã hoá được ${cfg.codec} ${W}×${H} ${fps} fps — chọn thấp hơn hoặc xuất bằng Server.`);
        const b = new BoMaHoa();
        Object.assign(b, { fps, cauHinhCu, cauHinh: null, loi: null, ghi: null, toiDa: W * H > 2e6 ? 2 : 4 });
        b.enc = new VideoEncoder({ output: (c, m) => b._ra(c, m), error: (e) => { b.loi = b.loi || e; } });
        b.enc.configure(cfg);
        return b;
    }

    _ra(chunk, meta) {
        if (meta && meta.decoderConfig && !this.cauHinh) {
            const d = meta.decoderConfig;
            this.cauHinh = { codec: d.codec, codedWidth: d.codedWidth, codedHeight: d.codedHeight, description: hex(d.description),
                colorSpace: d.colorSpace ? (d.colorSpace.toJSON ? d.colorSpace.toJSON() : { ...d.colorSpace }) : undefined };
            if (this.cauHinhCu && this.cauHinhCu.description !== this.cauHinh.description) {
                this.loi = Object.assign(new Error('Bộ mã hoá ra cấu hình khác lần trước'), { khac_cau_hinh: true });
            }
        }
        const b = new Uint8Array(chunk.byteLength);
        chunk.copyTo(b);
        this.ghi.them(b, chunk.timestamp, chunk.duration || Math.round(1e6 / this.fps), chunk.type === 'key');
    }

    /* Khung thứ k (tính từ đầu bản xuất) — canvas/OffscreenCanvas. keyFrame: đầu khúc / mỗi 2 s. */
    async them(cv, k, keyFrame) {
        if (this.loi) throw this.loi;
        const f = new VideoFrame(cv, { timestamp: Math.round(k * 1e6 / this.fps), duration: Math.round(1e6 / this.fps) });
        this.enc.encode(f, { keyFrame });
        f.close();
        while (this.enc.encodeQueueSize > this.toiDa && !this.loi) await new Promise((r) => setTimeout(r, 1));
    }

    /* Hết khúc: đợi mọi gói ra (ghi vào khúc hiện tại) rồi mới đổi khúc. */
    async flush() {
        await this.enc.flush();
        if (this.loi) throw this.loi;
    }

    dong() { try { this.enc.close(); } catch (e) { /* đã đóng */ } }
}

/* decoderConfig đã lưu → dạng cho muxer (description hex → bytes). */
export function cauHinhGiaiMa(ch) {
    const d = ch.description ? new Uint8Array(ch.description.match(/../g).map((x) => parseInt(x, 16))) : undefined;
    return { codec: ch.codec, codedWidth: ch.codedWidth, codedHeight: ch.codedHeight, description: d, colorSpace: ch.colorSpace };
}
