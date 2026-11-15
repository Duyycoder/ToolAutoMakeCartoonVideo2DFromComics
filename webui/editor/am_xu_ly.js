/* Xem trước xử lý âm thanh của clip (clip.xu_ly_am) bằng Web Audio — cùng tần số với orchestrator/editor/xu_ly_am.py.
   Chỉ nối thẻ <video>/<audio> vào Web Audio khi clip có chỉnh (nối rồi thì tiếng luôn đi qua AudioContext).
   Khử nhiễu FFT không làm được trên trình duyệt: preview chỉ cắt ù/gió dưới 80 Hz. */
let ac = null;
const doThi = new WeakMap();

export const coXuLy = (x) => !!x && ['giam_on', 'thap', 'trung', 'cao'].some((k) => Math.abs(Number(x[k] || 0)) >= 0.1);

/* Gọi trong lúc người dùng bấm (Phát): Safari/Chrome chỉ cho AudioContext chạy sau thao tác của người dùng. */
export function moKhoaAm() { if (ac && ac.state === 'suspended') ac.resume().catch(() => {}); }

export function ganXuLy(el, x) {
    let g = doThi.get(el);
    if (!g && !coXuLy(x)) return;
    if (!g) {
        try {
            ac = ac || new (window.AudioContext || window.webkitAudioContext)();
            const nguon = ac.createMediaElementSource(el);
            const tao = (type, f, q) => {
                const b = ac.createBiquadFilter();
                b.type = type;
                b.frequency.value = f;
                if (q) b.Q.value = q;
                return b;
            };
            g = { nguon, hp: tao('highpass', 10), thap: tao('lowshelf', 120), trung: tao('peaking', 1500, 1), cao: tao('highshelf', 6000) };
            nguon.connect(g.hp).connect(g.thap).connect(g.trung).connect(g.cao).connect(ac.destination);
            doThi.set(el, g);
        } catch (e) {
            console.warn('Không xem trước được xử lý âm thanh:', e.message);
            return;
        }
    }
    x = x || {};
    g.hp.frequency.value = Number(x.giam_on || 0) > 0 ? 80 : 10;
    for (const k of ['thap', 'trung', 'cao']) g[k].gain.value = Math.max(-12, Math.min(12, Number(x[k] || 0)));
    moKhoaAm();
}

/* Thẻ <audio> bị bỏ: tháo khỏi Web Audio cho khỏi giữ bộ nhớ. */
export function boXuLy(el) {
    const g = doThi.get(el);
    if (!g) return;
    try { g.nguon.disconnect(); g.cao.disconnect(); } catch (e) { /* đã tháo */ }
    doThi.delete(el);
}
