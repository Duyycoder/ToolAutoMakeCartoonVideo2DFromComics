/* Che phụ đề trên thiết bị — như render._loc_che: vùng (tỉ lệ 0–1 của khung media) đặt theo GIỜ MEDIA (t_vao..t_ra),
   áp lên khung NGUỒN trước biến đổi/chỉnh màu. "mau" khớp hẳn; làm mờ (gblur σ = độ mạnh/2), khảm (khối = độ mạnh/2)
   và xoá logo (vẽ như làm mờ) gần giống bản server. Khung nguồn được vẽ ra canvas tạm đúng cỡ sẽ dán (w × h). */
import { laNeo } from '../store.js';

/* Vùng che gắn với media `mid` (không nằm trên track ẩn). */
export function cheCuaMedia(tl, mid) {
    const an = new Set((tl.tracks || []).filter((x) => x.an).map((x) => x.id));
    return (tl.clips || []).filter((c) => c.loai === 'che_phu_de' && c.tu_media === mid && laNeo(c) && !an.has(c.track));
}

export class BoChe {
    constructor() {
        this.cv = new OffscreenCanvas(2, 2);
        this.c = this.cv.getContext('2d');
        this.nho = new OffscreenCanvas(2, 2);
        this.cNho = this.nho.getContext('2d');
    }

    /* nguon: VideoSample | ImageBitmap; ds: vùng che; tm: giây media; mw: chiều rộng media gốc.
       Trả canvas đã che (cỡ w × h) hoặc null nếu không vùng nào đang bật. */
    ap(nguon, w, h, ds, tm, mw) {
        const dang = ds.filter((c) => tm >= Number(c.t_vao) - 1e-6 && tm <= Number(c.t_ra) + 1e-6);
        if (!dang.length) return null;
        w = Math.max(2, Math.round(w)); h = Math.max(2, Math.round(h));
        if (this.cv.width !== w || this.cv.height !== h) { this.cv.width = w; this.cv.height = h; }
        const c = this.c;
        c.filter = 'none';
        c.clearRect(0, 0, w, h);
        if (nguon.draw) nguon.draw(c, 0, 0, w, h); else c.drawImage(nguon, 0, 0, w, h);
        const s = w / (Number(mw) || w);           // px khung tạm / px media gốc
        for (const che of dang) {
            const v = che.vung || {};
            const x = Math.max(0, Number(v.x || 0)), y = Math.max(0, Number(v.y || 0));
            const vw = Math.min(1 - x, Number(v.w ?? 0.1)), vh = Math.min(1 - y, Number(v.h ?? 0.1));
            if (vw <= 0.002 || vh <= 0.002) continue;
            const rx = x * w, ry = y * h, rw = vw * w, rh = vh * h;
            const manh = Math.max(1, Number(che.do_manh || 20));
            const kieu = che.kieu || 'blur';
            if (kieu === 'mau') {
                c.fillStyle = che.mau || '#000';
                c.fillRect(rx, ry, rw, rh);
            } else if (kieu === 'mosaic') {
                const k = Math.max(2, Math.floor(manh / 2)) * s;
                const nw = Math.max(1, Math.round(rw / k)), nh = Math.max(1, Math.round(rh / k));
                if (this.nho.width !== nw || this.nho.height !== nh) { this.nho.width = nw; this.nho.height = nh; }
                this.cNho.imageSmoothingEnabled = true;
                this.cNho.drawImage(this.cv, rx, ry, rw, rh, 0, 0, nw, nh);
                c.imageSmoothingEnabled = false;
                c.drawImage(this.nho, 0, 0, nw, nh, rx, ry, rw, rh);
                c.imageSmoothingEnabled = true;
            } else {
                // gblur: lấy rộng ra 3σ quanh vùng rồi cắt đúng vùng — không bị viền trong suốt ở mép.
                const sg = Math.max(0.5, manh / 2 * s), p = Math.ceil(sg * 3);
                const sx = Math.max(0, rx - p), sy = Math.max(0, ry - p);
                const sw = Math.min(w, rx + rw + p) - sx, sh = Math.min(h, ry + rh + p) - sy;
                if (this.nho.width !== Math.ceil(sw) || this.nho.height !== Math.ceil(sh)) { this.nho.width = Math.ceil(sw); this.nho.height = Math.ceil(sh); }
                this.cNho.filter = 'none';
                this.cNho.drawImage(this.cv, sx, sy, sw, sh, 0, 0, sw, sh);
                c.save();
                c.beginPath();
                c.rect(rx, ry, rw, rh);
                c.clip();
                c.filter = `blur(${sg}px)`;
                c.drawImage(this.nho, 0, 0, sw, sh, sx, sy, sw, sh);
                c.restore();
            }
        }
        return this.cv;
    }
}
