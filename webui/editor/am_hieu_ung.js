/* Xem trước hiệu ứng âm thanh của clip (clip.hieu_ung_am) bằng Web Audio — cùng công thức với
   orchestrator/editor/hieu_ung_am.py: lọc dải (điện thoại/radio/loa), méo atan, bitcrush, tremolo, nén, dội 3 lần, vang IR.
   Cao độ, robot, phát ngược, chuẩn hoá: trình duyệt không làm thời gian thực được → chỉ nghe ở bản xuất / Xem chính xác. */
export const LOC_BANG = { dien_thoai: [300, 3400], radio: [450, 4500], loa: [600, 3000] };
export const PHONG = { phong_nho: [0.5, 4, 0.25], phong_lon: [1.4, 14, 0.4], nha_tho: [3.2, 28, 0.55], hang: [2.2, 20, 0.3] };
export const CHI_KHI_XUAT = ['cao_do', 'robot', 'dao_nguoc', 'chuan_hoa'];

const kep = (x, a, b) => Math.max(a, Math.min(b, Number(x) || 0));

export const coHieuUng = (h) => !!h && (['cao_do', 'meo', 'bit', 'rung', 'nen', 'doi', 'vang'].some((k) => Number(h[k] || 0))
    || ['robot', 'loc_bang', 'dao_nguoc', 'chuan_hoa'].some((k) => !!h[k]));

/* Đáp ứng xung phòng (như ir_phong bên Python: nhiễu tắt dần theo RT60, lọc tối dần, năng lượng mỗi kênh = 1). */
const irCache = new Map();
function irPhong(ac, phong) {
    const khoa = `${phong}@${ac.sampleRate}`;
    if (irCache.has(khoa)) return irCache.get(khoa);
    const [rt, treMs, toi] = PHONG[phong] || PHONG.phong_lon;
    const sr = ac.sampleRate, n = Math.floor(sr * (rt + treMs / 1000)), tre = Math.floor(sr * treMs / 1000);
    const buf = ac.createBuffer(2, n, sr);
    for (let k = 0; k < 2; k++) {
        const d = buf.getChannelData(k);
        let y = 0, e = 0;
        for (let i = tre; i < n; i++) {
            y = y * toi + (Math.random() * 2 - 1) * (1 - toi);
            d[i] = y * Math.exp(-6.9078 * (i - tre) / sr / rt);
            e += d[i] * d[i];
        }
        e = Math.sqrt(e) || 1;
        for (let i = tre; i < n; i++) d[i] /= e;
    }
    irCache.set(khoa, buf);
    return buf;
}

function duongMeo(meo) {
    const g = 1 + 19 * Math.min(meo, 100) / 100, n = 2048, c = new Float32Array(n), at = Math.atan(g);
    for (let i = 0; i < n; i++) { const x = (i / (n - 1)) * 2 - 1; c[i] = Math.atan(g * x) / at; }
    return c;
}

function duongBit(bit) {
    const q = 2 ** (bit - 1), n = 4096, c = new Float32Array(n);
    for (let i = 0; i < n; i++) { const x = (i / (n - 1)) * 2 - 1; c[i] = Math.round(x * q) / q; }
    return c;
}

/* Chuỗi nút hiệu ứng: vao → … → ra. dat(h) cập nhật tham số (không dựng lại đồ thị). */
export function taoChuoi(ac) {
    const g = (v = 1) => { const x = ac.createGain(); x.gain.value = v; return x; };
    const bq = (type, f) => { const b = ac.createBiquadFilter(); b.type = type; b.frequency.value = f; return b; };
    const n = {
        vao: g(), hp1: bq('highpass', 10), hp2: bq('highpass', 10), lp1: bq('lowpass', 22000), lp2: bq('lowpass', 22000),
        meo: ac.createWaveShaper(), bit: ac.createWaveShaper(), rung: g(), lfo: ac.createOscillator(), lfoSau: g(0),
        nen: ac.createDynamicsCompressor(), bu: g(), doiKho: g(), tron: g(), vangKho: g(), vangUot: g(0),
        conv: ac.createConvolver(), ra: g(),
    };
    n.conv.normalize = false;
    n.doi = [1, 2, 3].map(() => ({ tre: ac.createDelay(3.5), gain: g(0) }));
    n.vao.connect(n.hp1).connect(n.hp2).connect(n.lp1).connect(n.lp2).connect(n.meo).connect(n.bit).connect(n.rung)
        .connect(n.nen).connect(n.bu);
    n.lfo.connect(n.lfoSau).connect(n.rung.gain);
    n.lfo.start();
    n.bu.connect(n.doiKho).connect(n.tron);
    for (const d of n.doi) n.bu.connect(d.tre).connect(d.gain).connect(n.tron);
    n.tron.connect(n.vangKho).connect(n.ra);
    n.tron.connect(n.conv).connect(n.vangUot).connect(n.ra);

    let khoa = null;
    n.dat = (h) => {
        h = h || {};
        const k = JSON.stringify(h);
        if (k === khoa) return;          // preview gọi mỗi khung — chỉ dựng lại đường cong khi tham số đổi
        khoa = k;
        const [thap, cao] = LOC_BANG[h.loc_bang] || [10, 22000];
        for (const b of [n.hp1, n.hp2]) b.frequency.value = thap;
        for (const b of [n.lp1, n.lp2]) b.frequency.value = Math.min(cao, ac.sampleRate / 2 - 100);
        const meo = kep(h.meo, 0, 100) + (h.loc_bang === 'loa' ? 25 : 0);
        n.meo.curve = meo > 0 ? duongMeo(meo) : null;
        const bit = Math.floor(kep(h.bit, 0, 12));
        n.bit.curve = bit >= 2 ? duongBit(bit) : null;
        // ffmpeg tremolo: gain = 1 - d/2 + (d/2)·sin(2πft)
        const d = kep(h.rung, 0, 100) / 100;
        n.lfo.frequency.value = kep(h.rung_tan || 6, 1, 20);
        n.rung.gain.value = 1 - d / 2;
        n.lfoSau.gain.value = d / 2;
        const a = kep(h.nen, 0, 100) / 100, nguong = -10 - 20 * a;
        n.nen.threshold.value = a ? nguong : 0;
        n.nen.ratio.value = 1 + 7 * a;
        n.nen.attack.value = 0.01;
        n.nen.release.value = 0.2;
        n.nen.knee.value = 0;
        n.bu.gain.value = a ? 10 ** ((-nguong * (1 - 1 / (1 + 7 * a)) * 0.5) / 20) : 1;
        const doi = kep(h.doi, 0, 100), tre = kep(h.doi_tre || 350, 80, 1000) / 1000, he = 0.2 + 0.5 * doi / 100;
        n.doi.forEach((x, i) => { x.tre.delayTime.value = tre * (i + 1); x.gain.gain.value = doi > 0 ? he ** (i + 1) : 0; });
        const v = kep(h.vang, 0, 100) / 100;
        if (v > 0) {
            const buf = irPhong(ac, h.phong || 'phong_lon');
            if (n.conv.buffer !== buf) n.conv.buffer = buf;
        }
        n.vangKho.gain.value = 1 - 0.5 * v;
        n.vangUot.gain.value = v;
    };
    return n;
}
