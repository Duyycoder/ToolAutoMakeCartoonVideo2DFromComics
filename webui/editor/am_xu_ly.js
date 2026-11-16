/* Xem trước xử lý âm thanh của clip (clip.xu_ly_am) bằng Web Audio — cùng tần số với orchestrator/editor/xu_ly_am.py.
   Chỉ nối thẻ <video>/<audio> vào Web Audio khi clip có chỉnh (nối rồi thì tiếng luôn đi qua AudioContext).
   Khử nhiễu FFT không làm được trên trình duyệt: preview chỉ cắt ù/gió dưới 80 Hz.
   Sau EQ là chuỗi hiệu ứng âm thanh của clip (clip.hieu_ung_am — am_hieu_ung.js). */
import { coHieuUng, taoChuoi } from './am_hieu_ung.js';

let ac = null;
const doThi = new WeakMap();
// Chuỗi CHUNG của cả dự án (timeline.am_tong): mọi tiếng đi qua đây rồi mới ra loa — giống _tieng_tong của render.py.
let tong = null, tongCaiDat = {}, tongBat = false;

function layTong() {
    if (!tong) {
        tong = taoChuoi(ac);
        tong.gainTong = ac.createGain();
        tong.ra.connect(tong.gainTong).connect(ac.destination);
    }
    tong.dat(tongCaiDat);
    tong.gainTong.gain.value = Number(tongCaiDat.am_luong ?? 1);
    return tong;
}

/* Đặt hiệu ứng chung (gọi khi timeline đổi). Có hiệu ứng/âm lượng ≠ 100% thì mọi thẻ tiếng được nối qua Web Audio. */
export function datTong(x) {
    tongCaiDat = x || {};
    tongBat = coHieuUng(tongCaiDat) || Math.abs(Number(tongCaiDat.am_luong ?? 1) - 1) > 1e-3;
    if (ac && tong) layTong();
}

export const coXuLy = (x) => !!x && ['giam_on', 'thap', 'trung', 'cao'].some((k) => Math.abs(Number(x[k] || 0)) >= 0.1);

/* Gọi trong lúc người dùng bấm (Phát): Safari/Chrome chỉ cho AudioContext chạy sau thao tác của người dùng. */
export function moKhoaAm() { if (ac && ac.state === 'suspended') ac.resume().catch(() => {}); }

export function ganXuLy(el, x, hu) {
    let g = doThi.get(el);
    if (!g && !coXuLy(x) && !coHieuUng(hu) && !tongBat) return;
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
            g = { nguon, hp: tao('highpass', 10), thap: tao('lowshelf', 120), trung: tao('peaking', 1500, 1), cao: tao('highshelf', 6000),
                hu: taoChuoi(ac) };
            nguon.connect(g.hp).connect(g.thap).connect(g.trung).connect(g.cao).connect(g.hu.vao);
            g.hu.ra.connect(layTong().vao);
            doThi.set(el, g);
        } catch (e) {
            console.warn('Không xem trước được xử lý âm thanh:', e.message);
            return;
        }
    }
    x = x || {};
    g.hp.frequency.value = Number(x.giam_on || 0) > 0 ? 80 : 10;
    for (const k of ['thap', 'trung', 'cao']) g[k].gain.value = Math.max(-12, Math.min(12, Number(x[k] || 0)));
    g.hu.dat(hu);
    moKhoaAm();
}

/* Thẻ <audio> bị bỏ: tháo khỏi Web Audio cho khỏi giữ bộ nhớ. */
export function boXuLy(el) {
    const g = doThi.get(el);
    if (!g) return;
    try { g.nguon.disconnect(); g.hu.ra.disconnect(); g.hu.lfo.stop(); } catch (e) { /* đã tháo */ }
    doThi.delete(el);
}
