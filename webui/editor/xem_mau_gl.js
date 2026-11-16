/* Xem trước chỉnh màu nâng cao bằng WebGL2 trên MỘT lớp của màn xem trước.
   <video>/<img> của lớp vẫn chạy (để lấy khung hình) nhưng ẩn đi (opacity 0); canvas phủ lên vẽ:
   khử nhiễu → làm nét → LUT 3D gộp (mau_nang_cao.js). CSS filter của lớp (chỉnh màu cơ bản) vẫn áp lên
   canvas — đúng thứ tự với render.py. Máy không có WebGL2 thì lớp hiện như cũ (không có phần nâng cao). */
import { KHOA_LUT, N_LUT, taoLut } from './mau_nang_cao.js';

const VS = `#version 300 es
in vec2 p; out vec2 uv;
void main() { uv = vec2(p.x * 0.5 + 0.5, 0.5 - p.y * 0.5); gl_Position = vec4(p, 0.0, 1.0); }`;
const FS = `#version 300 es
precision highp float; precision highp sampler3D;
uniform sampler2D hinh; uniform sampler3D lut; uniform vec2 px; uniform float net, nhieu, coLut;
in vec2 uv; out vec4 o;
vec3 t(float x, float y) { return texture(hinh, uv + px * vec2(x, y)).rgb; }
void main() {
    vec3 c = texture(hinh, uv).rgb;
    if (net > 0.0 || nhieu > 0.0) {
        vec3 b = (t(-1.,-1.) + t(1.,-1.) + t(-1.,1.) + t(1.,1.) + 2.0 * (t(0.,-1.) + t(0.,1.) + t(-1.,0.) + t(1.,0.)) + 4.0 * c) / 16.0;
        c = mix(c, b, nhieu * (1.0 - smoothstep(0.02, 0.15, length(c - b))));   // giữ cạnh, làm mịn vùng phẳng
        c = clamp(c + net * (c - b), 0.0, 1.0);
    }
    if (coLut > 0.5) c = texture(lut, c * ${(N_LUT - 1) / N_LUT} + ${0.5 / N_LUT}).rgb;
    o = vec4(c, 1.0);
}`;

function bienDich(gl) {
    const sh = (loai, src) => {
        const s = gl.createShader(loai);
        gl.shaderSource(s, src);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
        return s;
    };
    const pg = gl.createProgram();
    gl.attachShader(pg, sh(gl.VERTEX_SHADER, VS));
    gl.attachShader(pg, sh(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(pg);
    if (!gl.getProgramParameter(pg, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pg));
    return pg;
}

export class LopGL {
    constructor(el) {
        this.cv = document.createElement('canvas');
        this.cv.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:none;pointer-events:none';
        el.appendChild(this.cv);
        this.nguon = null;
        this._khoaLut = null;
        try {
            const gl = this.cv.getContext('webgl2', { premultipliedAlpha: false, antialias: false });
            if (!gl) throw new Error('không có WebGL2');
            this.pg = bienDich(gl);
            gl.useProgram(this.pg);
            gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
            gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
            const p = gl.getAttribLocation(this.pg, 'p');
            gl.enableVertexAttribArray(p);
            gl.vertexAttribPointer(p, 2, gl.FLOAT, false, 0, 0);
            this.texHinh = this._tex(gl.TEXTURE0, gl.TEXTURE_2D);
            this.texLut = this._tex(gl.TEXTURE1, gl.TEXTURE_3D);
            gl.uniform1i(gl.getUniformLocation(this.pg, 'hinh'), 0);
            gl.uniform1i(gl.getUniformLocation(this.pg, 'lut'), 1);
            this.u = Object.fromEntries(['px', 'net', 'nhieu', 'coLut'].map((k) => [k, gl.getUniformLocation(this.pg, k)]));
            this.gl = gl;
        } catch (e) {
            console.warn('Xem trước màu nâng cao tắt:', e.message);
            this.gl = null;
        }
    }

    _tex(don_vi, loai) {
        const gl = this.cv.getContext('webgl2');
        const t = gl.createTexture();
        gl.activeTexture(don_vi);
        gl.bindTexture(loai, t);
        for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR],
            [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_R, gl.CLAMP_TO_EDGE]]) gl.texParameteri(loai, k, v);
        return t;
    }

    /* Vẽ `nguon` (<video>/<img>) với chỉnh màu `mau`; `lutFile` = docCube của mau.lut (null nếu chưa tải/không có). */
    dat(nguon, mau, lutFile) {
        if (!this.gl) return false;
        const gl = this.gl;
        if (this.nguon !== nguon) { this._dungHen(); if (this.nguon) this.nguon.style.opacity = ''; this.nguon = nguon; }
        const khoa = JSON.stringify([...KHOA_LUT.map((k) => mau[k]), !!lutFile]);
        if (khoa !== this._khoaLut) {
            this._khoaLut = khoa;
            const du = taoLut(mau, lutFile);
            this.coLut = !!du;
            if (du) {
                gl.activeTexture(gl.TEXTURE1);
                gl.texImage3D(gl.TEXTURE_3D, 0, gl.RGBA8, N_LUT, N_LUT, N_LUT, 0, gl.RGBA, gl.UNSIGNED_BYTE, du);
            }
        }
        this.net = 1.5 * Number(mau.lam_net || 0) / 100;
        this.nhieu = Number(mau.khu_nhieu || 0) / 100;
        nguon.style.opacity = '0';
        this.cv.style.display = '';
        this.ve();
        if (!this._hen) this._lap();
        return true;
    }

    ve() {
        const gl = this.gl, n = this.nguon;
        if (!gl || !n) return;
        const w = n.videoWidth || n.naturalWidth, h = n.videoHeight || n.naturalHeight;
        if (!w || !h || (n.readyState !== undefined && n.readyState < 2)) return;
        const k = Math.min(1, 1920 / Math.max(w, h));
        const cw = Math.round(w * k), ch = Math.round(h * k);
        if (this.cv.width !== cw || this.cv.height !== ch) { this.cv.width = cw; this.cv.height = ch; }
        gl.viewport(0, 0, cw, ch);
        gl.activeTexture(gl.TEXTURE0);
        try { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, n); } catch (e) { return; }
        gl.uniform2f(this.u.px, 1 / w, 1 / h);
        gl.uniform1f(this.u.net, this.net);
        gl.uniform1f(this.u.nhieu, this.nhieu);
        gl.uniform1f(this.u.coLut, this.coLut ? 1 : 0);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }

    /* Vẽ lại mỗi khung mới của video (cả khi tua lúc dừng); ảnh thì vẽ khi tải xong. */
    _lap() {
        const n = this.nguon;
        if (!n) return;
        if (n.tagName === 'IMG') {
            if (!n.complete) { this._hen = { img: true }; n.addEventListener('load', () => { this._hen = null; this.ve(); }, { once: true }); }
            return;
        }
        if (n.requestVideoFrameCallback) {
            this._hen = { v: n.requestVideoFrameCallback(() => { this._hen = null; this.ve(); this._lap(); }) };
        } else {
            this._hen = { raf: requestAnimationFrame(() => { this._hen = null; this.ve(); this._lap(); }) };
        }
    }

    _dungHen() {
        if (!this._hen) return;
        if (this._hen.v != null && this.nguon?.cancelVideoFrameCallback) this.nguon.cancelVideoFrameCallback(this._hen.v);
        if (this._hen.raf != null) cancelAnimationFrame(this._hen.raf);
        this._hen = null;
    }

    tat() {
        this._dungHen();
        if (this.nguon) this.nguon.style.opacity = '';
        this.nguon = null;
        this.cv.style.display = 'none';
    }
}
