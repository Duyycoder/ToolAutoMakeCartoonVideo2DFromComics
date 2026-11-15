/* Khung hình dự án (dọc/ngang/vuông, độ phân giải, fps) — đổi được bất cứ lúc nào trong editor.
   Một thiết lập duy nhất cho CẢ màn xem trước lẫn bản xuất: clip tự co vừa khung mới (giữ biến đổi %).
   Dùng ở: bấm "1080×1920 │ 30fps" trên thanh đầu editor, và ô "Khung hình" trong hộp Xuất video. */
import { api, esc, toast } from './chung.js';

export const KHUNG = [
    ['9:16', 'Dọc 9:16 — TikTok, Reels, Shorts', 9, 16],
    ['16:9', 'Ngang 16:9 — YouTube', 16, 9],
    ['1:1', 'Vuông 1:1', 1, 1],
    ['4:5', 'Dọc 4:5 — Instagram', 4, 5],
    ['3:4', 'Dọc 3:4', 3, 4],
    ['4:3', 'Ngang 4:3', 4, 3],
];
const CANH_NGAN = [[720, '720p'], [1080, '1080p (Full HD)'], [1440, '1440p (2K)'], [2160, '2160p (4K)']];
const FPS = [24, 25, 30, 50, 60];
const chan = (x) => Math.max(2, Math.round(x / 2) * 2);

/* Khung hiện tại của dự án → {khung: '9:16' | '', canh: cạnh ngắn}. */
export function khungHienTai(ts) {
    const r = Number(ts.rong) || 1920, c = Number(ts.cao) || 1080;
    const k = KHUNG.find(([, , a, b]) => Math.abs(r / c - a / b) < 0.01);
    return { khung: k ? k[0] : '', canh: Math.min(r, c) };
}

export function kichThuoc(khung, canh) {
    const k = KHUNG.find(([id]) => id === khung);
    if (!k) return null;
    const [, , a, b] = k;
    return a <= b ? [chan(canh), chan(canh * b / a)] : [chan(canh * a / b), chan(canh)];
}

/* Ghi khung mới vào dự án rồi báo cho preview/timeline vẽ lại. */
export async function datKhung(ctx, { khung, canh, fps }) {
    const ts = ctx.du.thong_so || {};
    const hien = khungHienTai(ts);
    const wh = kichThuoc(khung || hien.khung || '16:9', canh || hien.canh);
    const moi = { ...ts, rong: wh[0], cao: wh[1], fps: fps || ts.fps || 30, theo_video_dau: false };
    if (moi.rong === ts.rong && moi.cao === ts.cao && moi.fps === ts.fps && !ts.theo_video_dau) return false;
    const r = await api(`/api/du-an/${encodeURIComponent(ctx.id)}`, { method: 'PATCH', body: { thong_so: moi } });
    ctx.du.thong_so = r.thong_so;
    ctx.bus.emit('thong_so');
    return true;
}

export function moHopKhung(ctx) {
    if (ctx.store.chiDoc) { toast('Cửa sổ này chỉ xem.', 'warn'); return; }
    const ts = ctx.du.thong_so || {};
    const hien = khungHienTai(ts);
    const nen = document.createElement('div');
    nen.className = 'modal-nen';
    nen.innerHTML = `<form class="modal" style="width:min(420px,100%)">
        <h3>Khung hình dự án</h3>
        <p class="modal-noi-dung">Đang là ${ts.rong}×${ts.cao} · ${ts.fps} fps. Đổi ở đây thì cả màn xem trước và video xuất đều đổi theo;
            clip tự co vừa khung mới.</p>
        <div class="o-form">
            <div class="khung-chon">${KHUNG.map(([id, ten, a, b]) => `<label class="khung-o ${id === hien.khung ? 'bat' : ''}">
                <input type="radio" name="khung" value="${id}" ${id === hien.khung ? 'checked' : ''}>
                <i style="aspect-ratio:${a}/${b}"></i><span>${esc(ten)}</span></label>`).join('')}</div>
            <div class="hang">
                <label>Độ phân giải<select name="canh">${CANH_NGAN.map(([v, t]) =>
                    `<option value="${v}" ${v === hien.canh ? 'selected' : ''}>${t}</option>`).join('')}
                    ${CANH_NGAN.some(([v]) => v === hien.canh) ? '' : `<option value="${hien.canh}" selected>${hien.canh}p (hiện tại)</option>`}</select></label>
                <label>FPS<select name="fps">${[...new Set([...FPS, Number(ts.fps) || 30])].sort((x, y) => x - y).map((v) =>
                    `<option value="${v}" ${v === Number(ts.fps) ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
            </div>
        </div>
        <div class="modal-nut"><button type="button" class="nut" data-huy>Huỷ</button><button type="submit" class="nut nut-chinh">Áp dụng</button></div>
    </form>`;
    document.body.appendChild(nen);
    const f = nen.querySelector('form');
    const dong = () => nen.remove();
    nen.querySelector('[data-huy]').addEventListener('click', dong);
    nen.addEventListener('keydown', (e) => { if (e.key === 'Escape') dong(); });
    f.addEventListener('change', () => f.querySelectorAll('.khung-o').forEach((o) => o.classList.toggle('bat', o.querySelector('input').checked)));
    f.addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            const doi = await datKhung(ctx, { khung: (f.khung.value || hien.khung || '16:9'), canh: Number(f.canh.value), fps: Number(f.fps.value) });
            dong();
            if (doi) toast(`Khung dự án: ${ctx.du.thong_so.rong}×${ctx.du.thong_so.cao} · ${ctx.du.thong_so.fps} fps`, 'success', 3000);
        } catch (err) { toast(err.message, 'error'); }
    });
}
