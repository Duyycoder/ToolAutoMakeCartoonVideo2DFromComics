/* Chỉnh màu nâng cao — BẢN SAO công thức của orchestrator/editor/mau_nang_cao.py (xuất ffmpeg).
   Preset + LUT .cube + đường cong + HSL gộp thành một LUT 3D 33³ → xem trước bằng WebGL (xem_mau_gl.js).
   Đổi công thức ở đây thì đổi cả file Python (tests/test_editor_mau_nang_cao.py so khớp hai bên). */
export let PRESET = {};
export const sanSang = typeof process !== 'undefined' && process.versions && process.versions.node
    ? import('fs').then((fs) => { PRESET = JSON.parse(fs.readFileSync(new URL('./preset_mau.json', import.meta.url), 'utf8')); })
    : fetch(new URL('./preset_mau.json', import.meta.url)).then((r) => r.json()).then((d) => { PRESET = d; }).catch(console.error);

export const N_LUT = 33;
const N_BANG = 1024;
export const VUNG_HSL = [['do', 0, 'Đỏ', '#e53935'], ['cam', 30, 'Cam', '#fb8c00'], ['vang', 60, 'Vàng', '#fdd835'],
    ['luc', 120, 'Lục', '#43a047'], ['xanh_ngoc', 180, 'Ngọc', '#00acc1'], ['lam', 240, 'Lam', '#1e88e5'],
    ['tim', 270, 'Tím', '#8e24aa'], ['hong', 300, 'Hồng', '#d81b60']];
const KENH = ['tong', 'do', 'luc', 'lam'];
const kep = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);
const mod = (a, n) => ((a % n) + n) % n;

export function bangDuongCong(diem) {
    const m0 = new Map();
    for (const [x, y] of diem || []) m0.set(Math.round(Number(x)), Number(y));
    const d = [...m0.entries()].sort((a, b) => a[0] - b[0]);
    if (d.length < 2 || (d.every(([x, y]) => Math.abs(x - y) < 1e-9) && d[0][0] === 0 && d[d.length - 1][0] === 255)) return null;
    const xs = d.map(([x]) => x / 255), ys = d.map(([, y]) => kep(y / 255));
    const n = xs.length;
    const dk = [];
    for (let k = 0; k < n - 1; k++) dk.push((ys[k + 1] - ys[k]) / (xs[k + 1] - xs[k]));
    const m = [dk[0]];
    for (let k = 1; k < n - 1; k++) m.push(dk[k - 1] * dk[k] <= 0 ? 0 : (dk[k - 1] + dk[k]) / 2);
    m.push(dk[n - 2]);
    for (let k = 0; k < n - 1; k++) {
        if (dk[k] === 0) { m[k] = 0; m[k + 1] = 0; continue; }
        const a = m[k] / dk[k], b = m[k + 1] / dk[k], s = a * a + b * b;
        if (s > 9) { const t = 3 / Math.sqrt(s); m[k] = t * a * dk[k]; m[k + 1] = t * b * dk[k]; }
    }
    const bang = new Float64Array(N_BANG + 1);
    let k = 0;
    for (let i = 0; i <= N_BANG; i++) {
        const x = i / N_BANG;
        if (x <= xs[0]) { bang[i] = ys[0]; continue; }
        if (x >= xs[n - 1]) { bang[i] = ys[n - 1]; continue; }
        while (x > xs[k + 1]) k++;
        const h = xs[k + 1] - xs[k], t = (x - xs[k]) / h, t2 = t * t, t3 = t2 * t;
        bang[i] = kep((2 * t3 - 3 * t2 + 1) * ys[k] + (t3 - 2 * t2 + t) * h * m[k]
            + (-2 * t3 + 3 * t2) * ys[k + 1] + (t3 - t2) * h * m[k + 1]);
    }
    return bang;
}

function tra(bang, x) {
    if (!bang) return x;
    const p = kep(x) * N_BANG, i = Math.min(Math.floor(p), N_BANG - 1);
    return bang[i] + (bang[i + 1] - bang[i]) * (p - i);
}

function cacBang(cong) {
    const b = {};
    for (const k of KENH) b[k] = bangDuongCong((cong || {})[k] || []);
    return KENH.some((k) => b[k]) ? b : null;
}

const apCong = (c, b) => [tra(b.do, tra(b.tong, c[0])), tra(b.luc, tra(b.tong, c[1])), tra(b.lam, tra(b.tong, c[2]))];

function baoHoa(c, bh) {
    if (!bh) return c;
    const k = 1 + bh / 100, y = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    return c.map((v) => kep(y + (v - y) * k));
}

function hslHopLe(hsl) {
    const ds = VUNG_HSL.map(([ten]) => ((hsl || {})[ten] || [0, 0, 0]).slice(0, 3).map(Number));
    return ds.some((x) => x.some(Boolean)) ? ds : null;
}

function apHsl(c, ds) {
    const [r, g, b] = c, mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
    if (d < 1e-6) return c;
    let l = (mx + mn) / 2;
    let s = Math.abs(2 * l - 1) < 1 ? d / (1 - Math.abs(2 * l - 1)) : 0;
    let h = mx === r ? mod((g - b) / d, 6) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h *= 60;
    let i = 0;
    while (i < VUNG_HSL.length - 1 && h >= VUNG_HSL[i + 1][1]) i++;
    const j = (i + 1) % VUNG_HSL.length, c0 = VUNG_HSL[i][1], c1 = j ? VUNG_HSL[j][1] : 360;
    const t = (h - c0) / (c1 - c0);
    const [dh, dS, dl] = [0, 1, 2].map((k) => (1 - t) * ds[i][k] + t * ds[j][k]);
    h = mod(h + dh * 0.3, 360);
    s = kep(s * (1 + dS / 100));
    l = kep(l * (1 + 0.5 * dl / 100 * s));
    const cc = (1 - Math.abs(2 * l - 1)) * s, x = cc * (1 - Math.abs(mod(h / 60, 2) - 1)), m = l - cc / 2;
    const [r1, g1, b1] = [[cc, x, 0], [x, cc, 0], [0, cc, x], [0, x, cc], [x, 0, cc], [cc, 0, x]][Math.floor(h / 60) % 6];
    return [kep(r1 + m), kep(g1 + m), kep(b1 + m)];
}

/* ---- chỉnh sơ cấp (tab Màu chuyên sâu): cân bằng trắng → tông sáng/tối → bánh xe Lift/Gamma/Gain/Offset ---- */
export const TONG = ['den', 'toi', 'sang', 'trang'];
export const BANH_XE = ['lift', 'gamma', 'gain', 'offset'];
const muot = (a, b, x) => { const t = kep((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const trongSoTong = (y) => [1 - muot(0, 0.3, y), Math.exp(-(((y - 0.25) / 0.18) ** 2)), Math.exp(-(((y - 0.75) / 0.18) ** 2)), muot(0.7, 1, y)];

/* Điểm (x, y) trên bánh xe → độ lệch RGB tổng 0, độ lớn = bán kính (giống _vec_mau bên Python). */
export function vecMau(x, y) {
    const r = Math.min(1, Math.hypot(x, y));
    if (r < 1e-6) return [0, 0, 0];
    const h = Math.atan2(y, x);
    return [0, 1, 2].map((k) => r * Math.cos(h - k * 2 * Math.PI / 3) * 2 / 3);
}

function soCapHopLe(mau) {
    let ct = Array.isArray(mau.can_trang) && mau.can_trang.length >= 3 ? mau.can_trang.slice(0, 3).map((v) => Math.max(0.5, Math.min(2, Number(v)))) : null;
    if (ct && ct.every((v) => Math.abs(v - 1) < 1e-4)) ct = null;
    const tg0 = mau.tong || {}, tg = TONG.map((k) => Math.max(-100, Math.min(100, Number(tg0[k] || 0))));
    const bx0 = mau.banh_xe || {}, bx = {};
    for (const k of BANH_XE) { const v = (bx0[k] || [0, 0, 0]).slice(0, 3).map(Number); if (v.some(Boolean)) bx[k] = v; }
    if (!(ct || tg.some(Boolean) || Object.keys(bx).length)) return null;
    return { ct, tg: tg.some(Boolean) ? tg : null, bx };
}

function apSoCap(c, sc) {
    if (sc.ct) c = c.map((v, k) => kep(v * sc.ct[k]));
    if (sc.tg) {
        const y = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2], w = trongSoTong(y);
        const d = 0.25 * sc.tg.reduce((a, k, i) => a + k / 100 * w[i], 0);
        c = c.map((v) => kep(v + d));
    }
    const bx = sc.bx;
    if (bx.lift) { const v = vecMau(bx.lift[0], bx.lift[1]), l = bx.lift[2] / 100; c = c.map((x, k) => kep(x + (0.25 * v[k] + 0.25 * l) * (1 - x))); }
    if (bx.gamma) { const v = vecMau(bx.gamma[0], bx.gamma[1]), l = bx.gamma[2] / 100; c = c.map((x, k) => kep(x) ** (1 / Math.max(0.1, 1 + 0.5 * v[k] + 0.5 * l))); }
    if (bx.gain) { const v = vecMau(bx.gain[0], bx.gain[1]), l = bx.gain[2] / 100; c = c.map((x, k) => kep(x * (1 + 0.5 * v[k] + 0.5 * l))); }
    if (bx.offset) { const v = vecMau(bx.offset[0], bx.offset[1]), l = bx.offset[2] / 100; c = c.map((x, k) => kep(x + 0.15 * v[k] + 0.15 * l)); }
    return c;
}

/* LUT 3D .cube → {n, du: Float32Array(n³·3)}; ném Error nếu hỏng. */
export function docCube(text) {
    let n = 0;
    const du = [];
    for (let dong of text.split(/\r?\n/)) {
        dong = dong.trim();
        if (!dong || dong.startsWith('#')) continue;
        const up = dong.toUpperCase();
        if (up.startsWith('LUT_3D_SIZE')) n = parseInt(dong.split(/\s+/)[1], 10);
        else if (up.startsWith('LUT_1D_SIZE')) throw new Error('Chỉ hỗ trợ LUT 3D (.cube có LUT_3D_SIZE).');
        else if (/^[-+0-9.eE]/.test(dong)) {
            const p = dong.split(/\s+/);
            if (p.length >= 3) du.push(kep(+p[0]), kep(+p[1]), kep(+p[2]));
        }
    }
    if (!(n >= 2 && n <= 129) || du.length !== n ** 3 * 3) throw new Error(`File .cube hỏng: LUT_3D_SIZE ${n}, có ${du.length / 3} dòng màu.`);
    return { n, du: Float64Array.from(du) };
}

function mauLut({ n, du }, c) {
    const p = c.map((x) => x * (n - 1)), i = p.map((x) => Math.min(Math.floor(x), n - 2)), f = p.map((x, k) => x - i[k]);
    const out = [0, 0, 0];
    for (let dz = 0; dz < 2; dz++) for (let dy = 0; dy < 2; dy++) for (let dx = 0; dx < 2; dx++) {
        const w = (dx ? f[0] : 1 - f[0]) * (dy ? f[1] : 1 - f[1]) * (dz ? f[2] : 1 - f[2]);
        if (!w) continue;
        const o = ((i[0] + dx) + (i[1] + dy) * n + (i[2] + dz) * n * n) * 3;
        for (let k = 0; k < 3; k++) out[k] += w * du[o + k];
    }
    return out;
}

const tron = (a, b, m) => a.map((v, k) => v + (b[k] - v) * m);

/* Hàm rgb→rgb của clip; null nếu không cần LUT. `lut` là kết quả docCube của file mau.lut (nếu có). */
export function hamMau(mau, lut = null) {
    mau = mau || {};
    const pr = PRESET[mau.preset || ''];
    const pm = pr ? Number(mau.preset_manh ?? 100) / 100 : 0;
    const prCong = pr ? cacBang(pr.cong) : null, prHsl = pr ? hslHopLe(pr.hsl) : null;
    const lm = lut ? Number(mau.lut_manh ?? 100) / 100 : 0;
    const cong = cacBang(mau.cong), hsl = hslHopLe(mau.hsl), sc = soCapHopLe(mau);
    if (!(pm || lm || cong || hsl || sc)) return null;
    return (c) => {
        if (sc) c = apSoCap(c, sc);
        if (lm) c = tron(c, mauLut(lut, c), lm);
        if (pm) {
            let v = prCong ? apCong(c, prCong) : c;
            v = baoHoa(v, Number(pr.bao_hoa || 0));
            v = prHsl ? apHsl(v, prHsl) : v;
            c = tron(c, v, pm);
        }
        if (cong) c = apCong(c, cong);
        if (hsl) c = apHsl(c, hsl);
        return c;
    };
}

/* Các khoá của clip.mau gộp vào LUT (đổi khoá nào thì dựng lại LUT) — giống KHOA_LUT bên Python. */
export const KHOA_LUT = ['preset', 'preset_manh', 'lut', 'lut_manh', 'cong', 'hsl', 'can_trang', 'tong', 'banh_xe'];

/* LUT 33³ RGBA8 (r chạy nhanh nhất) cho texImage3D; null nếu clip không cần. */
export function taoLut(mau, lut = null) {
    const f = hamMau(mau, lut);
    if (!f) return null;
    const n = N_LUT, out = new Uint8Array(n * n * n * 4);
    let o = 0;
    for (let b = 0; b < n; b++) for (let g = 0; g < n; g++) for (let r = 0; r < n; r++) {
        const v = f([r / (n - 1), g / (n - 1), b / (n - 1)]);
        out[o++] = Math.round(v[0] * 255); out[o++] = Math.round(v[1] * 255); out[o++] = Math.round(v[2] * 255); out[o++] = 255;
    }
    return out;
}

/* Clip có dùng chỉnh màu nâng cao (cần vẽ WebGL) không. */
export function coNangCao(mau) {
    mau = mau || {};
    return !!(mau.preset || mau.lut || mau.lam_net || mau.khu_nhieu || cacBang(mau.cong) || hslHopLe(mau.hsl) || soCapHopLe(mau));
}
