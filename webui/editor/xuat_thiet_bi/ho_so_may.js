/* Hồ sơ máy: đo GIỚI HẠN THẬT của thiết bị cho việc xuất video trên máy (không đoán theo tên máy).
   Bước 1: VideoEncoder.isConfigSupported — lọc nhanh codec × độ phân giải nào máy nhận.
   Bước 2: chạy thử — mã hoá ~1,5 s khung WebGL có chi tiết thật (không phải khung trống) → khung/giây đạt được.
   isConfigSupported hay "nói dối" (nhận cấu hình nhưng lỗi/chậm khi chạy, nhất là Safari 4K HEVC) → chỉ tin số chạy thử.
   Kết quả lưu localStorage theo trình duyệt + ngày; nút "Đo lại" xoá cache. */

export const CODEC = [
    ['avc', 'H.264', 'avc1.640034'],          // High L5.2 — đủ cho 4K60
    ['hevc', 'HEVC', 'hvc1.1.6.L153.B0'],     // Main L5.1
    ['av1', 'AV1', 'av01.0.12M.08'],
];
export const DO_PHAN_GIAI = [['720p', 1280, 720], ['1080p', 1920, 1080], ['1440p', 2560, 1440], ['4k', 3840, 2160]];
const KHOA = 'ho_so_may_v1';
const KHUNG_THU = 45;            // số khung mỗi lần chạy thử
const HET_GIO_THU = 6000;        // ms — một cấu hình chạy thử quá lâu thì dừng, tính theo số khung đã xong

/* Khung thử: gradient động + nhiễu + vạch — đủ chi tiết để bộ mã hoá làm việc thật (khung trống mã hoá nhanh giả). */
function taoNguonThu(w, h) {
    const cv = new OffscreenCanvas(w, h);
    const gl = cv.getContext('webgl2', { antialias: false, preserveDrawingBuffer: false });
    if (!gl) return { cv, ve: () => {}, gl: null };
    const sh = (loai, src) => { const s = gl.createShader(loai); gl.shaderSource(s, src); gl.compileShader(s); return s; };
    const pg = gl.createProgram();
    gl.attachShader(pg, sh(gl.VERTEX_SHADER, '#version 300 es\nin vec2 p;void main(){gl_Position=vec4(p,0.,1.);}'));
    gl.attachShader(pg, sh(gl.FRAGMENT_SHADER, `#version 300 es
precision highp float; uniform float t; uniform vec2 r; out vec4 o;
float n(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233)) + t) * 43758.5453); }
void main(){ vec2 u = gl_FragCoord.xy / r;
  vec3 c = 0.5 + 0.5 * cos(t + u.xyx * 6.0 + vec3(0, 2, 4));
  c += 0.25 * n(gl_FragCoord.xy) + 0.2 * step(0.5, fract((u.x + u.y + t * 0.1) * 40.0));
  o = vec4(c, 1.0); }`));
    gl.linkProgram(pg);
    gl.useProgram(pg);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    const ut = gl.getUniformLocation(pg, 't'), ur = gl.getUniformLocation(pg, 'r');
    return {
        cv, gl,
        ve(i) { gl.viewport(0, 0, w, h); gl.uniform1f(ut, i * 0.05); gl.uniform2f(ur, w, h); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); },
    };
}

function cauHinh(chuoi, w, h, fps = 30) {
    return { codec: chuoi, width: w, height: h, framerate: fps, bitrate: Math.round(w * h * fps * 0.12),
        hardwareAcceleration: 'prefer-hardware', latencyMode: 'quality', avc: chuoi.startsWith('avc') ? { format: 'avc' } : undefined };
}

/* Mã hoá KHUNG_THU khung → {khung_giay, loi}. */
async function chayThu(chuoi, w, h, phanCung) {
    const nguon = taoNguonThu(w, h);
    if (!nguon.gl) return { khung_giay: 0, loi: 'không có WebGL2 trong OffscreenCanvas' };
    let xong = 0, loi = null;
    const enc = new VideoEncoder({ output: () => { xong++; }, error: (e) => { loi = e.message; } });
    try {
        enc.configure({ ...cauHinh(chuoi, w, h), hardwareAcceleration: phanCung ? 'prefer-hardware' : 'no-preference' });
        const t0 = performance.now();
        for (let i = 0; i < KHUNG_THU && !loi; i++) {
            nguon.ve(i);
            const f = new VideoFrame(nguon.cv, { timestamp: Math.round(i * 1e6 / 30), duration: Math.round(1e6 / 30) });
            enc.encode(f, { keyFrame: i % 60 === 0 });
            f.close();
            while (enc.encodeQueueSize > 4 && !loi) await new Promise((r) => setTimeout(r, 1));
            if (performance.now() - t0 > HET_GIO_THU) break;
        }
        await Promise.race([enc.flush(), new Promise((r) => setTimeout(r, HET_GIO_THU))]);
        const giay = (performance.now() - t0) / 1000;
        return { khung_giay: loi ? 0 : Math.round(xong / giay), loi };
    } catch (e) {
        return { khung_giay: 0, loi: e.message };
    } finally {
        try { enc.close(); } catch (e) { /* đã đóng */ }
    }
}

function thongTinChung() {
    const cv = new OffscreenCanvas(1, 1);
    const gl = cv.getContext('webgl2');
    return {
        trinh_duyet: navigator.userAgent,
        webcodecs: typeof VideoEncoder === 'function' && typeof VideoDecoder === 'function',
        webgl2: !!gl,
        max_texture: gl ? gl.getParameter(gl.MAX_TEXTURE_SIZE) : 0,
        bo_nho_gb: navigator.deviceMemory || null,      // Chrome; Safari không có
        luong_cpu: navigator.hardwareConcurrency || null,
    };
}

export function hoSoDaLuu() {
    try {
        const d = JSON.parse(localStorage.getItem(KHOA) || 'null');
        return d && d.trinh_duyet === navigator.userAgent ? d : null;
    } catch (e) { return null; }
}

/* Đo hồ sơ máy. baoTienDo(phan_tram, chu). chayThuDayDu=false: chỉ bước lọc (nhanh, không đo tốc độ). */
export async function doHoSo({ baoTienDo = () => {}, chayThuDayDu = true } = {}) {
    const hs = { ...thongTinChung(), luc: new Date().toISOString(), ma_hoa: [] };
    if (navigator.storage && navigator.storage.estimate) {
        try { const e = await navigator.storage.estimate(); hs.opfs_trong_gb = Math.round((e.quota - e.usage) / 1e8) / 10; } catch (e) { /* bỏ qua */ }
    }
    if (!hs.webcodecs) return hs;
    const viec = [];
    for (const [k, ten, chuoi] of CODEC) for (const [nhan, w, h] of DO_PHAN_GIAI) viec.push({ codec: k, ten, chuoi, nhan, w, h });
    let i = 0;
    for (const v of viec) {
        baoTienDo(Math.round(i++ / viec.length * 100), `Kiểm ${v.ten} ${v.nhan}…`);
        let nhan = false, phanCung = null;
        try {
            const r = await VideoEncoder.isConfigSupported({ ...cauHinh(v.chuoi, v.w, v.h), hardwareAcceleration: 'no-preference' });
            nhan = !!r.supported;
            if (nhan) {
                const cung = await VideoEncoder.isConfigSupported({ ...cauHinh(v.chuoi, v.w, v.h), hardwareAcceleration: 'prefer-hardware' });
                phanCung = !!cung.supported;
            }
        } catch (e) { nhan = false; }
        const muc = { codec: v.codec, ten: v.ten, do_phan_giai: v.nhan, w: v.w, h: v.h, nhan, phan_cung: phanCung, khung_giay: null, loi: null };
        if (nhan && chayThuDayDu) {
            baoTienDo(Math.round(i / viec.length * 100), `Chạy thử ${v.ten} ${v.nhan}…`);
            Object.assign(muc, await chayThu(v.chuoi, v.w, v.h, phanCung));
        }
        hs.ma_hoa.push(muc);
    }
    baoTienDo(100, 'Xong');
    try { localStorage.setItem(KHOA, JSON.stringify(hs)); } catch (e) { /* bộ nhớ trình duyệt bị chặn */ }
    return hs;
}

/* fps tối đa xuất được (offline không cần thời gian thực) và thời gian ước lượng cho video dài `giay` ở `fps`. */
export function uocLuong(muc, giay, fps) {
    if (!muc || !muc.khung_giay) return null;
    return { giay_xuat: Math.round(giay * fps / muc.khung_giay), nhanh_hon_thoi_gian_thuc: muc.khung_giay >= fps };
}
