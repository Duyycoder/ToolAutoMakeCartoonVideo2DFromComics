/* Scopes đo màu khung hình đang xem (SAU chỉnh màu): Histogram, Waveform, RGB Parade, Vectorscope.
   Khung lấy mẫu nhỏ (~256 px ngang) → đủ nhanh để cập nhật vài lần mỗi giây khi phát. */
import { taoLut, N_LUT } from './mau_nang_cao.js';

export const KIEU_SCOPE = [['histogram', 'Histogram'], ['waveform', 'Waveform'], ['parade', 'RGB Parade'], ['vector', 'Vectorscope']];
const W_MAU = 256;

let cvA = null, cvB = null;

/* Lấy mẫu khung của `nguon` (<video>/<img>) đã áp chỉnh màu: LUT gộp (như WebGL) rồi CSS filter (chỉnh cơ bản, hiệu ứng). */
export function layMau(nguon, mau, lutFile, cssLoc) {
    const w0 = nguon.videoWidth || nguon.naturalWidth, h0 = nguon.videoHeight || nguon.naturalHeight;
    if (!w0 || !h0) return null;
    const w = W_MAU, h = Math.max(1, Math.round(W_MAU * h0 / w0));
    cvA = cvA || document.createElement('canvas');
    cvB = cvB || document.createElement('canvas');
    for (const c of [cvA, cvB]) { if (c.width !== w || c.height !== h) { c.width = w; c.height = h; } }
    const a = cvA.getContext('2d', { willReadFrequently: true });
    try { a.drawImage(nguon, 0, 0, w, h); } catch (e) { return null; }
    let px;
    try { px = a.getImageData(0, 0, w, h); } catch (e) { return null; }   // nguồn khác origin
    const lut = taoLut(mau || {}, lutFile);
    if (lut) {
        const d = px.data, n = N_LUT - 1;
        for (let i = 0; i < d.length; i += 4) {
            const o = (Math.round(d[i] / 255 * n) + Math.round(d[i + 1] / 255 * n) * N_LUT + Math.round(d[i + 2] / 255 * n) * N_LUT * N_LUT) * 4;
            d[i] = lut[o]; d[i + 1] = lut[o + 1]; d[i + 2] = lut[o + 2];
        }
        a.putImageData(px, 0, 0);
    }
    if (!cssLoc || cssLoc === 'none') return lut ? px : a.getImageData(0, 0, w, h);
    const b = cvB.getContext('2d', { willReadFrequently: true });
    b.clearRect(0, 0, w, h);
    b.filter = cssLoc;
    b.drawImage(cvA, 0, 0);
    b.filter = 'none';
    return b.getImageData(0, 0, w, h);
}

/* Vẽ scope `kieu` của ImageData `px` lên canvas `cv`. */
export function veScope(cv, kieu, px) {
    const c = cv.getContext('2d'), W = cv.width, H = cv.height;
    c.fillStyle = '#0b0b0d';
    c.fillRect(0, 0, W, H);
    c.strokeStyle = 'rgba(255,255,255,.08)';
    c.lineWidth = 1;
    if (!px) return;
    const d = px.data, w = px.width, h = px.height;
    if (kieu === 'histogram') {
        const hs = [new Uint32Array(256), new Uint32Array(256), new Uint32Array(256), new Uint32Array(256)];
        for (let i = 0; i < d.length; i += 4) {
            hs[0][d[i]]++; hs[1][d[i + 1]]++; hs[2][d[i + 2]]++;
            hs[3][Math.round(0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2])]++;
        }
        const max = Math.max(1, ...hs.slice(0, 3).map((x) => Math.max(...x.slice(1, 255))));
        c.globalCompositeOperation = 'lighter';
        [['rgba(255,60,60,.55)', 0], ['rgba(60,255,60,.55)', 1], ['rgba(70,110,255,.6)', 2], ['rgba(220,220,220,.25)', 3]].forEach(([mau, k]) => {
            c.fillStyle = mau;
            c.beginPath();
            c.moveTo(0, H);
            for (let x = 0; x < 256; x++) c.lineTo(x / 255 * W, H - Math.min(1, hs[k][x] / max) * H);
            c.lineTo(W, H);
            c.fill();
        });
        c.globalCompositeOperation = 'source-over';
        return;
    }
    const img = c.getImageData(0, 0, W, H), o = img.data;
    const cham = (x, y, r, g, b) => {
        if (x < 0 || y < 0 || x >= W || y >= H) return;
        const k = ((y | 0) * W + (x | 0)) * 4;
        o[k] = Math.min(255, o[k] + r); o[k + 1] = Math.min(255, o[k + 1] + g); o[k + 2] = Math.min(255, o[k + 2] + b);
    };
    const s = Math.max(6, Math.round(40000 / (w * h) * 24));       // độ sáng mỗi điểm
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const i = (y * w + x) * 4, r = d[i], g = d[i + 1], b = d[i + 2];
        if (kieu === 'waveform') {
            const Y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
            cham(x / w * W, H - 1 - Y / 255 * (H - 1), s, s, s);
        } else if (kieu === 'parade') {
            const ww = W / 3;
            cham(x / w * ww, H - 1 - r / 255 * (H - 1), s * 1.6, s * 0.3, s * 0.3);
            cham(ww + x / w * ww, H - 1 - g / 255 * (H - 1), s * 0.3, s * 1.6, s * 0.3);
            cham(2 * ww + x / w * ww, H - 1 - b / 255 * (H - 1), s * 0.4, s * 0.5, s * 1.8);
        } else {
            const cb = -0.1146 * r - 0.3854 * g + 0.5 * b, cr = 0.5 * r - 0.4542 * g - 0.0458 * b;    // BT.709, ±127.5
            const R = Math.min(W, H) / 2 - 4;
            cham(W / 2 + cb / 127.5 * R, H / 2 - cr / 127.5 * R, r / 255 * s + 4, g / 255 * s + 4, b / 255 * s + 4);
        }
    }
    c.putImageData(img, 0, 0);
    c.strokeStyle = 'rgba(255,255,255,.18)';
    if (kieu === 'vector') {
        const R = Math.min(W, H) / 2 - 4;
        c.beginPath(); c.arc(W / 2, H / 2, R, 0, 2 * Math.PI); c.stroke();
        // Đường màu da (skin tone line ~123°).
        const a = 123 * Math.PI / 180;
        c.strokeStyle = 'rgba(255,190,140,.5)';
        c.beginPath(); c.moveTo(W / 2, H / 2); c.lineTo(W / 2 + Math.cos(a) * R, H / 2 - Math.sin(a) * R); c.stroke();
    } else {
        for (const v of [0.25, 0.5, 0.75]) { c.beginPath(); c.moveTo(0, H * v); c.lineTo(W, H * v); c.stroke(); }
    }
}
